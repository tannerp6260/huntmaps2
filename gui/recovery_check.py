"""Disposable browser acceptance with real jobs and controlled provider responses."""

import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    work = Path(tempfile.mkdtemp(prefix="huntmaps-browser-recovery-"))
    print("Recovery acceptance artifacts:", work, flush=True)
    for name in ["gui", "docs"]:
        (work / name).symlink_to(ROOT / name, target_is_directory=True)
    for name in ["huntmaps_gui", "glassing", "configs"]:
        shutil.copytree(
            ROOT / name, work / name, ignore=shutil.ignore_patterns("__pycache__")
        )
    env = dict(
        os.environ,
        PYTHONPATH=str(work),
        HUNTMAPS_SOURCE_DIR=str(work),
        HUNTMAPS_WORKSPACE=str(work),
        HUNTMAPS_STATE_DIR=str(work / "state"),
    )
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from glassing.transfer_fixture import create;create('fixture.json','fixture',32613)",
        ],
        cwd=work,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "huntmaps_gui.owner_worker",
            "run",
            "--area",
            "fixture/observer.geojson",
            "--source-config",
            "fixture.json",
            "--name",
            "starter",
        ],
        cwd=work,
        env=env,
        check=True,
    )
    c = json.loads((work / "fixture.json").read_text())
    c["data"]["shrub"] = None
    (work / "configs/transfer.template.json").write_text(json.dumps(c))

    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json
from glassing.transfer import project
from huntmaps_gui.scouting_network import save_network
from shapely.geometry import shape
value=json.load(open('fixture/observer.geojson'))
from shapely.ops import unary_union
area=unary_union([shape(f['geometry']) for f in value['features']]) if value.get('type')=='FeatureCollection' else shape(value.get('geometry',value))
ll=project(32613,4326)
line=dict(type='LineString',coordinates=[ll(450140,4200000),ll(450140,4200400)])
for kind in ['roads','trails']:
 save_network(json.dumps(line).encode(),'.geojson',kind,'Controlled cached inventory',coverage=list(area.bounds))
""",
        ],
        cwd=work,
        env=env,
        check=True,
    )

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    provider = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Quiet, directory=str(work / "fixture"))
    )
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    (work / "sitecustomize.py").write_text(
        f"""
import urllib.request
from pathlib import Path
original=urllib.request.urlopen
def controlled(request,*args,**kwargs):
 url=request.full_url if hasattr(request,'full_url') else str(request)
 if 'geoserver/mrlc_shrub' in url:
  request='http://127.0.0.1:{provider.server_port}/shrub.tif'
 elif not url.startswith('http://127.0.0.1:'):
  raise AssertionError('Uncontrolled external request: '+url)
 return original(request,*args,**kwargs)
urllib.request.urlopen=controlled
from huntmaps_gui import search
score=search.score
def fail_once(c):
 marker=Path('injected-analysis-failure')
 if not marker.exists():
  marker.write_text('controlled failure after download')
  raise ValueError('Injected post-download analysis failure')
 return score(c)
search.score=fail_once
"""
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env.update(
        HUNTMAPS_URL=f"http://127.0.0.1:{port}",
        HUNTMAPS_IMPORT_FILE=str(work / "fixture/observer.geojson"),
        HUNTMAPS_SCREENSHOTS=str(work / "screenshots"),
    )
    process = None
    try:
        with (work / "server.log").open("w") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    f"import uvicorn;from huntmaps_gui.server import create_app;uvicorn.run(create_app(),host='127.0.0.1',port={port},log_level='warning')",
                ],
                cwd=work,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError((work / "server.log").read_text())
                try:
                    with urllib.request.urlopen(
                        env["HUNTMAPS_URL"] + "/api/runs", timeout=0.5
                    ):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Recovery server timeout")
            subprocess.run(
                ["node", "browser-recovery-check.mjs"],
                cwd=ROOT / "gui/frontend",
                env=env,
                check=True,
                timeout=180,
            )
            subprocess.run(
                ["node", "browser-workflow-check.mjs"],
                cwd=ROOT / "gui/frontend",
                env=dict(
                    env,
                    HUNTMAPS_WORKFLOW_RUN="browser-recovery",
                    HUNTMAPS_SCREENSHOTS=str(work / "workflow-screenshots"),
                ),
                check=True,
                timeout=180,
            )
    finally:
        if process:
            process.terminate()
            process.wait(timeout=10)
        provider.shutdown()
        provider.server_close()


if __name__ == "__main__":
    main()
