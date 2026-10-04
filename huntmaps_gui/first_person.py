"""Display-only Soap Creek pilot. No historical writes or visibility-score changes."""

import hashlib
import json
import math
import re
import uuid
from functools import lru_cache
from pathlib import Path
import numpy as np
from osgeo import gdal
from .catalog import ROOT, STATE, Run, read, check_hash
from .jobs import write

PILOT = ("A0075", "V010", "V008", "A0031")
RUN = "soap-creek-decision-review-v2"
from .config import ConfigPath

HOME = ConfigPath("state_dir", "first-person")
VERSION = 6
CURVATURE = 6 / 7
EARTH = 6378137.0
LIMIT = 10_000_000


def stage(text):
    print("STAGE " + text, flush=True)


def candidate(ident, cid):
    return scene_run(ident).candidate(cid)


def scene_run(ident):
    from .working_waypoints import DisplayRun
    from .manual_observers import records

    r = DisplayRun(ident, None)
    r.points = dict(r.base.points)
    for cid in dict.fromkeys([*records(ident), *r.working]):
        p = r.candidate(cid)
        x, y = (
            r.xy(p["longitude"], p["latitude"])
            if hasattr(r, "xy")
            else __import__("pyproj")
            .Transformer.from_crs(4326, r.config["epsg"], always_xy=True)
            .transform(p["longitude"], p["latitude"])
        )
        r.points[cid] = dict(p, x=x, y=y)
    return r


def ready_path(run, cid, validated=False):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", cid):
        raise ValueError("Invalid waypoint ID")
    from .catalog import Run

    if not validated:
        Run(run)
    return HOME / "ready" / run / (cid + ".json")


def plan(ident):
    if not re.fullmatch(r"[a-f0-9]{32}", ident):
        raise ValueError("Unknown first-person preparation plan")
    p = read(HOME / "plans" / (ident + ".json"))
    if not p:
        raise ValueError("Unknown first-person preparation plan")
    return p


def new_plan(run=RUN, ids=None, fidelity="lidar", acquisition=None):
    ids = list(PILOT) if ids is None else ids
    if not isinstance(ids, list) or any(not isinstance(cid, str) for cid in ids):
        raise ValueError("Supply a list of waypoint IDs")
    if not ids or len(ids) > 250 or len(set(ids)) != len(ids):
        raise ValueError("Choose distinct completed-run waypoints")
    if fidelity not in ("lidar", "terrain"):
        raise ValueError("Choose lidar or terrain fidelity")
    from .workflow import point

    snapshots = {cid: point(run, cid) for cid in ids}
    ident = uuid.uuid4().hex
    write(
        HOME / "plans" / (ident + ".json"),
        dict(
            id=ident,
            kind="first-person",
            prepared=False,
            radius_m=300,
            download_cap_bytes=LIMIT,
            candidates=ids,
            run_id=run,
            snapshots=snapshots,
            fidelity=fidelity,
            acquisition=acquisition,
            version=VERSION,
        ),
    )
    return ident


def verify_file(path, expected):
    st = path.stat()
    check_hash(str(path), st.st_mtime_ns, st.st_size, expected)


def scene(ident, cid, run_data=None, orientation=True):
    p = run_data.candidate(cid) if run_data is not None else candidate(ident, cid)
    pointer = read(ready_path(ident, cid, validated=run_data is not None))
    legacy = pointer is None and ident == RUN and cid in PILOT
    if legacy:
        historical = (
            (run_data.base if hasattr(run_data, "working") else run_data)
            if run_data is not None
            else Run(ident)
        )
        p = historical.candidate(cid)
        pointer = read(HOME / "ready" / (cid + ".json"))
    if pointer is None and ident == RUN and cid in PILOT:
        pointer = read(ROOT / ".gui/first-person/ready" / (cid + ".json"))
    if not pointer:
        return dict(
            status="unprepared",
            candidate=cid,
            observer=p,
            reason="Review a scene source plan, or prepare a terrain-only view from the existing DEM.",
        )
    folder = locate_bundle(pointer["key"])
    meta = read(folder / "scene.json")
    if (
        not meta
        or meta.get("version") not in (5, VERSION)
        or meta["observer"]["longitude"] != p["longitude"]
        or meta["observer"]["latitude"] != p["latitude"]
    ):
        raise ValueError("First-person bundle is stale. Prepare the pilot again.")
    signature = meta.get("scene_signature")
    if signature:
        r = run_data if run_data is not None else scene_run(ident)
        r.validate(r.dem_path)
        from glassing.acquire import digest

        if signature.get("imagery") is not None and signature["imagery"] != sorted(
            r.hashes[str(r.path(i["path"]))] for i in r.images
        ):
            raise ValueError("Scene imagery changed; review a new scene plan")
        if (
            signature.get("run_id") != ident
            or signature.get("waypoint_revision") != p.get("working_revision")
            or signature.get("baseline") != r.hashes[str(r.dem_path)]
        ):
            raise ValueError("Scene inputs changed; review a new scene plan")
    for name, h in meta["hashes"].items():
        verify_file(asset_path(folder, meta, name), h)
    if not orientation:
        return meta
    # Orientation only: face the first saved inspection sector, not a new score.
    r = scene_run(ident) if not legacy else Run(ident)
    sectors = (
        r.sectors(cid)
        if cid in (r.points if legacy else r.base.points)
        else {"features": []}
    )
    sectors = sectors.get("features", [])
    bearing = 0.0
    if sectors:
        from shapely.geometry import shape
        from pyproj import Transformer

        centre = shape(sectors[0]["geometry"]).centroid
        x, y = Transformer.from_crs(4326, r.config["epsg"], always_xy=True).transform(
            centre.x, centre.y
        )
        observer = r.points[cid]
        bearing = (
            math.degrees(math.atan2(x - observer["x"], y - observer["y"])) + 360
        ) % 360
    from . import vegetation_screen as veg

    if meta.get("vegetation"):
        meta = dict(
            meta,
            vegetation=dict(meta["vegetation"], default_radius_m=veg.DEFAULT_RADIUS),
        )
    return dict(
        meta,
        initial_bearing_deg=bearing,
        initial_facing_note="Initial facing is the centre of the first saved inspection sector, for orientation only; sectors may include hidden terrain.",
    )


def bundle(cid, ident=RUN, run_data=None):
    meta = scene(ident, cid, run_data=run_data, orientation=False)
    if meta["status"] == "unprepared":
        raise ValueError("Prepare this setup first")
    return locate_bundle(meta["key"]), meta


def locate_bundle(key):
    if not re.fullmatch(r"[a-f0-9]{32}", key):
        raise ValueError("Invalid scene bundle key")
    local = HOME / "bundles" / key
    return local if local.exists() else ROOT / ".gui/first-person/bundles" / key


def asset_path(folder, meta, name):
    if (meta.get("hashes") is not None and name not in meta["hashes"]) or Path(
        name
    ).name != name:
        raise ValueError("Unknown scene asset")
    base = meta.get("asset_bundles", {}).get(name)
    if base:
        if not re.fullmatch(r"[a-f0-9]{32}", base):
            raise ValueError("Invalid referenced bundle")
        return locate_bundle(base) / name
    return folder / name


@lru_cache(maxsize=12)
def grid(path, mtime):
    with np.load(path) as z:
        return z["heights"], float(z["res"]), float(z["x0"]), float(z["y0"])


def sample(heights, res, x0, y0, x, y):
    """Same fixed diagonal triangles as render mesh; exact within grid triangle."""
    u = (x - x0) / res
    v = (y0 - y) / res
    c = np.floor(u).astype(int)
    r = np.floor(v).astype(int)
    good = (
        (u >= 0) & (v >= 0) & (u <= heights.shape[1] - 1) & (v <= heights.shape[0] - 1)
    )
    rr = np.clip(r, 0, heights.shape[0] - 2)
    cc = np.clip(c, 0, heights.shape[1] - 2)
    fx = u - cc
    fy = v - rr
    a = heights[rr, cc]
    b = heights[rr, cc + 1]
    d = heights[rr + 1, cc]
    e = heights[rr + 1, cc + 1]
    # a,b,e for fy<=fx; a,e,d otherwise. No fallback through missing corners.
    top = fy <= fx
    z = np.where(
        top,
        a * (1 - fx) + b * (fx - fy) + e * fy,
        a * (1 - fy) + e * fx + d * (fy - fx),
    )
    valid = (
        good
        & np.isfinite(a)
        & np.isfinite(e)
        & np.where(top, np.isfinite(b), np.isfinite(d))
    )
    return np.where(valid, z, np.nan)


def profile_grid(
    heights, res, x0, y0, target_x, target_y, eye, target_height, curvature=CURVATURE
):
    distance = math.hypot(target_x, target_y)
    if distance < 0.1:
        raise ValueError("Choose an inspection target away from the observer")
    # Include all grid and diagonal crossings, and interior samples at <= quarter cell.
    ts = list(np.linspace(0, 1, max(2, math.ceil(distance / (res / 4))) + 1))
    for origin, delta in [
        ((-x0) / res, target_x / res),
        (y0 / res, -target_y / res),
        ((-x0 - y0) / res, (target_x + target_y) / res),
    ]:
        if abs(delta) > 1e-12:
            lo, hi = sorted([origin, origin + delta])
            ts.extend(
                (k - origin) / delta for k in range(math.ceil(lo), math.floor(hi) + 1)
            )
    t = np.unique(np.clip(ts, 0, 1))
    x = t * target_x
    y = t * target_y
    z = sample(heights, res, x0, y0, x, y)
    drop = curvature * (distance * t) ** 2 / (2 * EARTH)
    ground = z - drop
    start = z[0] + eye
    end = z[-1] + target_height - curvature * distance**2 / (2 * EARTH)
    line = start * (1 - t) + end * t
    finite = np.isfinite(ground) & np.isfinite(line)
    interior = (t > 1e-8) & (t < 1 - 1e-8)
    clearance = line - ground
    hits = np.where(finite & interior & (clearance < -1e-6))[0]
    unknown = not np.all(finite)
    valid_clear = clearance[finite & interior]
    minimum = float(valid_clear.min()) if len(valid_clear) else None
    result = (
        "incomplete data"
        if unknown
        else (
            "modeled ground obstruction"
            if len(hits)
            else "no obstruction found in this ground model"
        )
    )
    obstruction = None
    if len(hits):
        k = hits[0]
        obstruction = dict(
            distance_m=float(distance * t[k]),
            east_m=float(x[k]),
            north_m=float(y[k]),
            ground_m=float(ground[k]),
        )
    # Bounded SVG chart transport. Keep unknown/blocking samples while thinning others.
    stride = max(1, len(t) // 1000)
    keep = set(range(0, len(t), stride)) | {0, len(t) - 1}
    keep.update(np.flatnonzero(~finite).tolist())
    keep.update(hits[:1].tolist())
    points = [
        dict(
            distance_m=float(distance * t[k]),
            ground_m=float(ground[k]) if np.isfinite(ground[k]) else None,
            line_m=float(line[k]) if np.isfinite(line[k]) else None,
        )
        for k in sorted(keep)
    ]
    return dict(
        result=result,
        distance_m=distance,
        minimum_clearance_m=minimum,
        borderline=minimum is not None and abs(minimum) <= 0.05,
        first_obstruction=obstruction,
        points=points,
        eye_m=eye,
        target_height_m=target_height,
        unknown=unknown,
        curvature=curvature,
        warning="Terrain-model diagnostic only. Trees, brush, footing and current field sightlines remain unverified.",
    )


NEARBY_RADIUS = 9.144


@lru_cache(maxsize=8)
def scene_grid(path, mtime, ground):
    a, res, x0, y0 = grid(path, mtime)
    rows, cols = np.indices(a.shape)
    x = x0 + cols * res
    y = y0 - rows * res
    # Exactly the float32 elevations and supported triangles sent to WebGL.
    z = (
        (a - ground - CURVATURE * (x * x + y * y) / (2 * EARTH))
        .astype("<f4")
        .astype(float)
    )
    z[np.hypot(x, y) > 300] = np.nan
    return z, res, x0, y0


def observer(ident, cid, body):
    try:
        if isinstance(body["observer_east_m"], bool) or isinstance(
            body["observer_north_m"], bool
        ):
            raise ValueError()
        east = float(body["observer_east_m"])
        north = float(body["observer_north_m"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Supply both nearby observer offsets in metres.")
    if (
        not all(math.isfinite(v) for v in (east, north))
        or math.hypot(east, north) > NEARBY_RADIUS + 1e-9
    ):
        raise ValueError(
            "Choose a position within 30 ft (9.144 m) of the saved observer."
        )
    r = scene_run(ident) if ready_path(ident, cid).exists() else Run(ident)
    p = r.points[cid]
    lon, lat = r.ll(p["x"] + east, p["y"] + north)
    from shapely.geometry import shape, Point

    features = r.boundary().get("features", [])
    if not any(shape(f["geometry"]).covers(Point(lon, lat)) for f in features):
        raise ValueError(
            "This position is outside the saved observer area. Choose a point inside the boundary."
        )
    folder, meta = bundle(cid, ident, run_data=r)
    if not meta["fine_observer_available"]:
        raise ValueError("Supported fine ground is unavailable at this setup.")
    path = asset_path(folder, meta, "fine.npz")
    a, res, x0, y0 = scene_grid(str(path), path.stat().st_mtime_ns, meta["ground_m"])
    z = float(sample(a, res, x0, y0, np.array(east), np.array(north)))
    if not math.isfinite(z):
        raise ValueError(
            "Fine ground is unknown here. Choose another position; the view has not moved."
        )
    return dict(
        east_m=east,
        north_m=north,
        scene_y_m=z,
        ground_m=z + meta["ground_m"],
        longitude=lon,
        latitude=lat,
        displacement_m=math.hypot(east, north),
        anchor=cid,
        scene_key=meta["key"],
        coverage_anchor_east_m=0,
        coverage_anchor_north_m=0,
        coverage_radius_m=120,
    )


def moved_profile(a, res, x0, y0, pose, x, y, eye, height, ground):
    sx, sy = pose["east_m"], pose["north_m"]
    dx, dy = x - sx, y - sy
    distance = math.hypot(dx, dy)
    if distance < 0.1:
        raise ValueError("Choose an inspection target away from the observer")
    ts = list(np.linspace(0, 1, max(2, math.ceil(distance / (res / 4))) + 1))
    for origin, delta in [
        ((sx - x0) / res, dx / res),
        ((y0 - sy) / res, -dy / res),
        ((sx - x0 - y0 + sy) / res, (dx + dy) / res),
    ]:
        if abs(delta) > 1e-12:
            lo, hi = sorted((origin, origin + delta))
            ts.extend(
                (k - origin) / delta for k in range(math.ceil(lo), math.floor(hi) + 1)
            )
    t = np.unique(np.clip(ts, 0, 1))
    xx = sx + t * dx
    yy = sy + t * dy
    z = sample(a, res, x0, y0, xx, yy) + ground
    start = pose["scene_y_m"] + ground + eye
    end = z[-1] + height
    line = start * (1 - t) + end * t
    finite = np.isfinite(z) & np.isfinite(line)
    interior = (t > 1e-8) & (t < 1 - 1e-8)
    clear = line - z
    hits = np.flatnonzero(finite & interior & (clear < -1e-6))
    unknown = not bool(np.all(finite))
    valid = clear[finite & interior]
    minimum = float(valid.min()) if len(valid) else None
    stride = max(1, len(t) // 1000)
    keep = set(range(0, len(t), stride)) | {0, len(t) - 1}
    keep.update(np.flatnonzero(~finite))
    keep.update(hits[:1])
    points = [
        dict(
            distance_m=float(t[k] * distance),
            ground_m=float(z[k]) if np.isfinite(z[k]) else None,
            line_m=float(line[k]) if np.isfinite(line[k]) else None,
        )
        for k in sorted(keep)
    ]
    block = None
    if len(hits):
        k = hits[0]
        block = dict(
            distance_m=float(t[k] * distance),
            east_m=float(xx[k]),
            north_m=float(yy[k]),
            ground_m=float(z[k]),
        )
    return dict(
        result=(
            "incomplete data"
            if unknown
            else (
                "modeled ground obstruction"
                if len(hits)
                else "no obstruction found in this ground model"
            )
        ),
        points=points,
        distance_m=distance,
        minimum_clearance_m=minimum,
        borderline=minimum is not None and abs(minimum) <= 0.05,
        first_obstruction=block,
        unknown=unknown,
        eye_m=eye,
        target_height_m=height,
        observer=pose,
        curvature=CURVATURE,
        warning="Nearby preview only; no full-area analysis calculated. Ground and foliage use the unchanged saved scene and anchored curvature.",
    )


def profile(ident, cid, body):
    candidate(ident, cid)
    try:
        x = float(body["east_m"])
        y = float(body["north_m"])
        eye = float(body.get("eye_m", 1.7))
        h = float(body.get("target_height_m", 0.8))
    except (KeyError, TypeError, ValueError):
        raise ValueError("Choose a valid target and viewing heights")
    if (
        not all(math.isfinite(v) for v in [x, y, eye, h])
        or not 0.8 <= eye <= 2.2
        or not 0 <= h <= 2.5
        or math.hypot(x, y) > 2000
    ):
        raise ValueError(
            "Use eye height 0.8–2.2 m, target height 0–2.5 m and targets within 2 km."
        )
    from . import vegetation_screen as veg

    scenario = body.get("vegetation_scenario")
    if scenario is not None and (
        not isinstance(scenario, str) or scenario not in veg.SCENARIOS
    ):
        raise ValueError("Choose sparse, medium or dense vegetation screening")
    radius = body.get("vegetation_radius_m", veg.DEFAULT_RADIUS)
    if scenario is not None and (
        isinstance(radius, bool)
        or not isinstance(radius, (int, float))
        or radius not in veg.RANGES
    ):
        raise ValueError("Choose nearby foliage range 30, 60 or 120 m")
    folder, meta = bundle(cid, ident)
    moved = "observer_east_m" in body or "observer_north_m" in body
    pose = observer(ident, cid, body) if moved else None
    if moved and math.hypot(x, y) > 300:
        return dict(
            status="unavailable",
            result="Nearby-position profiles are limited to the saved 300 m fine-ground circle.",
            points=[],
            observer=pose,
        )
    source = (
        "fine"
        if math.hypot(x, y) <= 300 and meta["fine_observer_available"]
        else "baseline"
    )
    path = asset_path(folder, meta, source + ".npz")
    a, res, x0, y0 = grid(str(path), path.stat().st_mtime_ns)
    if moved:
        a, res, x0, y0 = scene_grid(
            str(path), path.stat().st_mtime_ns, meta["ground_m"]
        )
        result = moved_profile(a, res, x0, y0, pose, x, y, eye, h, meta["ground_m"])
    else:
        result = profile_grid(a, res, x0, y0, x, y, eye, h)
    result.update(
        source=source,
        source_label=(
            "Local lidar-derived ground"
            if source == "fine"
            else "Separate baseline-only profile; both endpoints use baseline ground"
        ),
        resolution_m=res,
    )
    if scenario is not None:
        if source != "fine":
            result["vegetation"] = dict(
                status="unavailable",
                reason="Vegetation screening requires fine observer ground and a target within 300 m.",
            )
        elif (
            result["points"][0]["line_m"] is None
            or result["points"][-1]["line_m"] is None
        ):
            result["vegetation"] = dict(
                status="unavailable",
                reason="Observer or target fine ground is unknown.",
            )
        elif not meta.get("vegetation"):
            result["vegetation"] = dict(
                status="unavailable",
                reason="Prepare the inferred vegetation pilot first.",
            )
        else:
            if meta["vegetation"].get("meshes"):
                from . import foliage_clusters

                start = (
                    [pose["east_m"], pose["scene_y_m"] + eye, -pose["north_m"]]
                    if moved
                    else [0, eye, 0]
                )
                end = [x, result["points"][-1]["line_m"] - meta["ground_m"], -y]
                result["vegetation"] = foliage_clusters.evaluate(
                    folder,
                    meta,
                    start,
                    end,
                    result["distance_m"],
                    meta["ground_m"],
                    scenario,
                    result["unknown"],
                    radius,
                    asset_path,
                )
                if moved:
                    v = result["vegetation"]
                    v["farther_vegetation_unevaluated"] = math.hypot(x, y) > radius
                    v["coverage_anchor"] = dict(east_m=0, north_m=0)
                    if math.hypot(x, y) > radius:
                        sx, sy = pose["east_m"], pose["north_m"]
                        dx, dy = x - sx, y - sy
                        b = sx * dx + sy * dy
                        aa = dx * dx + dy * dy
                        v["coverage_exit_distance_m"] = (
                            (
                                -b
                                + math.sqrt(
                                    b * b - aa * (sx * sx + sy * sy - radius * radius)
                                )
                            )
                            / aa
                            * result["distance_m"]
                        )
                return result
            path = folder / meta["vegetation"]["centres_file"]
            centres = veg.load_centres(str(path), path.stat().st_mtime_ns)
            start = (
                [pose["east_m"], pose["scene_y_m"] + eye, -pose["north_m"]]
                if moved
                else [0, eye, 0]
            )
            end = [x, result["points"][-1]["line_m"] - meta["ground_m"], -y]
            primitive_path = folder / meta["vegetation"]["primitive_file"]
            shape = veg.load_primitive(
                str(primitive_path), primitive_path.stat().st_mtime_ns
            )
            result["vegetation"] = veg.evaluate(
                centres,
                start,
                end,
                result["distance_m"],
                meta["ground_m"],
                scenario,
                result["unknown"],
                shape,
                radius,
            )
    return result


def mesh(a, res, x0, y0, ground, radius, inner=0):
    rows, cols = np.indices(a.shape)
    x = x0 + cols * res
    n = y0 - rows * res
    d = np.hypot(x, n)
    a = np.where((d <= radius) & (d >= inner), a, np.nan)
    positions = (
        np.stack(
            [x, np.nan_to_num(a - ground - CURVATURE * d * d / (2 * EARTH), nan=0), -n],
            axis=-1,
        )
        .astype("<f4")
        .reshape(-1, 3)
    )
    index = np.arange(a.size, dtype=np.uint32).reshape(a.shape)
    tl = index[:-1, :-1]
    tr = index[:-1, 1:]
    bl = index[1:, :-1]
    br = index[1:, 1:]
    good = np.isfinite(a)
    one = good[:-1, :-1] & good[:-1, 1:] & good[1:, 1:]
    two = good[:-1, :-1] & good[1:, 1:] & good[1:, :-1]
    # Correct upward winding in east / height / south coordinates.
    faces = np.concatenate(
        [
            np.stack([tl[one], br[one], tr[one]], 1),
            np.stack([tl[two], bl[two], br[two]], 1),
        ]
    ).astype("<u4")
    return positions, faces
