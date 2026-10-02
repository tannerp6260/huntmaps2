"""Disposable local verification; never reuse the owner's GUI server or state."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def inventory():
    records = {}
    for folder in ("glassing", "configs", "docs/glassing", "data", "runs", "results"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                records[str(path.relative_to(ROOT))] = (
                    path.stat().st_size,
                    path.stat().st_mtime_ns,
                )
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-browser", action="store_true")
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="huntmaps-check-"))
    state = work / "state"
    state.mkdir()
    env = dict(
        os.environ,
        HUNTMAPS_STATE_DIR=str(state),
        HUNTMAPS_WORKSPACE=str(work / "workspace"),
        HUNTMAPS_SOURCE_DIR=str(ROOT),
        HUNTMAPS_SCREENSHOTS=str(work / "screenshots"),
        HUNTMAPS_IMPORT_FILE=str(ROOT / "inputs/test.kml"),
        HUNTMAPS_BROWSER=os.environ.get("HUNTMAPS_BROWSER", "/usr/bin/google-chrome"),
    )
    (work / "workspace").mkdir()
    before = inventory()
    process = None

    def run(command, label, cwd=ROOT):
        print(label, flush=True)
        with (work / (label + ".log")).open("w") as log:
            result = subprocess.run(
                command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT
            )
        if result.returncode:
            print((work / (label + ".log")).read_text()[-12000:], flush=True)
            raise RuntimeError(label + " failed")

    try:
        patterns = [
            "test_gui*.py",
            "test_first_person.py",
            "test_vegetation_screen.py",
            "test_nearby_foliage.py",
            "test_foliage_clusters.py",
            "test_nearby_observer.py",
            "test_working_waypoints.py",
            "test_gui_storage.py",
        ]
        for pattern in patterns:
            run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-p",
                    pattern,
                    "-v",
                ],
                pattern.replace(".py", ""),
            )
        run(["npm", "run", "build"], "frontend-build", ROOT / "gui/frontend")
        if not args.skip_browser:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            env["HUNTMAPS_URL"] = f"http://127.0.0.1:{port}"
            server_log = (work / "server.log").open("w")
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "huntmaps_gui",
                    "--no-browser",
                    "--port",
                    str(port),
                    "--state-dir",
                    str(state),
                    "--test-workspace",
                    str(work / "workspace"),
                ],
                cwd=ROOT,
                env=env,
                stdout=server_log,
                stderr=subprocess.STDOUT,
            )
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError(
                        "Dedicated test server failed; inspect server.log"
                    )
                try:
                    with urllib.request.urlopen(
                        env["HUNTMAPS_URL"] + "/api/runs", timeout=0.5
                    ):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Dedicated test server did not become ready")
            for script in (
                "browser-check.mjs",
                "browser-training-check.mjs",
                "browser-first-person-check.mjs",
                "browser-working-waypoint-check.mjs",
            ):
                run(
                    ["node", script], script.removesuffix(".mjs"), ROOT / "gui/frontend"
                )
        print("Checks passed. Diagnostics: " + str(work), flush=True)
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            server_log.close()
        after = inventory()
        changed = [
            path
            for path in before.keys() | after.keys()
            if before.get(path) != after.get(path)
        ]
        (work / "protected-audit.json").write_text(
            json.dumps(dict(files=len(before), changed=changed), indent=2)
        )
        print("Diagnostics retained: " + str(work), flush=True)
        if changed:
            raise RuntimeError("Protected files changed: " + ", ".join(changed[:20]))


if __name__ == "__main__":
    main()
