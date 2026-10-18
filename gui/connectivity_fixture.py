"""Synthetic browser fixtures only. Refuses the owner's workspace or state."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
import numpy as np
from osgeo import gdal
from shapely.geometry import mapping
from shapely.ops import transform
from glassing.transfer_fixture import create
from glassing.acquire import digest
from huntmaps_gui.config import current
from huntmaps_gui.catalog import Run
from huntmaps_gui import connectivity as c, workflow, manual_observers, approach_service
from huntmaps_gui.scouting_network import save_network
from huntmaps_gui.storage import write


def owner(name, source, area):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "huntmaps_gui.owner_worker",
            "run",
            "--area",
            area,
            "--source-config",
            source,
            "--name",
            name,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return Run(name)


def sources(r, point):
    terrain = c.Terrain(r)
    bounds = list(transform(terrain.ll, terrain.footprint).bounds)
    bounds = [bounds[0] - 0.01, bounds[1] - 0.01, bounds[2] + 0.01, bounds[3] + 0.01]
    x, y = terrain.xy(point["longitude"], point["latitude"])
    raw = json.dumps(
        dict(
            type="LineString",
            coordinates=[terrain.ll(x - 10, y - 20), terrain.ll(x + 10, y + 20)],
        )
    ).encode()
    road = save_network(
        raw, ".geojson", "roads", "Synthetic connectivity fixture", coverage=bounds
    )
    trail = save_network(
        b'{"type":"FeatureCollection","features":[]}',
        ".geojson",
        "trails",
        "Synthetic empty trails",
        coverage=bounds,
    )
    return [road["id"], trail["id"]]


def shortlist(r, cid):
    workflow.decide(
        r.id,
        cid,
        dict(
            action="shortlist",
            revision=workflow.records(r.id)["revision"],
            point=workflow.point(r.id, cid),
        ),
        None,
    )


def main():
    config = current()
    if (
        config.workspace == config.source_dir
        or config.state_dir == config.source_dir / ".gui"
    ):
        raise ValueError("Use an isolated workspace and state")
    r = owner(
        "connection-fixture", "search-fixture.json", "workflow-fixture/observer.geojson"
    )
    ids = list(r.points)
    found, blocked, kept = ids[:3]
    networks = sources(r, r.candidate(found))
    terrain = c.Terrain(r)
    drafts = {}
    for cid in (blocked, kept):
        area = mapping(transform(terrain.ll, terrain.proposal(r.candidate(cid))))
        drafts[cid] = dict(
            point=workflow.point(r.id, cid),
            travel_area=area,
            exclusions=[area],
            maximum_slope_deg=25,
            network_ids=networks,
            kinds=["roads", "trails"],
        )
    shortlist(r, kept)
    write(
        config.state_dir / "approach-reviews" / f"{r.id}.json",
        dict(
            version=1,
            revision=1,
            queue=[kept],
            active_point=kept,
            drafts=drafts,
            defaults=dict(maximum_slope_deg=25),
        ),
    )
    pose = dict(
        anchor=found,
        longitude=r.candidate(found)["longitude"],
        latitude=r.candidate(found)["latitude"],
        east_m=1,
        north_m=0,
    )
    with patch.object(manual_observers.fp, "observer", return_value=pose):
        manual = manual_observers.create(r.id, dict(name="Exact synthetic manual spot"))
    # A separate tilted plane makes the explicit 25-to-30-degree retry reproducible.
    create("connection-retry-source.json", "connection-retry-inputs")
    path = Path("connection-retry-source.json")
    v = json.loads(path.read_text())
    ds = gdal.Open(v["data"]["dem"]["path"], gdal.GA_Update)
    yy, xx = np.indices((ds.RasterYSize, ds.RasterXSize))
    ds.GetRasterBand(1).WriteArray(
        (2100 + xx * 10 * np.tan(np.deg2rad(28))).astype("float32")
    )
    ds = None
    v["data"]["dem"]["sha256"] = digest(v["data"]["dem"]["path"])
    v["search"] = dict(
        version=1,
        ranking_version=2,
        target_filters={},
        avoid_dense_vegetation=False,
        recommendation_count=5,
        nearby_radius_m=30,
        tree_threshold_percent=10,
    )
    v["normal_scouting"] = True
    path.write_text(json.dumps(v))
    retry = owner(
        "connection-retry", str(path), "connection-retry-inputs/observer.geojson"
    )
    cid = next(iter(retry.points))
    shortlist(retry, cid)
    nets = sources(retry, retry.candidate(cid))
    t = c.Terrain(retry)
    body = dict(
        ids=[cid],
        travel_area=mapping(transform(t.ll, t.proposal(retry.candidate(cid)))),
        exclusions=[],
        maximum_slope_deg=25,
        network_ids=nets,
        kinds=["roads", "trails"],
        weights=dict(slope=1, gain=1, tree=1, shrub=1),
        start=None,
        pinned=None,
    )
    scenario = approach_service.create(retry.id, body, None)
    approach_service.compute(scenario["id"])
    write(
        config.state_dir / "approach-reviews" / f"{retry.id}.json",
        dict(
            version=1,
            revision=1,
            queue=[cid],
            active_point=cid,
            defaults=dict(maximum_slope_deg=25),
            drafts={
                cid: dict(
                    body,
                    point=workflow.point(retry.id, cid),
                    scenario=scenario["id"],
                    attempted=True,
                    alternative=0,
                    boundary_confirmed=True,
                )
            },
        ),
    )
    print(
        json.dumps(
            dict(
                run=r.id,
                found=found,
                blocked=blocked,
                kept=kept,
                manual=manual["id"],
                retry_run=retry.id,
                retry_cid=cid,
                scenario=scenario["id"],
            )
        )
    )


if __name__ == "__main__":
    main()
