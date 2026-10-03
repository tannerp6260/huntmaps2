"""Versioned independent kept-point scenarios, source seals, workers and exports."""

import hashlib
import json
import uuid
import time
import xml.etree.ElementTree as ET
import numpy as np
from osgeo import gdal
from shapely.geometry import shape, mapping, GeometryCollection, Point
from shapely.ops import transform, unary_union
from glassing.transfer import project
from .config import STATE
from .storage import write, read_json, locked
from .scouting_network import load_networks, checked_id
from .approach_search import Grid, solve, VERSION

NOTICE = "Provisional approach on a 20 m ground grid. Fences, deadfall, cliffs below grid scale, water crossings, snow, permissions and parking unmodeled. No walking time or safe/legal access certification."


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def point_snapshot(run, jobs=None):
    from .working_waypoints import DisplayRun
    from .manual_observers import records
    from .catalog import Run

    r = DisplayRun(run, jobs)
    annotations = read_json(STATE / "annotations" / f"{run}.json", {})
    manual = records(run)
    from .workflow import records

    decisions = records(run)["points"]
    result = {}
    for ident in dict.fromkeys([*r.points, *r.working]):
        p = r.candidate(ident)
        override = r.working.get(ident, {})
        annotation = override or manual.get(ident) or annotations.get(ident, {})
        if decisions.get(ident, {}).get(
            "shortlisted", annotation.get("status") == "keep"
        ):
            result[ident] = dict(
                id=ident,
                longitude=p["longitude"],
                latitude=p["latitude"],
                revision=override.get(
                    "revision", digest([p["longitude"], p["latitude"]])
                ),
                coverage=p.get("metrics", {}).get("raw_km2"),
            )
    # Uncalculated manual waypoints still have exact destination coordinates.
    for ident, p in manual.items():
        if (
            decisions.get(ident, {}).get("shortlisted", p["status"] == "keep")
            and ident not in result
        ):
            result[ident] = dict(
                id=ident,
                longitude=p["longitude"],
                latitude=p["latitude"],
                revision=digest([p["longitude"], p["latitude"]]),
                coverage=None,
            )
    return r, result


def geometry(value, polygon=True):
    if value.get("type") == "Feature":
        value = value["geometry"]
    if value.get("type") == "FeatureCollection":
        g = unary_union([shape(f["geometry"]) for f in value["features"]])
    else:
        g = shape(value)
    if (
        g.is_empty
        or not g.is_valid
        or (polygon and g.geom_type not in ("Polygon", "MultiPolygon"))
    ):
        raise ValueError("Draw/import a valid explicit travel polygon")
    if any(not np.isfinite(v) for v in g.bounds) or not (
        -180 <= g.bounds[0] <= g.bounds[2] <= 180
        and -90 <= g.bounds[1] <= g.bounds[3] <= 90
    ):
        raise ValueError("Travel geometry must be WGS84 longitude/latitude")
    return g


def create(run, body, jobs):
    r, points = point_snapshot(run, jobs)
    ids = body.get("ids", [])
    if (
        not ids
        or len(ids) > 250
        or len(set(ids)) != len(ids)
        or any(i not in points for i in ids)
    ):
        raise ValueError(
            "Keep at least one setup before planning its independent approach"
        )
    area = geometry(body["travel_area"])
    exclusions = [mapping(geometry(v)) for v in body.get("exclusions", [])]
    weights = body.get("weights", dict(slope=1, tree=1, shrub=1, gain=1))
    if set(weights) != {"slope", "tree", "shrub", "gain"} or any(
        not isinstance(v, (int, float)) or not np.isfinite(v) or not 0 <= v <= 5
        for v in weights.values()
    ):
        raise ValueError("Preference weights must be 0–5")
    maximum = body.get("maximum_slope_deg", 30)
    if (
        not isinstance(maximum, (int, float))
        or not np.isfinite(maximum)
        or not 0 < maximum <= 60
    ):
        raise ValueError("Maximum modeled slope must be >0–60 degrees")
    lines, sources = load_networks(
        body.get("network_ids", []),
        r.config["epsg"],
        body.get("kinds", ["roads", "trails"]),
    )
    if not lines:
        raise ValueError(
            "Load/select mapped roads or trails first; missing network coverage is unknown"
        )
    source_hashes = {
        str(p): r.hashes.get(str(p.resolve()))
        for p in [r.dem_path, r.analysis / "tree.tif", r.analysis / "shrub.tif"]
    }
    for p in source_hashes:
        r.validate(p)
    value = dict(
        version=1,
        id=uuid.uuid4().hex,
        run_id=run,
        algorithm=VERSION,
        created=time.time(),
        points=[points[i] for i in ids],
        travel_area=mapping(area),
        exclusions=exclusions,
        weights=weights,
        maximum_slope_deg=maximum,
        network_ids=body["network_ids"],
        kinds=body.get("kinds", ["roads", "trails"]),
        sources=sources,
        source_hashes=source_hashes,
        start=body.get("start"),
        pinned=body.get("pinned"),
        notice=NOTICE,
    )
    for key in ("start", "pinned"):
        if value[key] is not None:
            p = geometry(dict(type="Point", coordinates=value[key]), False)
            if not area.covers(p):
                raise ValueError(f"{key} must lie in the explicit travel area")
    write(STATE / "approaches" / value["id"] / "scenario.json", value)
    from .workflow import records, path

    with locked(path(run)):
        workflow = records(run)
        changed = False
        for cid in ids:
            entry = workflow["points"].get(cid)
            if entry and entry.get("approach"):
                entry.pop("approach", None)
                entry["confirmed"] = False
                changed = True
        if changed:
            workflow["revision"] += 1
            write(path(run), workflow)
    return value


def status(ident, jobs=None):
    folder = STATE / "approaches" / checked_id(ident)
    scenario = read_json(folder / "scenario.json")
    if not scenario:
        raise ValueError("Unknown approach scenario")
    if scenario.get("version") != 1 or scenario.get("algorithm") != VERSION:
        raise ValueError(
            "Unsupported saved approach version; prior definition retained"
        )
    stale = []
    try:
        r, points = point_snapshot(scenario["run_id"], jobs)
        for p in scenario["points"]:
            if p != points.get(p["id"]):
                stale.append("Waypoint changed/restored or no longer kept: " + p["id"])
        _, sources = load_networks(
            scenario["network_ids"], r.config["epsg"], scenario["kinds"]
        )
        if sources != scenario["sources"]:
            stale.append("Network sources changed")
        for path, expected in scenario["source_hashes"].items():
            r.validate(path)
            if (
                r.hashes.get(str(__import__("pathlib").Path(path).resolve()))
                != expected
            ):
                stale.append("Terrain source changed")
    except ValueError as error:
        stale.append(str(error))
    results = read_json(folder / "results.json")
    if results is not None:
        sealed = dict(results)
        expected = sealed.pop("sha256", None)
        if expected != digest(sealed) or results.get("scenario_sha256") != digest(
            scenario
        ):
            raise ValueError(
                "Approach results or scenario changed; preserve them and explicitly recompute"
            )
    return dict(
        scenario=scenario,
        stale=bool(stale),
        stale_reasons=stale,
        results=results,
    )


def compute(ident):
    from .catalog import Run

    s = read_json(STATE / "approaches" / checked_id(ident) / "scenario.json")
    current_status = status(ident)
    if current_status["stale"]:
        raise ValueError(
            "Scenario changed before computation; explicitly submit current inputs"
        )
    r = Run(s["run_id"])
    epsg = r.config["epsg"]
    xy = project(4326, epsg)
    ll = project(epsg, 4326)
    area = transform(xy, shape(s["travel_area"]))
    exclusions = (
        unary_union([transform(xy, shape(v)) for v in s["exclusions"]])
        if s["exclusions"]
        else GeometryCollection()
    )
    bounds = area.bounds
    width = int(np.ceil((bounds[2] - bounds[0]) / 20))
    height = int(np.ceil((bounds[3] - bounds[1]) / 20))
    if width * height > 3_000_000:
        raise ValueError("Travel grid exceeds 3 million cells; narrow travel area")

    def raster(path, cover=False):
        r.validate(path)
        ds = gdal.Warp(
            "",
            str(path),
            format="MEM",
            outputBounds=[
                bounds[0],
                bounds[3] - height * 20,
                bounds[0] + width * 20,
                bounds[3],
            ],
            width=width,
            height=height,
            dstSRS=f"EPSG:{epsg}",
            resampleAlg="near" if cover else "bilinear",
            dstNodata=-9999,
        )
        a = ds.ReadAsArray().astype(float)
        a[a == -9999] = np.nan
        if cover:
            a[(a < 0) | (a > 1)] = np.nan
        return a

    dem = raster(r.dem_path)
    tree = raster(r.analysis / "tree.tif", True)
    shrub = raster(r.analysis / "shrub.tif", True)
    grid = Grid(
        dem,
        tree,
        shrub,
        (bounds[0], bounds[3]),
        area,
        exclusions,
        s["maximum_slope_deg"],
    )
    lines, sources = load_networks(s["network_ids"], epsg, s["kinds"])
    if sources != s["sources"]:
        raise ValueError("Network changed; create/review a new scenario")
    # Clip to the supplied search domain, retaining exact shared vertices only.
    clipped = []
    for l in lines:
        g = l.intersection(grid.domain)
        if g.geom_type == "LineString" and not g.is_empty:
            clipped.append(g)
        elif g.geom_type in ("MultiLineString", "GeometryCollection"):
            clipped.extend(p for p in g.geoms if p.geom_type == "LineString")
    start = xy(*s["start"]) if s["start"] else None
    pinned = xy(*s["pinned"]) if s["pinned"] else None
    results = []
    for p in s["points"]:
        print(
            "STAGE Planning independent provisional approach for " + p["id"], flush=True
        )
        result = solve(
            grid,
            clipped,
            xy(p["longitude"], p["latitude"]),
            s["weights"],
            start,
            pinned,
        )
        for a in result["alternatives"]:
            pinned_endpoint = pinned is not None and tuple(a["departure"]) == tuple(
                pinned
            )
            a["departure"] = ll(*a["departure"])
            a["mapped"] = [ll(*v) for v in a["mapped"]]
            a["offtrail"] = [ll(*v) for v in a["offtrail"]]
            if start is not None:
                a["mapped"][0] = tuple(s["start"])
            if pinned_endpoint:
                a["departure"] = tuple(s["pinned"])
                a["mapped"][-1] = tuple(s["pinned"])
                a["offtrail"][0] = tuple(s["pinned"])
            # Exact input endpoints retained, with checked projected connectors.
            a["offtrail"][-1] = (p["longitude"], p["latitude"])
        results.append(dict(point=p, **result))
    output = dict(
        version=1,
        algorithm=VERSION,
        results=results,
        notice=NOTICE,
        scenario_sha256=digest(s),
    )
    output["sha256"] = digest(output)
    with locked(STATE / "maintenance"):
        write(STATE / "approaches" / ident / "results.json", output)


def export(ident, index, alternative, fmt, jobs):
    v = status(ident, jobs)
    if v["stale"]:
        raise ValueError(
            "Scenario stale; explicitly recompute with current inputs before export"
        )
    if not v["results"]:
        raise ValueError("Approach job has not completed")
    result = v["results"]["results"][index]
    a = result["alternatives"][alternative]
    p = result["point"]
    if fmt == "geojson":
        features = []
        for mode in ("mapped", "offtrail"):
            if len(a[mode]) > 1:
                features.append(
                    dict(
                        type="Feature",
                        geometry=dict(type="LineString", coordinates=a[mode]),
                        properties=dict(kind=mode, notice=NOTICE),
                    )
                )
        features.append(
            dict(
                type="Feature",
                geometry=dict(
                    type="Point", coordinates=[p["longitude"], p["latitude"]]
                ),
                properties=dict(id=p["id"], kind="unchanged destination waypoint"),
            )
        )
        return json.dumps(
            dict(
                type="FeatureCollection",
                features=features,
                properties=dict(
                    notice=NOTICE,
                    algorithm=VERSION,
                    metrics={
                        k: v for k, v in a.items() if k not in ("mapped", "offtrail")
                    },
                ),
            )
        ).encode()
    if fmt != "gpx":
        raise ValueError("Choose GeoJSON or GPX provisional approach export")
    root = ET.Element(
        "gpx",
        version="1.1",
        creator="HuntMaps2 provisional approach",
        xmlns="http://www.topografix.com/GPX/1/1",
    )
    waypoint = ET.SubElement(
        root, "wpt", lat=str(p["latitude"]), lon=str(p["longitude"])
    )
    ET.SubElement(waypoint, "name").text = p["id"]
    for mode in ("mapped", "offtrail"):
        track = ET.SubElement(root, "trk")
        ET.SubElement(track, "name").text = "Provisional approach · " + mode
        ET.SubElement(track, "desc").text = NOTICE
        segment = ET.SubElement(track, "trkseg")
        for lon, lat in a[mode]:
            ET.SubElement(segment, "trkpt", lon=str(lon), lat=str(lat))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
