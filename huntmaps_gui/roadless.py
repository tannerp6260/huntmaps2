"""Display-only distance from retained roads; no scoring or acquisition changes."""

from functools import lru_cache
import math

from shapely.geometry import box, shape, mapping
from shapely.ops import transform, unary_union
from glassing.transfer import project
from .config import STATE
from .storage import read_json
from . import scouting_network as network, unit_packs as packs


@lru_cache(maxsize=24)
def pack_lines(path, stamp, epsg):
    from pathlib import Path

    return tuple(
        transform(project(4326, epsg), g)
        for g in network.parse_lines(Path(path).read_bytes(), ".geojson", True)
    )


def distant_land(region, coverage, roads, distance):
    # Shrink the union, not each source tile: adjacent inventory tiles have no gap.
    # The inward margin prevents unknown roads beyond a query edge looking roadless.
    supported = (
        region.intersection(coverage.buffer(-distance))
        if distance
        else region.intersection(coverage)
    )
    if supported.is_empty:
        return supported, supported
    nearby = region.buffer(distance + 1)
    lines = [g.intersection(nearby) for g in roads if g.intersects(nearby)]
    # A circumscribed buffer keeps the polygon approximation conservative.
    radius = distance / math.cos(math.pi / 64) if distance else 0
    excluded = unary_union([g.buffer(radius, resolution=16) for g in lines])
    return supported.difference(excluded), supported


def overlay(body):
    bounds, distance = body.get("bounds"), body.get("distance_m")
    if (
        not isinstance(bounds, list)
        or len(bounds) != 4
        or any(type(n) not in (int, float) or not math.isfinite(n) for n in bounds)
        or not (-180 <= bounds[0] < bounds[2] <= 180)
        or not (-80 <= bounds[1] < bounds[3] <= 84)
        or (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) > 16
    ):
        raise ValueError("Zoom in to a local area to show road distance")
    if (
        type(distance) not in (int, float)
        or not math.isfinite(distance)
        or not 0 <= distance <= 16093.44
    ):
        raise ValueError("Choose a road distance between 0 and 10 miles")
    unit = body.get("unit_pack")
    epsg = (32600 if bounds[1] + bounds[3] >= 0 else 32700) + min(
        60, int(((bounds[0] + bounds[2]) / 2 + 180) / 6) + 1
    )
    if unit is not None:
        if not isinstance(unit, dict):
            raise ValueError("Choose a prepared hunting unit")
        folder, manifest = packs.load(
            unit.get("unit_id"), unit.get("version"), verify=False
        )
        epsg = manifest["epsg"]
    to_map, to_local = project(epsg, 4326), project(4326, epsg)
    region = transform(to_local, box(*bounds).segmentize(0.01))
    expanded = region.buffer(distance + 100)
    roads, coverages = [], []
    sources = 0
    if unit is not None:
        boundary = packs.asset_path(folder, manifest["boundary"])
        packs.verify_file(boundary, manifest["assets"][manifest["boundary"]])
        unit_area = unary_union(
            [shape(f["geometry"]) for f in read_json(boundary)["features"]]
        )
        region = region.intersection(transform(to_local, unit_area))
        for spec in manifest["networks"]["roads"]:
            coverage = transform(to_local, box(*spec["bounds"]).segmentize(0.01))
            if not coverage.intersects(expanded):
                continue
            path = packs.asset_path(folder, spec["path"])
            packs.verify_file(path, manifest["assets"][spec["path"]])
            roads.extend(pack_lines(str(path), packs.identity(path), epsg))
            coverages.append(coverage)
            sources += 1
    # Imported/cached roads also count inside a prepared unit. A display toggle
    # or a trail-only planning preference must never erase a known road here.
    for path in (STATE / "networks").glob("*/network.json"):
        record = read_json(path)
        if record["kind"] != "roads":
            continue
        if record.get("coverage"):
            coverage = transform(to_local, box(*record["coverage"]).segmentize(0.01))
            if not coverage.intersects(expanded):
                continue
        else:
            coverage = None
        record, lines = network.verified_network(record["id"], epsg)
        roads.extend(lines)
        if coverage is not None:
            coverages.append(coverage)
            sources += 1
    # Deduplicate overlapping inventories without dropping roads from outside the view.
    roads = list({g.wkb: g for g in roads if g.intersects(expanded)}.values())
    distant, supported = distant_land(region, unary_union(coverages), roads, distance)
    features = (
        []
        if distant.is_empty
        else [
            dict(
                type="Feature",
                properties={},
                geometry=mapping(transform(to_map, distant)),
            )
        ]
    )
    fraction = min(1, max(0, supported.area / region.area)) if region.area else 0
    return dict(
        type="FeatureCollection",
        features=features,
        distance_m=distance,
        coverage_fraction=fraction,
        road_sources=sources,
        status="unavailable" if supported.is_empty else "ready",
        message=(
            "Road-source coverage is insufficient here. Load roads covering a wider area or reduce the distance."
            if supported.is_empty
            else "Shaded land is farther from mapped roads; unshaded land may be near a road or outside source coverage."
        ),
    )
