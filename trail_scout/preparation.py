"""Inspectable, bounded official access snapshots and attributed GeoJSON imports."""

from datetime import date as Date
import json
import math
from pathlib import Path
import urllib.parse
import urllib.request
import uuid

from shapely.geometry import shape, box, mapping
from .sources import project, geographic
from .storage import atomic, now, file_hash, verify, read, digest

KINDS = {
    "closed_roads": ("EDW_RoadBasic_01", 1, "closed"),
    "mvum_roads": ("EDW_MVUM_02", 1, "Roads"),
    "mvum_trails": ("EDW_MVUM_02", 2, "Trails"),
}
CEILING = 250 * 1024**2


def validate_geojson(data, kind):
    if kind not in KINDS:
        raise ValueError("Supported imports: closed_roads, mvum_roads, mvum_trails")
    if data.get("type") != "FeatureCollection" or not isinstance(
        data.get("features"), list
    ):
        raise ValueError("Network source must be a WGS84 GeoJSON FeatureCollection")
    if data.get("exceededTransferLimit") or data.get("error"):
        raise ValueError("Provider truncated/error response; source not published")
    if len(data["features"]) > 2000:
        raise ValueError("Network import exceeds 2,000 features; narrow the corridor")
    if data.get("crs") and data["crs"].get("properties", {}).get("name") not in (
        "EPSG:4326",
        "urn:ogc:def:crs:OGC:1.3:CRS84",
        "urn:ogc:def:crs:EPSG::4326",
    ):
        raise ValueError("Network import CRS must explicitly be WGS84")
    points = 0
    for f in data["features"]:
        g = shape(f["geometry"])
        if (
            g.geom_type not in ("LineString", "MultiLineString")
            or g.is_empty
            or not g.is_valid
        ):
            raise ValueError(
                "Invalid network geometry; original retained, not published"
            )
        if not box(-108, 38, -106, 40).covers(g):
            raise ValueError("Network geometry outside bounded GMU54 source region")
        if not isinstance(f.get("properties"), dict):
            raise ValueError("Network attributes are required and preserved")
        props = {k.lower(): v for k, v in f["properties"].items()}
        if not any(
            props.get(k) is not None for k in ("objectid", "globalid", "rte_cn", "id")
        ):
            raise ValueError("Stable source feature identity required")
        parts = [g] if g.geom_type == "LineString" else g.geoms
        points += sum(len(p.coords) for p in parts)
    if points > 150000:
        raise ValueError("Network coordinate budget exceeded; narrow import")
    return data


def publish(paths, folder, kind, data, meta):
    validate_geojson(data, kind)
    path = folder / (kind + ".geojson")
    if path.exists():
        old = read(folder / (kind + "-manifest.json"))
        if old:
            verify(path, old["sha256"])
        if read(path) != data:
            raise ValueError(
                "Retained normalized source disagrees with verified original; restore exact bytes or import a new snapshot. It was not resealed."
            )
    else:
        atomic(path, data)
    spec = dict(
        meta,
        path=str(path),
        sha256=file_hash(path),
        bytes=path.stat().st_size,
        kind=kind,
    )
    atomic(folder / (kind + "-manifest.json"), spec)
    return spec


def import_snapshot(paths, body):
    if not body.get("provenance") or not body.get("source_date"):
        raise ValueError("Import requires source date and provenance")
    Date.fromisoformat(body["source_date"])
    paths.space(30 * 1024**2)
    ident = uuid.uuid4().hex
    folder = paths.artifact("imports", ident)
    folder.mkdir(parents=True)
    data = body["geojson"]
    kind = body["kind"]
    # Retain original supplied JSON before semantic validation for diagnosis.
    atomic(folder / "original.json", data)
    spec = publish(
        paths,
        folder,
        kind,
        data,
        dict(
            source_date=body["source_date"],
            provider=body["provenance"],
            retrieved_utc=now(),
            provenance=body["provenance"],
            scope="Owner import; completeness not established",
        ),
    )
    current = read(paths.state / "imports/active.json", {})
    current[kind] = spec
    atomic(paths.state / "imports/active.json", current)
    return spec


def prepare(
    paths,
    body,
    folder,
    progress,
    cancel,
    service_root="https://apps.fs.usda.gov/arcx/rest/services/EDW",
):
    lon, lat, radius = (
        body.get("longitude"),
        body.get("latitude"),
        body.get("radius_m", 5000),
    )
    if (
        not all(
            type(v) in (int, float) and math.isfinite(v) for v in (lon, lat, radius)
        )
        or not -108 < lon < -106
        or not 38 < lat < 40
        or not 1000 <= radius <= 6000
    ):
        raise ValueError("Choose a GMU54 center and 1–6 km radius")
    from shapely.geometry import Point

    bounds = geographic(project(Point(lon, lat)).buffer(radius)).bounds
    paths.space(160 * 1024**2)
    folder.mkdir(parents=True, exist_ok=True)
    ledger = read(
        folder / "transfer.json",
        dict(received_bytes=0, budget_bytes=CEILING, started_utc=now(), bounds=bounds),
    )

    def fetch(name, url, limit):
        cancel()
        path = folder / name
        old = read(folder / (name + ".manifest.json"))
        if path.exists() and old:
            verify(path, old["sha256"])
            return read(path)
        if ledger["received_bytes"] + limit > CEILING:
            raise ValueError(
                "250 MiB cumulative acquisition budget exhausted. Inspect transfer.json and retain partials."
            )
        progress(
            "source download",
            0,
            1,
            name + " (bounded " + str(limit // 1024) + " KiB piece)",
        )
        partial = folder / (name + "." + uuid.uuid4().hex + ".partial")
        request = urllib.request.Request(
            url, headers={"User-Agent": "TrailScout-local/1.0"}
        )
        total = 0
        with urllib.request.urlopen(request, timeout=25) as response, partial.open(
            "wb"
        ) as out:
            expected = response.headers.get("Content-Length")
            if expected and int(expected) > limit:
                raise ValueError("Provider response exceeds bounded piece allowance")
            while True:
                cancel()
                paths.space(1024**2)
                block = response.read(min(1024**2, limit - total + 1))
                if not block:
                    break
                total += len(block)
                ledger["received_bytes"] += len(block)
                atomic(folder / "transfer.json", ledger)
                if total > limit or ledger["received_bytes"] > CEILING:
                    raise ValueError(
                        "Acquisition byte ceiling exceeded; partial retained"
                    )
                out.write(block)
        if expected and total != int(expected):
            raise ValueError("Truncated provider response; partial retained")
        value = read(partial)
        if value.get("error") or value.get("exceededTransferLimit"):
            raise ValueError(
                "Provider error/truncation; partial retained: "
                + str(value.get("error"))
            )
        partial.replace(path)
        atomic(
            folder / (name + ".manifest.json"),
            dict(url=url, sha256=file_hash(path), bytes=total, retrieved_utc=now()),
        )
        return value

    def query(base, params):
        return base + "?" + urllib.parse.urlencode(params)

    published = {}
    for i, (kind, (service, layer, expected_name)) in enumerate(KINDS.items()):
        cancel()
        base = f"{service_root}/{service}/MapServer/{layer}"
        metadata = fetch(kind + "-metadata.json", query(base, dict(f="json")), 1024**2)
        if (
            expected_name.lower() not in metadata.get("name", "").lower()
            or metadata.get("geometryType") != "esriGeometryPolyline"
        ):
            raise ValueError(
                "Live service layer identity changed; inspect retained metadata before importing"
            )
        params = dict(
            where="1=1",
            geometry=",".join(str(x) for x in bounds),
            geometryType="esriGeometryEnvelope",
            inSR=4326,
            spatialRel="esriSpatialRelIntersects",
        )
        count = fetch(
            kind + "-count.json",
            query(base + "/query", dict(params, f="json", returnCountOnly="true")),
            1024**2,
        ).get("count")
        if type(count) is not int or count > min(
            2000, metadata.get("maxRecordCount", 2000)
        ):
            raise ValueError(
                "Official response exceeds one complete bounded page; narrow corridor explicitly"
            )
        data = fetch(
            kind + "-original.json",
            query(
                base + "/query", dict(params, f="geojson", outFields="*", outSR=4326)
            ),
            20 * 1024**2,
        )
        if len(data.get("features", [])) != count:
            raise ValueError(
                "Official count and response disagree; source not published"
            )
        spec = publish(
            paths,
            folder,
            kind,
            data,
            dict(
                provider="USFS EDW",
                source_date=now()[:10],
                retrieved_utc=now(),
                url=base,
                query_bounds_wgs84=bounds,
                complete_inventory_count=count,
                metadata_path=str(folder / (kind + "-metadata.json")),
                provenance="Live bounded official query; no emergency/foot closure certification",
            ),
        )
        published[kind] = spec
        progress(
            "source validation",
            i + 1,
            3,
            f"{kind}: {count} original attributed features validated",
        )
    cancel()
    current = read(paths.state / "imports/active.json", {})
    current.update(published)
    atomic(paths.state / "imports/active.json", current)
    return dict(published=published, ledger=ledger, bounds=bounds)
