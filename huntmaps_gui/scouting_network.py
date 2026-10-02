"""Bounded line imports and explicitly reviewed single-provider USFS acquisition."""

import hashlib
import json
import uuid
import zipfile
import io
import xml.etree.ElementTree as ET
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from shapely.geometry import shape, mapping, LineString
from shapely.ops import transform
from glassing.transfer import project
from .config import STATE
from .storage import read_json, write, locked

LIMIT = 10_000_000
SERVICES = dict(
    roads="EDW_RoadBasic_01/MapServer/0", trails="EDW_TrailNFSPublish_01/MapServer/0"
)


def checked_id(ident):
    if len(ident) != 32 or any(c not in "0123456789abcdef" for c in ident):
        raise ValueError("Unknown network/scenario identifier")
    return ident


def parse_lines(data, extension):
    if extension in (".json", ".geojson"):
        value = json.loads(data)
        features = (
            value.get("features", [])
            if value.get("type") == "FeatureCollection"
            else [value]
        )
        geometries = [
            shape(f["geometry"] if f.get("type") == "Feature" else f) for f in features
        ]
    else:
        if extension == ".kmz":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                files = [i for i in z.infolist() if i.filename.lower().endswith(".kml")]
                if len(files) != 1 or files[0].file_size > LIMIT:
                    raise ValueError("KMZ must contain one bounded KML file")
                data = z.read(files[0])
        root = ET.fromstring(data)
        geometries = []
        if extension == ".gpx":
            for segment in root.iter():
                if segment.tag.split("}")[-1] not in ("trkseg", "rte"):
                    continue
                pts = [
                    (float(p.attrib["lon"]), float(p.attrib["lat"]))
                    for p in segment
                    if p.tag.split("}")[-1] in ("trkpt", "rtept")
                ]
                if len(pts) > 1:
                    geometries.append(LineString(pts))
        else:
            for line in root.iter():
                if line.tag.split("}")[-1] != "LineString":
                    continue
                coord = next(
                    (n.text for n in line if n.tag.split("}")[-1] == "coordinates"), ""
                )
                geometries.append(
                    LineString(
                        [tuple(map(float, p.split(",")[:2])) for p in coord.split()]
                    )
                )
    lines = []
    for geometry in geometries:
        if geometry.geom_type not in ("LineString", "MultiLineString"):
            raise ValueError("Network import contains non-line geometry")
        for line in (
            [geometry] if geometry.geom_type == "LineString" else geometry.geoms
        ):
            if not line.is_valid or line.is_empty:
                raise ValueError("Invalid network line")
            if any(
                not (-180 <= x <= 180 and -90 <= y <= 90) for x, y, *_ in line.coords
            ):
                raise ValueError("Network imports must use WGS84 longitude/latitude")
            lines.append(LineString([(x, y) for x, y, *_ in line.coords]))
    if not lines:
        raise ValueError("No road/trail lines found; missing coverage remains unknown")
    if sum(len(l.coords) for l in lines) > 100000:
        raise ValueError("Network too large; narrow the import")
    return lines


def save_network(data, extension, kind, source, date="unknown", coverage=None):
    if kind not in SERVICES:
        raise ValueError("Choose roads or trails")
    if len(data) > LIMIT:
        raise ValueError("Network import exceeds 10 MB")
    lines = parse_lines(data, extension)
    ident = uuid.uuid4().hex
    folder = STATE / "networks" / ident
    with locked(STATE / "maintenance"):
        folder.mkdir(parents=True)
        (folder / ("original" + extension)).write_bytes(data)
        value = dict(
            version=1,
            id=ident,
            kind=kind,
            source=source,
            source_date=date,
            retrieved_utc=datetime.now(timezone.utc).isoformat(),
            sha256=hashlib.sha256(data).hexdigest(),
            coverage=coverage,
            coverage_note="Mapped inventory only; absence of lines is not evidence of no access",
            lines=[mapping(l) for l in lines],
        )
        write(folder / "network.json", value)
        return value


def load_networks(ids, epsg, kinds=("roads", "trails")):
    lines, sources = [], []
    for ident in ids:
        folder = STATE / "networks" / checked_id(ident)
        v = read_json(folder / "network.json")
        if not v:
            raise ValueError("Network unavailable; import/acquire it again")
        original = next(folder.glob("original.*"))
        raw = original.read_bytes()
        if hashlib.sha256(raw).hexdigest() != v["sha256"]:
            raise ValueError("Network source changed; prior scenarios preserved")
        actual = [mapping(g) for g in parse_lines(raw, original.suffix)]
        if v.get("version") != 1 or json.dumps(actual, sort_keys=True) != json.dumps(
            v["lines"], sort_keys=True
        ):
            raise ValueError(
                "Network derived geometry changed; preserve original and re-import"
            )
        sources.append(
            {
                k: v[k]
                for k in ("id", "sha256", "source", "source_date", "kind", "coverage")
            }
        )
        if v["kind"] in kinds:
            lines.extend(transform(project(4326, epsg), shape(g)) for g in v["lines"])
    return lines, sources


def network_plan(bounds, budget_mb):
    if len(bounds) != 4 or not all(isinstance(v, (float, int)) for v in bounds):
        raise ValueError("Use WGS84 query bounds")
    west, south, east, north = bounds
    if (
        not (-180 <= west < east <= 180 and -90 <= south < north <= 90)
        or (east - west) * (north - south) > 0.05
    ):
        raise ValueError(
            "USFS query too large; narrow the travel area (maximum 0.05 square degrees)"
        )
    if not 1 <= budget_mb <= 1900:
        raise ValueError("Download cap must be 1–1900 MB")
    ident = uuid.uuid4().hex
    value = dict(
        version=1,
        id=ident,
        bounds=bounds,
        max_download_mb=budget_mb,
        estimated_bytes=2 * LIMIT,
        provider="USFS EDW roads/trails",
        source_date="unknown; retain source attributes",
        note="20 MB maximum combined network responses; shares the reviewed analysis cap. No provider fallback.",
        items=[
            dict(kind=k, url="https://apps.fs.usda.gov/arcx/rest/services/EDW/" + v)
            for k, v in SERVICES.items()
        ],
    )
    write(STATE / "network-plans" / f"{ident}.json", value)
    return value


def acquire(ident, remaining_bytes):
    p = read_json(STATE / "network-plans" / f"{checked_id(ident)}.json")
    if not p:
        raise ValueError("Review a network download plan first")
    cap = min(p["max_download_mb"] * 1000000, remaining_bytes)
    if p["estimated_bytes"] > cap:
        raise ValueError("Network plan exceeds remaining shared download budget")
    responses = []
    used = 0
    for item in p["items"]:
        params = dict(
            f="geojson",
            where="1=1",
            geometry=",".join(map(str, p["bounds"])),
            geometryType="esriGeometryEnvelope",
            inSR=4326,
            outSR=4326,
            spatialRel="esriSpatialRelIntersects",
            outFields="*",
        )
        url = item["url"] + "/query?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(min(LIMIT, cap - used) + 1)
        used += len(data)
        if len(data) > LIMIT or used > cap:
            raise ValueError("Network response exceeds approved budget; no fallback")
        value = json.loads(data)
        if (
            value.get("error")
            or value.get("exceededTransferLimit")
            or "features" not in value
        ):
            raise ValueError(
                "USFS query failed or truncated; narrow query or import checked lines"
            )
        responses.append((item, data, url))
    results = [
        save_network(data, ".geojson", item["kind"], url, coverage=p["bounds"])
        for item, data, url in responses
    ]
    write(
        STATE / "network-plans" / f"{ident}-result.json",
        dict(networks=results, downloaded_bytes=used),
    )
    return results


def display_network(value):
    """Read-time display enrichment; never mutate the sealed analysis inventory."""
    folder = STATE / "networks" / checked_id(value["id"])
    original = next(folder.glob("original.*"))
    raw = original.read_bytes()
    if hashlib.sha256(raw).hexdigest() != value["sha256"]:
        raise ValueError("Network source changed; re-import to display it")
    geometries = [mapping(g) for g in parse_lines(raw, original.suffix)]
    if json.dumps(geometries, sort_keys=True) != json.dumps(
        value["lines"], sort_keys=True
    ):
        raise ValueError("Network derived geometry changed")
    properties = []
    if original.suffix in (".geojson", ".json"):
        document = json.loads(raw)
        features = (
            document.get("features", [])
            if document.get("type") == "FeatureCollection"
            else [document]
        )
        for feature in features:
            geometry = (
                feature.get("geometry") if feature.get("type") == "Feature" else feature
            )
            count = (
                len(geometry["coordinates"])
                if geometry["type"] == "MultiLineString"
                else 1
            )
            properties.extend([feature.get("properties") or {}] * count)
    else:
        if original.suffix == ".kmz":
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                raw = archive.read(
                    next(n for n in archive.namelist() if n.lower().endswith(".kml"))
                )
        root = ET.fromstring(raw)
        local = lambda element: element.tag.split("}")[-1]
        for parent in root.iter():
            if local(parent) not in ("Placemark", "trk", "rte"):
                continue
            attrs = {}
            for element in parent:
                if local(element) in ("name", "type", "desc"):
                    attrs[local(element)] = element.text or ""
            for element in parent.iter():
                if local(element) in ("Data", "SimpleData") and element.get("name"):
                    attrs[element.get("name")] = (
                        element.text
                        if local(element) == "SimpleData"
                        else next((v.text for v in element if local(v) == "value"), "")
                    )
            count = sum(
                local(element) in ("LineString", "trkseg") for element in parent.iter()
            )
            if local(parent) == "rte":
                count = 1
            properties.extend([attrs] * count)
    features = []
    for index, geometry in enumerate(geometries):
        attrs = {
            str(k).lower(): v
            for k, v in (properties[index] if index < len(properties) else {}).items()
        }
        get = lambda *keys: next(
            (str(attrs[k]) for k in keys if attrs.get(k) is not None), "unknown"
        )
        surface = get("surface_type", "surfacetype", "trail_surface", "surface")
        code = surface.upper().split(" - ")[0]
        subtype = "unknown"
        if value["kind"] == "roads":
            if code in ("AC", "BST", "PCC", "ASPHALT", "CONCRETE", "PAVED"):
                subtype = "paved"
            elif code in ("AGG", "GRAVEL", "AGGREGATE"):
                subtype = "gravel"
            elif code in ("NAT", "NATIVE MATERIAL", "DIRT", "EARTH"):
                subtype = "natural"
            elif surface != "unknown":
                subtype = "other"
        else:
            motorized = get("terra_motorized", "motorized").upper()
            if motorized in ("Y", "YES", "TRUE"):
                subtype = "motorized"
            elif motorized in ("N", "NO", "FALSE"):
                subtype = "nonmotorized"
        features.append(
            dict(
                type="Feature",
                geometry=geometry,
                properties=dict(
                    kind=value["kind"],
                    subtype=subtype,
                    name=get("name", "trail_name"),
                    number=get("id", "trail_no", "field_id"),
                    surface=surface,
                    maintenance=get("oper_maint_level", "operationalmaintlevel"),
                    classification=get(
                        "trail_class", "trailclass", "trail_type", "type"
                    ),
                    source=value["source"],
                    source_date=value["source_date"],
                    retrieved_utc=value["retrieved_utc"],
                ),
            )
        )
    return dict(value, display_features=features)
