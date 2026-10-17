"""Normal GUI distance adapter; historical engine and model files stay byte-identical."""

import math
from pathlib import Path
from types import FunctionType
from shapely.geometry import Point, mapping
from shapely.ops import transform
from glassing import transfer
from glassing.transfer import work, read, dump, srs, polygon, manual, digest, project


def intake(c):
    band = transfer.read(c["model_lock"])["attention"]["band_m"]
    if c["radius_m"] % band == 0:
        return transfer.intake(c)
    if not c.get("normal_scouting"):
        raise ValueError("Historical experiments require the recorded metric radius")
    from .requests import Preparation

    Preparation.radius_preset(c["radius_m"])
    return _yard_intake(c)


def prepare(c):
    # Same preparation function, with only its intake boundary supplied by this adapter.
    return FunctionType(
        transfer.prepare.__code__, dict(transfer.__dict__, intake=intake)
    )(c)


def _yard_intake(c):
    root = work(c)
    if not 0 <= c["season"]["winter_mix"] <= 1 or c["observation_minutes"] <= 0:
        raise ValueError("Invalid common seasonal mixture or effort budget")
    if (
        not c.get("normal_scouting")
        and c["radius_m"] % read(c["model_lock"])["attention"]["band_m"]
    ):
        raise ValueError("Radius must be a multiple of the frozen 500m patch band")
    required = ["observer_polygon"] + (
        ["manual_points"]
        if not c.get("normal_scouting") or c.get("manual_points")
        else []
    )
    missing = [c.get(k) for k in required if not c.get(k) or not Path(c[k]).is_file()]
    if missing:
        result = dict(
            status="WAITING_FOR_HUNTER_INPUTS",
            missing=missing,
            message="No replacement AOI or generated manual selections will be chosen. Supply polygon and manual waypoints; see docs/glassing/transfer/INPUTS.md.",
        )
        dump(root / "intake.json", result)
        return result
    sr = srs(c["epsg"])
    if not sr.IsProjected() or abs(sr.GetLinearUnits() - 1) > 1e-9:
        raise ValueError("Analysis EPSG must be projected metres")
    if c["radius_m"] <= 0 or c["resolution_m"] <= 0:
        raise ValueError("Positive radius and resolution required")
    area = polygon(c["observer_polygon"], c["epsg"])
    pts = (
        manual(c["manual_points"], c["epsg"], area, c["manual_provenance"])
        if c.get("manual_points")
        else []
    )
    # Observer domain and target support are deliberately different geometries.
    domain = area.buffer(c["radius_m"], resolution=64)
    targets = domain
    if c.get("target_limit"):
        targets = targets.intersection(polygon(c["target_limit"], c["epsg"]))
    for p in c["target_exclusions"]:
        targets = targets.difference(polygon(p, c["epsg"]))
    observers = area
    for p in c["observer_exclusions"]:
        observers = observers.difference(polygon(p, c["epsg"]))
    for p in pts:
        if not observers.covers(Point(p["x"], p["y"])):
            raise ValueError(
                "Manual point excluded by observer policy: " + p["original_id"]
            )
    halo = domain.buffer(2 * c["resolution_m"])
    access = (
        polygon(c["access"]["extent_polygon"], c["epsg"])
        if c["access"].get("extent_polygon")
        else area.buffer(max(c["access"]["buffer_m"], c["radius_m"]))
    )
    if not access.covers(domain):
        raise ValueError(
            "Access-data extent must encompass observation context; enlarge it explicitly"
        )
    result = dict(
        status="INPUTS_IMPORTED",
        kind=c["input_kind"],
        manual_count=len(pts),
        observer_area_km2=observers.area / 1e6,
        target_area_km2=targets.area / 1e6,
        target_policy=c["target_policy"],
        source_hashes={
            str(p): digest(p)
            for p in [c["observer_polygon"]]
            + ([c["manual_points"]] if c.get("manual_points") else [])
            + c["target_exclusions"]
            + c["observer_exclusions"]
            + ([c["target_limit"]] if c.get("target_limit") else [])
            + (
                [c["access"]["extent_polygon"]]
                if c["access"].get("extent_polygon")
                else []
            )
        },
        geometry={
            k: mapping(g)
            for k, g in [
                ("observer", observers),
                ("target", targets),
                ("target_context", domain),
                ("terrain_halo", halo),
                ("access_extent", access),
            ]
        },
        acquisition_requests={
            k: dict(
                epsg=c["epsg"],
                bounds=list(g.bounds),
                wgs84_bounds=list(transform(project(c["epsg"], 4326), g).bounds),
            )
            for k, g in [("terrain", halo), ("access", access)]
        },
        warning="Permission/actionability unknown unless explicitly evidenced. Terrain halo never masked by ownership. Access buffer is an initial query extent, not proof of connectivity.",
    )
    dump(root / "intake.json", result)
    dump(root / "manual_import.json", pts)
    return result


def packet(c):
    """Keep recorded fractional radii; only distance-ring iteration needs integers."""
    from glassing import transfer_packet

    def metric_range(start, stop=None, step=1):
        if stop is None:
            return range(start)
        return range(start, math.floor(stop), step)

    return FunctionType(
        transfer_packet.run.__code__, dict(transfer_packet.__dict__, range=metric_range)
    )(c)
