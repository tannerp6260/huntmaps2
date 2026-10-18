"""Read a prior isolated 711 run; benchmark screens in a fresh disposable state."""

import argparse
import contextlib
import json
import shutil
import time
from unittest.mock import patch
from pathlib import Path
import numpy as np
from shapely.geometry import LineString, mapping, Polygon
from shapely.ops import transform
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui import connectivity as c
from huntmaps_gui.scouting_network import save_network
from huntmaps_gui.storage import write
from huntmaps_gui.approach_search import Grid, solve


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = args.workspace.resolve()
    state = out / "state"
    for name in ("networks", "approaches"):
        shutil.copytree(source / "state" / name, state / name)
    with configured(AppConfig(workspace=source, state_dir=state)):
        spec, r = c.snapshot("guided-711")
        assert len(spec["rows"]) == 711
        terrain = c.Terrain(r)
        seed = r.candidate(
            min(r.points.values(), key=lambda p: p.get("slope_deg", 90))["id"]
        )
        area = terrain.proposal(seed)
        dem, origin = terrain.raster(area)
        bounds = list(transform(terrain.ll, terrain.footprint).bounds)
        bounds = [
            bounds[0] - 0.01,
            bounds[1] - 0.01,
            bounds[2] + 0.01,
            bounds[3] + 0.01,
        ]
        x, y = terrain.xy(seed["longitude"], seed["latitude"])
        line = LineString([(x - 1, y), (x + 1, y)])
        road = save_network(
            json.dumps(mapping(transform(terrain.ll, line))).encode(),
            ".geojson",
            "roads",
            "Synthetic benchmark departure only",
            coverage=bounds,
        )
        trail = save_network(
            b'{"type":"FeatureCollection","features":[]}',
            ".geojson",
            "trails",
            "Synthetic benchmark empty trails",
            coverage=bounds,
        )
        spec, r = c.snapshot(r.id)
        token = c.digest(spec)[:32]
        write(
            c.path(token),
            dict(
                id=token,
                version=c.VERSION,
                run_id=r.id,
                status="running",
                maximum_slope_deg=25,
                snapshot=spec,
                points={},
                total=711,
                completed=0,
            ),
        )
        started = time.perf_counter()
        with (out / "screen.log").open("w") as log, contextlib.redirect_stdout(
            log
        ), patch.object(
            Grid, "search", side_effect=AssertionError("Screen called weighted solver")
        ):
            result = c.calculate(r.id, token)
        cold = time.perf_counter() - started
        started = time.perf_counter()
        c.current(r.id)
        warm = time.perf_counter() - started
        positive = [
            cid
            for cid, p in result["points"].items()
            if p["status"] == "connection_found"
        ]
        negative = [
            cid for cid, p in result["points"].items() if p["status"] == "no_connection"
        ]
        chosen = positive[:12] + negative[:12]
        # Compare only computation, sharing the same terrain preparation for both.
        from huntmaps_gui.approach_native import library

        library()
        index = c.Index(r, spec["inventory"])
        quick_s = full_s = 0
        for cid in chosen:
            row = next(row for row in spec["rows"] if row["point"]["id"] == cid)
            started = time.perf_counter()
            e = index.query(row["point"], row["settings"])
            quick_s += time.perf_counter() - started
            started = time.perf_counter()
            area = terrain.proposal(row["point"])
            dem, origin = terrain.raster(area)
            grid = Grid(
                dem, np.zeros_like(dem), np.zeros_like(dem), origin, area, Polygon(), 25
            )
            clipped = line.intersection(area)
            lines = (
                [clipped]
                if not clipped.is_empty and clipped.geom_type == "LineString"
                else []
            )
            full = solve(
                grid,
                lines,
                terrain.xy(row["point"]["longitude"], row["point"]["latitude"]),
                c.ZERO,
            )
            full_s += time.perf_counter() - started
            assert bool(full["alternatives"]) == (e["status"] == "connection_found")
        value = dict(
            cold_s=cold,
            warm_s=warm,
            screened=len(result["points"]),
            network_records=len(spec["inventory"]),
            history_records=len(list((state / "approaches").glob("*/scenario.json"))),
            statuses={
                s: sum(p["status"] == s for p in result["points"].values())
                for s in ("connection_found", "no_connection", "unavailable")
            },
            comparison_sample=len(chosen),
            sample_screen_s=quick_s,
            sample_full_routes_s=full_s,
            weighted_screen_calls=0,
            source_note="Synthetic mapped line and completeness fixtures over actual cached terrain; no access claim",
        )
        (out / "timings.json").write_text(json.dumps(value, indent=2) + "\n")
        print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
