"""Real GMU pack acceptance with an isolated server and startup socket denial."""

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import httpx
from shapely.geometry import box, shape, mapping
from shapely.ops import transform, unary_union
from glassing.transfer import project
from huntmaps_gui.unit_packs import load
from huntmaps_gui.storage import write

ROOT = Path(__file__).resolve().parents[1]


def main():
    home = Path(tempfile.mkdtemp(prefix="huntmaps-pack-offline-"))
    workspace = home / "workspace"
    workspace.mkdir()
    for name in ("glassing", "configs", "docs"):
        (workspace / name).symlink_to(ROOT / name, target_is_directory=True)
    hook = home / "hooks"
    hook.mkdir()
    (hook / "sitecustomize.py").write_text(
        """import socket,os,json
from pathlib import Path
old=socket.socket.connect
oldex=socket.socket.connect_ex
oldaddr=socket.getaddrinfo
def allow(address):
 if isinstance(address,tuple) and str(address[0]) not in ('127.0.0.1','localhost','::1'):
  with open(os.environ['PACK_NETWORK_LOG'],'a') as f:f.write(json.dumps({'blocked':str(address)})+'\\n')
  raise OSError('External network blocked from application startup')
def connect(self,address):
 allow(address);return old(self,address)
def connect_ex(self,address):
 allow(address);return oldex(self,address)
def getaddrinfo(host,*a,**k):
 if host is not None and str(host) not in ('127.0.0.1','localhost','::1',"b'127.0.0.1'"):
  allow((host,0))
 return oldaddr(host,*a,**k)
socket.socket.connect=connect;socket.socket.connect_ex=connect_ex;socket.getaddrinfo=getaddrinfo
"""
    )
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(
        os.environ,
        HUNTMAPS_STATE_DIR=str(workspace / "state"),
        HUNTMAPS_WORKSPACE=str(workspace),
        HUNTMAPS_SOURCE_DIR=str(ROOT),
        HUNTMAPS_PACK_DIR=str(ROOT / "data/unit-packs"),
        HUNTMAPS_DISABLE_SPEED_PROBE="1",
        PYTHONPATH=str(hook) + os.pathsep + str(ROOT),
        PACK_NETWORK_LOG=str(home / "network-attempts.jsonl"),
        PYTHONDONTWRITEBYTECODE="1",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
    )
    (home / "server-env.json").write_text(
        json.dumps(
            {
                k: v
                for k, v in env.items()
                if k.startswith(("HUNTMAPS_", "PACK_"))
                or k
                in (
                    "PYTHONPATH",
                    "PYTHONDONTWRITEBYTECODE",
                    "OPENBLAS_NUM_THREADS",
                    "OMP_NUM_THREADS",
                )
            },
            indent=2,
        )
    )
    log = (home / "server.log").open("w")
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "huntmaps_gui.server:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=workspace,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    print("ACCEPTANCE " + str(home), flush=True)
    write(
        home / "location.json",
        dict(base=base, home=str(home), workspace=str(workspace)),
    )
    client = httpx.Client(base_url=base, headers={"X-HuntMaps": "local"}, timeout=120)

    def call(method, path, **kwargs):
        r = client.request(method, "/api" + path, **kwargs)
        if r.status_code != 200:
            raise AssertionError(f"{method} {path} {r.status_code} {r.text[:4000]}")
        return r.json()

    def job(j):
        for _ in range(2400):
            v = call("GET", "/jobs/" + j["id"])
            if v["status"] == "complete":
                return v
            if v["status"] not in ("running", "cancelling"):
                raise AssertionError(json.dumps(v))
            time.sleep(0.2)
        raise AssertionError("job timed out")

    try:
        for _ in range(150):
            if server.poll() is not None:
                raise RuntimeError((home / "server.log").read_text())
            try:
                call("GET", "/unit-packs")
                break
            except httpx.ConnectError:
                time.sleep(0.1)
        folder, v = load("co-gmu54")
        boundary = unary_union(
            [
                shape(f["geometry"])
                for f in json.loads((folder / v["boundary"]).read_text())["features"]
            ]
        )
        unit = transform(project(4326, 32613), boundary)
        assert call("GET", "/unit-packs")["units"][0]["status"] == "ready"
        # Choose new small areas near measured roads at west/central/east positions.
        points = []
        for spec in v["networks"]["roads"]:
            for f in json.loads((folder / spec["path"]).read_text())["features"]:
                g = transform(project(4326, 32613), shape(f["geometry"]))
                q = g.interpolate(0.53, normalized=True)
                if unit.covers(q.buffer(700)):
                    points.append(q)
        points.sort(key=lambda p: (p.x, p.y))
        selections = [
            points[int((len(points) - 1) * fraction)] for fraction in (0.02, 0.49, 0.98)
        ]
        selections.append(
            min(points, key=lambda q: abs(project(32613, 4326)(q.x, q.y)[0] + 107))
        )
        outcomes = []
        for n, q in enumerate(selections):
            run = f"pack-offline-{n+1}"
            area = transform(
                project(32613, 4326), box(q.x - 400, q.y - 350, q.x + 400, q.y + 350)
            )
            raw = json.dumps(
                dict(type="Feature", properties={"name": run}, geometry=mapping(area))
            ).encode()
            imported = call(
                "POST",
                "/imports",
                files={"file": ("area.geojson", raw, "application/geo+json")},
            )
            body = dict(
                name=run,
                import_id=imported["id"],
                polygon="1",
                unit_id="co-gmu54",
                pack_version=v["version"],
                radius_m=2000,
                candidate_count=24,
                recommendation_count=12,
                estimate_first=False,
                include_network=True,
                access_sampling=dict(
                    network_ids=[],
                    kinds=["roads", "trails"],
                    distance_m=804.672,
                    height_m=None,
                ),
                max_download_mb=10,
            )
            if n == 1:
                from huntmaps_gui.habitat import DEFAULTS

                body["habitat"] = DEFAULTS
            j = call("POST", "/plans", json=body)
            job(j)
            plan = call("GET", "/plans/" + j["plan"])
            assert plan["sources_ready"], plan
            assert plan["acquisition"]["estimated_bytes"] == 0, plan
            started = call(
                "POST",
                "/plans/" + j["plan"] + "/start",
                json={"download": False, "review_signature": plan["review_signature"]},
            )
            job(started)
            result = call("GET", "/runs/" + run)
            assert result["unit_pack"]["version"] == v["version"]
            assert len(result["candidates"]) > 0
            screen = call("POST", "/runs/" + run + "/connectivity-screen", json={})
            if screen.get("job"):
                job(screen["job"])
            elif screen.get("job_id"):
                job({"id": screen["job_id"]})
            current = call("GET", "/runs/" + run + "/connectivity-screen")
            write(home / (run + "-screen.json"), current)
            # The completed screen carries connected candidates; choose the first,
            # otherwise attempt measured-road candidates and retain diagnostics.
            rows = current.get("results", current.get("rows", []))
            print("SCREEN", run, json.dumps(current)[:500], flush=True)
            candidates = result["candidates"]
            scenario = None
            cid = None
            for candidate in candidates[:12]:
                cid = candidate["id"]
                lon = candidate["longitude"]
                lat = candidate["latitude"]
                proposal = (
                    call(
                        "POST", "/runs/" + run + "/approach-proposal", json={"id": cid}
                    )
                    if False
                    else None
                )
                p = transform(
                    project(4326, 32613),
                    shape(dict(type="Point", coordinates=[lon, lat])),
                )
                travel = transform(project(32613, 4326), p.buffer(1900, resolution=48))
                nets = call(
                    "POST", "/networks/resolve", json={"bounds": list(travel.bounds)}
                )["network_ids"]
                assert len(nets) == 2
                state = call("GET", "/runs/" + run + "/workflow")
                point = call("GET", "/runs/" + run + "/workflow-point/" + cid)
                if cid not in state["points"] or not state["points"][cid].get(
                    "shortlisted"
                ):
                    call(
                        "PUT",
                        "/runs/" + run + "/workflow/" + cid,
                        json=dict(
                            action="shortlist", point=point, revision=state["revision"]
                        ),
                    )
                submitted = call(
                    "POST",
                    "/runs/" + run + "/approaches",
                    json=dict(
                        ids=[cid],
                        network_ids=nets,
                        travel_area=mapping(travel),
                        maximum_slope_deg=35,
                    ),
                )
                job(submitted["job"])
                saved = call("GET", "/approaches/" + submitted["scenario"]["id"])
                if saved["results"]["results"][0]["alternatives"]:
                    scenario = saved
                    break
                state = call("GET", "/runs/" + run + "/workflow")
                call(
                    "PUT",
                    "/runs/" + run + "/workflow/" + cid,
                    json=dict(action="remove", point=point, revision=state["revision"]),
                )
            assert scenario, "No connected candidate in tested pool; retain diagnostics"

            def decide(action, **extra):
                state = call("GET", "/runs/" + run + "/workflow")
                return call(
                    "PUT",
                    "/runs/" + run + "/workflow/" + cid,
                    json=dict(
                        action=action, point=point, revision=state["revision"], **extra
                    ),
                )

            decide("approach", scenario=scenario["scenario"]["id"], alternative=0)
            basic = call(
                "POST",
                "/first-person/plans",
                json=dict(run_id=run, ids=[cid], fidelity="terrain"),
            )
            job(basic)
            scene_plan = call("GET", "/first-person/plans/" + basic["plan"])
            assert scene_plan["estimated_new_bytes"] == 0
            job(
                call(
                    "POST",
                    "/first-person/plans/" + basic["plan"] + "/start",
                    json={"download": False},
                )
            )
            scene = call("GET", "/runs/" + run + "/first-person/" + cid)
            assert scene["status"] == "ready" and scene["fidelity"] == "terrain", scene
            for a in scene.get("assets", {}).values():
                pass
            decide("viewed", scene=scene["key"])
            decide("confirm")
            call(
                "PUT",
                "/runs/" + run + "/annotations/" + cid,
                json=dict(
                    revision=0, status="keep", notes="Offline GMU pack acceptance"
                ),
            )
            for fmt in ("gpx", "kml"):
                r = client.get(
                    "/api/runs/" + run + "/export/" + fmt, params={"ids": cid}
                )
                assert r.status_code == 200
                r.raise_for_status()
                (home / (run + "." + fmt)).write_bytes(r.content)
                import xml.etree.ElementTree as ET

                ET.fromstring(r.content)
            again = call("GET", "/runs/" + run)
            assert again["unit_pack"] == result["unit_pack"]
            assert call("GET", "/runs/" + run + "/workflow")["points"][cid]["confirmed"]
            config = json.loads(
                (workspace / "results" / run / "scouting.json").read_text()
            )
            assert all(
                Path(config["data"][k]["path"]).is_file()
                for k in ("dem", "tree", "shrub", "herb", "summer", "winter")
            )
            outcomes.append(
                dict(
                    run=run,
                    candidate=cid,
                    coordinates=[point["longitude"], point["latitude"]],
                    distance_to_unit_boundary_m=unit.boundary.distance(q),
                    area_bounds=list(area.bounds),
                    screen=current.get("counts"),
                    unit_pack=result["unit_pack"],
                    scene_key=scene["key"],
                    source_windows={
                        k: config["data"][k].get("local_window_bounds")
                        for k in ("dem", "tree", "shrub", "herb")
                    },
                )
            )
            write(home / "outcomes.json", outcomes)
            print("PASSED " + run, flush=True)
        # Oversized whole-unit intake must fail before a job starts.
        imp = call(
            "POST",
            "/imports",
            files={
                "file": (
                    "unit.geojson",
                    json.dumps(
                        dict(type="Feature", geometry=mapping(boundary), properties={})
                    ).encode(),
                    "application/geo+json",
                )
            },
        )
        r = client.post(
            "/api/plans",
            json=dict(
                name="oversized",
                import_id=imp["id"],
                polygon="1",
                unit_id="co-gmu54",
                pack_version=v["version"],
                radius_m=3000,
                candidate_count=12,
                recommendation_count=12,
            ),
        )
        assert r.status_code == 400 and "smaller" in r.text, r.text
        assert not (workspace / "results/oversized").exists()
        attempts = home / "network-attempts.jsonl"
        assert not attempts.exists() or not attempts.read_text(), attempts.read_text()
        write(
            home / "acceptance.json",
            dict(
                status="passed",
                new_areas=len(outcomes),
                external_socket_attempts=0,
                whole_unit_rejected=True,
                base=base,
            ),
        )
        # Browser runs while the socket-denied server is alive.
        browser_env = dict(
            env,
            HUNTMAPS_URL=base,
            HUNTMAPS_SCREENSHOTS=str(home / "screenshots"),
            HUNTMAPS_PACK_ACCEPTANCE=str(home / "outcomes.json"),
        )
        subprocess.run(
            ["node", "browser-unit-packs-check.mjs"],
            cwd=ROOT / "gui/frontend",
            env=browser_env,
            check=True,
        )
        print("OFFLINE ACCEPTANCE PASSED " + str(home), flush=True)
    finally:
        server.terminate()
        try:
            server.wait(timeout=20)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
        log.close()
        client.close()


if __name__ == "__main__":
    main()
