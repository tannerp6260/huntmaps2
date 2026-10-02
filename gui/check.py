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


def owner_records():
    from .preservation import digest

    files = []
    for folder in (
        "annotations",
        "manual-observers",
        "networks",
        "approaches",
        "filter-profiles",
        "first-person/ready",
        "first-person/bundles",
    ):
        files.extend(
            path for path in (ROOT / ".gui" / folder).rglob("*") if path.is_file()
        )
    files.extend((ROOT / ".gui/working-waypoints").glob("*/state.json"))
    files.extend((ROOT / ".gui/jobs").glob("*.json"))
    return {str(path): digest(path) for path in files}


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
        PYTHONDONTWRITEBYTECODE="1",
        HUNTMAPS_SCREENSHOTS=str(work / "screenshots"),
        HUNTMAPS_IMPORT_FILE=str(ROOT / "inputs/test.kml"),
        HUNTMAPS_SCENE_SOURCE=str(ROOT / ".gui/first-person"),
        HUNTMAPS_BROWSER=os.environ.get("HUNTMAPS_BROWSER", "/usr/bin/google-chrome"),
    )
    (work / "workspace").mkdir()
    from .preservation import audit

    changed = audit()
    if changed:
        raise RuntimeError("Protected baseline differs: " + ", ".join(changed[:20]))
    before = inventory()
    owner_before = owner_records()
    process = None
    companion = None
    companion_log = None
    companion_snapshot = None
    companion_state = work / "companion-state"

    def run(command, label, cwd=ROOT):
        print(label, flush=True)
        with (work / (label + ".log")).open("w") as log:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=600,
            )
        if result.returncode:
            print((work / (label + ".log")).read_text()[-12000:], flush=True)
            raise RuntimeError(label + " failed")

    try:
        patterns = [
            "test_gui*.py",
            "test_approach*.py",
            "test_scouting_filters.py",
            "test_first_person.py",
            "test_vegetation_screen.py",
            "test_nearby_foliage.py",
            "test_foliage_clusters.py",
            "test_nearby_observer.py",
            "test_working_waypoints.py",
            "test_owner.py",
            "test_vegetation_rays.py",
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
        run(
            [
                sys.executable,
                "-m",
                "black",
                "--check",
                "huntmaps_gui",
                "gui/check.py",
                "gui/preservation.py",
            ],
            "python-format",
        )
        run(["npm", "run", "format:check"], "frontend-format", ROOT / "gui/frontend")
        run(["npm", "run", "build"], "frontend-build", ROOT / "gui/frontend")
        if not args.skip_browser:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            env["HUNTMAPS_URL"] = f"http://127.0.0.1:{port}"
            # A second live app represents normal use while verification mutates
            # its own state. Seed a review and audit this companion's exact bytes.
            from huntmaps_gui.storage import atomic_write

            sentinel = companion_state / "annotations/soap-creek-v1.json"
            atomic_write(
                sentinel,
                dict(
                    _store_version=1,
                    records={
                        "A0075": {"status": "keep", "notes": "Concurrent app sentinel"}
                    },
                ),
            )
            with socket.socket() as other_socket:
                other_socket.bind(("127.0.0.1", 0))
                other_port = other_socket.getsockname()[1]
            companion_log = (work / "companion.log").open("w")
            companion = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "huntmaps_gui",
                    "--no-browser",
                    "--port",
                    str(other_port),
                    "--state-dir",
                    str(companion_state),
                    "--test-workspace",
                    str(work / "workspace"),
                ],
                cwd=ROOT,
                env=env,
                stdout=companion_log,
                stderr=subprocess.STDOUT,
            )
            for _ in range(100):
                if companion.poll() is not None:
                    raise RuntimeError("Concurrent app failed; inspect companion.log")
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{other_port}/api/runs", timeout=0.5
                    ):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Concurrent app timeout")
            from .preservation import digest

            companion_snapshot = {
                str(path): digest(path)
                for path in companion_state.rglob("*")
                if path.is_file()
            }

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
                "browser-storage-check.mjs",
                "browser-scouting-check.mjs",
                "browser-network-compat-check.mjs",
                "browser-performance-check.mjs",
                "browser-clusters-check.mjs",
                "browser-nearby-observer-check.mjs",
            ):
                env["HUNTMAPS_SCREENSHOTS"] = str(
                    work / "screenshots" / script.removesuffix(".mjs")
                )
                run(
                    ["node", script], script.removesuffix(".mjs"), ROOT / "gui/frontend"
                )
        if process is not None:
            (work / "server-memory.txt").write_text(
                Path(f"/proc/{process.pid}/status").read_text()
            )
        print("Checks passed. Diagnostics: " + str(work), flush=True)
    finally:
        if companion is not None:
            companion.terminate()
            try:
                companion.wait(timeout=15)
            except subprocess.TimeoutExpired:
                companion.kill()
                companion.wait()
            companion_log.close()
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            server_log.close()
        after = inventory()
        content_changed = audit()
        owner_after = owner_records()
        owner_changed = [
            path
            for path in owner_before.keys() | owner_after.keys()
            if owner_before.get(path) != owner_after.get(path)
        ]
        content_changed.extend(owner_changed)
        if companion_snapshot is not None:
            companion_after = {
                str(path): digest(path)
                for path in companion_state.rglob("*")
                if path.is_file()
            }
            content_changed.extend(
                path
                for path in companion_snapshot.keys() | companion_after.keys()
                if companion_snapshot.get(path) != companion_after.get(path)
            )
        changed = [
            path
            for path in before.keys() | after.keys()
            if before.get(path) != after.get(path)
        ]
        changed = sorted(set(changed + content_changed))
        (work / "protected-audit.json").write_text(
            json.dumps(dict(files=len(before), changed=changed), indent=2)
        )
        print("Diagnostics retained: " + str(work), flush=True)
        if changed:
            raise RuntimeError("Protected files changed: " + ", ".join(changed[:20]))


if __name__ == "__main__":
    main()
