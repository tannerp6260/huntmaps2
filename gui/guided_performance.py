"""Offline 711-location, accumulated-history check. Writes only its supplied output folder."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui.storage import write, read_json
from huntmaps_gui.server import create_app
from huntmaps_gui.catalog import Run
from huntmaps_gui import approach_service, scouting_network, workflow
from fastapi.testclient import TestClient
from shapely.geometry import LineString, mapping
from shapely.ops import transform
from glassing.transfer import project

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuse-completed", action="store_true")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=args.reuse_completed)
    for folder in ("glassing", "configs"):
        shutil.copytree(
            ROOT / folder,
            out / folder,
            ignore=shutil.ignore_patterns("__pycache__"),
            dirs_exist_ok=args.reuse_completed,
        )
    config = json.loads((ROOT / "results/soap-creek-v1/scouting.json").read_text())

    def absolute(value):
        if isinstance(value, dict):
            if "path" in value and isinstance(value["path"], str):
                value["path"] = str((ROOT / value["path"]).resolve())
            for v in value.values():
                absolute(v)
        elif isinstance(value, list):
            for v in value:
                absolute(v)

    absolute(config["data"])
    config.update(candidate_count=711, normal_scouting=True)
    config["search"] = dict(
        version=1,
        ranking_version=2,
        target_filters={},
        avoid_dense_vegetation=False,
        recommendation_count=20,
        nearby_radius_m=30,
        tree_threshold_percent=10,
    )
    (out / "source.json").write_text(json.dumps(config))
    env = dict(
        os.environ,
        PYTHONPATH=str(ROOT),
        HUNTMAPS_STATE_DIR=str(out / "state"),
        HUNTMAPS_WORKSPACE=str(out),
        HUNTMAPS_SOURCE_DIR=str(ROOT),
        PYTHONDONTWRITEBYTECODE="1",
        HUNTMAPS_DISABLE_SPEED_PROBE="1",
    )
    if not args.reuse_completed:
        began = time.perf_counter()
        with (out / "owner.log").open("w") as log:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "huntmaps_gui.owner_worker",
                    "run",
                    "--area",
                    str(ROOT / "results/soap-creek-v1/observer.geojson"),
                    "--source-config",
                    str(out / "source.json"),
                    "--name",
                    "guided-711",
                ],
                cwd=out,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=600,
            )
        owner_s = time.perf_counter() - began
    else:
        owner_s = read_json(out / "results/guided-711/timing.json")[
            "owner_analysis_wall_s"
        ]
    records = []

    def measure(name, fn):
        started = time.perf_counter()
        result = fn()
        records.append(dict(stage=name, seconds=time.perf_counter() - started))
        return result

    appconfig = AppConfig(workspace=out, state_dir=out / "state")
    with configured(appconfig):
        app = create_app(appconfig)
        try:
            client = TestClient(app)
            r = Run("guided-711")
            rows = list(r.points.values())
            assert len(rows) == 711, len(rows)
            cid = rows[0]["id"]
            point = r.candidate(cid)
            p = workflow.point("guided-711", cid)
            workflow.decide(
                "guided-711",
                cid,
                dict(
                    revision=workflow.records("guided-711")["revision"],
                    point=p,
                    action="shortlist",
                ),
                app.state.jobs,
            )
            ll = project(r.config["epsg"], 4326)
            xy = project(4326, r.config["epsg"])(point["longitude"], point["latitude"])
            line = mapping(
                transform(
                    ll,
                    LineString(
                        [(xy[0] - 100, xy[1] - 300), (xy[0] - 100, xy[1] + 300)]
                    ),
                )
            )
            network = scouting_network.save_network(
                json.dumps(line).encode(),
                ".geojson",
                "trails",
                "Synthetic benchmark inventory",
            )
            for index in range(60):
                ident = f"{index+1:032x}"
                target = out / "state/networks" / ident
                if ident == network["id"]:
                    continue
                shutil.copytree(
                    out / "state/networks" / network["id"],
                    target,
                    dirs_exist_ok=args.reuse_completed,
                )
                value = read_json(target / "network.json")
                value["id"] = ident
                write(target / "network.json", value)
            area = mapping(
                transform(
                    ll,
                    __import__("shapely.geometry", fromlist=["box"]).box(
                        xy[0] - 1000, xy[1] - 1000, xy[0] + 1000, xy[1] + 1000
                    ),
                )
            )
            body = dict(
                ids=[cid],
                travel_area=area,
                network_ids=[network["id"]],
                maximum_slope_deg=25,
            )
            scenario = measure(
                "create_with_711_locations",
                lambda: approach_service.create("guided-711", body, app.state.jobs),
            )
            for index in range(80):
                ident = f"{index+1:032x}"
                write(
                    out / "state/approaches" / ident / "scenario.json",
                    dict(scenario, id=ident),
                )
                write(
                    out / "state/jobs" / (ident + ".json"),
                    dict(
                        id=ident,
                        kind="approach",
                        status="complete",
                        started=0,
                        finished=1,
                        plan=ident,
                    ),
                )
            endpoints = [
                "/api/runs/guided-711",
                "/api/networks",
                "/api/runs/guided-711/approaches",
                "/api/runs/guided-711/approaches?summary=true",
                "/api/approaches/" + scenario["id"],
                "/api/jobs",
                "/api/jobs/" + f"{1:032x}",
            ]
            for endpoint in endpoints:
                for repeat in range(2):
                    response = measure(
                        endpoint + (":cold" if repeat == 0 else ":warm"),
                        lambda: client.get(endpoint),
                    )
                    assert response.status_code == 200, response.text
            info = dict(
                locations=len(rows),
                network_records=len(
                    list((out / "state/networks").glob("*/network.json"))
                ),
                history_records=len(
                    list((out / "state/approaches").glob("*/scenario.json"))
                ),
                owner_s=owner_s,
                timings=records,
            )
            (out / "timings.json").write_text(json.dumps(info, indent=2))
            print(json.dumps(info, indent=2))
        finally:
            app.state.jobs.shutdown()


if __name__ == "__main__":
    main()
