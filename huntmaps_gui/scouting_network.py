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


def parse_lines(data, extension, allow_empty=False):
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
    if not lines and not allow_empty:
        raise ValueError("No road/trail lines found; missing coverage remains unknown")
    if sum(len(l.coords) for l in lines) > 100000:
        raise ValueError("Network too large; narrow the import")
    return lines


def save_network(data, extension, kind, source, date="unknown", coverage=None):
    if kind not in SERVICES:
        raise ValueError("Choose roads or trails")
    if len(data) > LIMIT:
        raise ValueError("Network import exceeds 10 MB")
    lines = parse_lines(data, extension, allow_empty=coverage is not None)
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
        actual = [
            mapping(g)
            for g in parse_lines(
                raw, original.suffix, allow_empty=v.get("coverage") is not None
            )
        ]
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
    if type(budget_mb) is not int or budget_mb < 1:
        raise ValueError("Download allowance must be a positive integer MB value")
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
    cached = covering_networks(bounds)
    if cached:
        value["cached_network_ids"] = [n["id"] for n in cached]
        value["estimated_bytes"] = 0
        value["note"] = (
            "Reuse checksum-verified cached roads/trails covering these bounds; no network download."
        )
    write(STATE / "network-plans" / f"{ident}.json", value)
    return value


def remaining_estimate(ident):
    p = read_json(STATE / "network-plans" / f"{checked_id(ident)}.json")
    if not p:
        raise ValueError("Unknown network plan")
    if p.get("cached_network_ids"):
        return 0, 0
    cached_bytes = 0
    missing = 0
    partials = STATE / "network-plans" / f"{ident}-responses"
    for item in p["items"]:
        path = partials / (item["kind"] + ".json")
        seal = read_json(path.with_suffix(".seal"), {})
        if (
            path.exists()
            and seal.get("url", "").startswith(item["url"] + "/query?")
            and seal.get("sha256") == hashlib.sha256(path.read_bytes()).hexdigest()
        ):
            cached_bytes += path.stat().st_size
        else:
            missing += LIMIT
    return missing, cached_bytes


def acquire(ident, remaining_bytes):
    import os
    from .storage import locked

    ledger = os.environ.get("HUNTMAPS_TRANSFER_LEDGER")
    owned = not ledger
    if owned:
        ledger = str(STATE / "network-plans" / f"{checked_id(ident)}-transfer.json")
        with locked(ledger):
            record = read_json(ledger, dict(received_bytes=0))
            reviewed = read_json(STATE / "network-plans" / f"{checked_id(ident)}.json")
            if not reviewed:
                raise ValueError("Review a network download plan first")
            record["ceiling_bytes"] = min(
                remaining_bytes, reviewed["max_download_mb"] * 1000000
            )
            write(ledger, record)
        os.environ["HUNTMAPS_TRANSFER_LEDGER"] = ledger
    try:
        return _acquire(ident, remaining_bytes)
    finally:
        if owned:
            os.environ.pop("HUNTMAPS_TRANSFER_LEDGER", None)


def _acquire(ident, remaining_bytes):
    p = read_json(STATE / "network-plans" / f"{checked_id(ident)}.json")
    if not p:
        raise ValueError("Review a network download plan first")
    cap = min(p["max_download_mb"] * 1000000, remaining_bytes)

    if p.get("cached_network_ids"):
        records = [
            read_json(STATE / "networks" / checked_id(i) / "network.json")
            for i in p["cached_network_ids"]
        ]
        load_networks(p["cached_network_ids"], 4326)
        write(
            STATE / "network-plans" / f"{ident}-result.json",
            dict(networks=records, downloaded_bytes=0),
        )
        return records
    from .downloads import check_space
    from .progress import start_download, received, flush_download, progress_path, emit

    progress_file = progress_path()
    if not progress_file or not progress_file.exists():
        start_download(p["estimated_bytes"])
    check_space(STATE, 3 * p["estimated_bytes"])
    import os

    ledger = os.environ["HUNTMAPS_TRANSFER_LEDGER"]
    partials = STATE / "network-plans" / f"{ident}-responses"
    partials.mkdir(parents=True, exist_ok=True)

    pending_estimate, _ = remaining_estimate(ident)
    accounting = read_json(ledger)
    if pending_estimate > min(
        cap, accounting["ceiling_bytes"] - accounting["received_bytes"]
    ):
        raise ValueError(
            "Network plan exceeds remaining cumulative download budget; review a larger allowance"
        )
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
        cache = partials / (item["kind"] + ".json")
        seal = read_json(cache.with_suffix(".seal"), {})
        if (
            cache.is_file()
            and seal.get("url") == url
            and hashlib.sha256(cache.read_bytes()).hexdigest() == seal.get("sha256")
        ):
            data = cache.read_bytes()
        else:
            with urllib.request.urlopen(url, timeout=30) as response:
                chunks = []
                size = 0
                declared = (
                    response.headers.get("Content-Length")
                    if hasattr(response, "headers")
                    else None
                )
                declared = int(declared) if declared is not None else None
                if declared is not None and (
                    declared > LIMIT
                    or declared
                    > min(
                        cap - used,
                        read_json(ledger)["ceiling_bytes"]
                        - read_json(ledger)["received_bytes"],
                    )
                ):
                    raise ValueError(
                        "Network response exceeds remaining cumulative download budget"
                    )
                while True:
                    check_space(STATE, 1024 * 1024)
                    accounting = read_json(ledger)
                    remaining = min(
                        cap - used - size,
                        accounting["ceiling_bytes"] - accounting["received_bytes"],
                        LIMIT - size,
                    )
                    if remaining <= 0:
                        raise ValueError(
                            "Cumulative network allowance exhausted; review a larger allowance or narrow the query"
                        )
                    block = response.read(min(1024 * 1024, remaining))
                    if not block:
                        break
                    received(len(block), url)
                    chunks.append(block)
                    size += len(block)
                    if declared is not None and size == declared:
                        break
                data = b"".join(chunks)
                flush_download()
            used += len(data)
        value = json.loads(data)
        if (
            value.get("error")
            or value.get("exceededTransferLimit")
            or "features" not in value
        ):
            raise ValueError(
                "USFS query failed or truncated; narrow query or import checked lines"
            )
        if not cache.exists() or seal.get("url") != url or cache.read_bytes() != data:
            temp = cache.with_suffix(".part")
            temp.write_bytes(data)
            temp.replace(cache)
            write(
                cache.with_suffix(".seal"),
                dict(url=url, sha256=hashlib.sha256(data).hexdigest()),
            )
        responses.append((item, data, url))
    emit("processing", "Validating mapped roads/trails", force=True)
    results = [
        save_network(data, ".geojson", item["kind"], url, coverage=p["bounds"])
        for item, data, url in responses
    ]
    write(
        STATE / "network-plans" / f"{ident}-result.json",
        dict(networks=results, downloaded_bytes=used),
    )
    emit(
        "processing",
        "Mapped roads/trails ready",
        len(results),
        len(results),
        force=True,
    )
    return results


def display_network(value):
    """Read-time display enrichment; never mutate the sealed analysis inventory."""
    folder = STATE / "networks" / checked_id(value["id"])
    original = next(folder.glob("original.*"))
    raw = original.read_bytes()
    if hashlib.sha256(raw).hexdigest() != value["sha256"]:
        raise ValueError("Network source changed; re-import to display it")
    geometries = [
        mapping(g)
        for g in parse_lines(
            raw, original.suffix, allow_empty=value.get("coverage") is not None
        )
    ]
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


def covering_networks(bounds):
    """Only complete, checksum-verified inventories whose recorded query contains the AOI."""
    choices = {kind: [] for kind in SERVICES}
    for path in (STATE / "networks").glob("*/network.json"):
        value = read_json(path)
        coverage = value.get("coverage")
        if (
            value.get("kind") not in choices
            or not isinstance(coverage, list)
            or len(coverage) != 4
        ):
            continue
        if not (
            coverage[0] <= bounds[0]
            and coverage[1] <= bounds[1]
            and coverage[2] >= bounds[2]
            and coverage[3] >= bounds[3]
        ):
            continue
        try:
            load_networks([value["id"]], 4326)
        except (ValueError, OSError, StopIteration):
            continue
        choices[value["kind"]].append(value)
    if not all(choices.values()):
        return []
    return [
        sorted(
            choices[kind], key=lambda v: (v["retrieved_utc"], v["id"]), reverse=True
        )[0]
        for kind in SERVICES
    ]


def sampling_networks(settings, inventory=None):
    """Resolve explicitly selected sources, or this reviewed plan's network inventory."""
    effective = dict(settings)
    if not effective["network_ids"] and inventory:
        effective["network_ids"] = [
            n["id"] for n in inventory["networks"] if n["kind"] in effective["kinds"]
        ]
    if not effective["network_ids"]:
        raise ValueError(
            "Select mapped network sources for observer sampling, or include a reviewed network acquisition"
        )
    lines, sources = load_networks(effective["network_ids"], 4326, effective["kinds"])
    if not lines:
        raise ValueError(
            "Selected mapped inventories contain no road/trail lines; choose available sources or import checked lines"
        )
    return effective, sources
