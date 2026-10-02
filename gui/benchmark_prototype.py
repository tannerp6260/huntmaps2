"""Compare scene instrumentation with the preserved prototype in disposable state."""

import io
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", action="store_true")
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="huntmaps-prototype-benchmark-"))
    print("Prototype diagnostics: " + str(work), flush=True)
    if args.current:
        state = work / "state"
        state.mkdir()
    else:
        archive = subprocess.check_output(
            ["git", "archive", "aeecf0b", "huntmaps_gui", "gui/frontend"], cwd=ROOT
        )
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            bundle.extractall(work)
        state = work / "state"
        state.mkdir()
        source = ROOT / ".gui/first-person"
        (state / "first-person").mkdir()
        (state / "first-person/bundles").symlink_to(
            source / "bundles", target_is_directory=True
        )
        (state / "first-person/ready").symlink_to(
            source / "ready", target_is_directory=True
        )
        # Only relocate adapter state and static assets; preserve prototype behavior.
        path = work / "huntmaps_gui/catalog.py"
        text = (
            path.read_text()
            .replace(
                "ROOT = Path(__file__).resolve().parents[1]",
                "ROOT = Path(" + repr(str(ROOT)) + ")",
            )
            .replace("STATE = ROOT / '.gui'", "STATE = Path(" + repr(str(state)) + ")")
        )
        path.write_text(text)
        path = work / "huntmaps_gui/server.py"
        path.write_text(
            path.read_text().replace(
                "dist=ROOT/'gui/frontend/dist'",
                "dist=Path(" + repr(str(work / "gui/frontend/dist")) + ")",
            )
        )
        (work / "gui/frontend/node_modules").symlink_to(
            ROOT / "gui/frontend/node_modules", target_is_directory=True
        )
        with (work / "build.log").open("w") as log:
            subprocess.run(
                ["npm", "run", "build"],
                cwd=work / "gui/frontend",
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(
        os.environ,
        PYTHONPATH=(str(ROOT) if args.current else str(work) + os.pathsep + str(ROOT)),
        HUNTMAPS_STATE_DIR=str(state),
        HUNTMAPS_SOURCE_DIR=str(ROOT),
        HUNTMAPS_WORKSPACE=str(work),
        MPLCONFIGDIR=str(work / "mpl"),
        HUNTMAPS_URL=f"http://127.0.0.1:{port}",
        HUNTMAPS_SCREENSHOTS=str(work / "screenshots"),
    )
    with (work / "server.log").open("w") as log:
        process = subprocess.Popen(
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
            cwd=ROOT if args.current else work,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError("Prototype server failed: " + str(work))
                try:
                    with urllib.request.urlopen(
                        env["HUNTMAPS_URL"] + "/api/runs", timeout=0.5
                    ):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Prototype server timeout: " + str(work))
            subprocess.run(
                ["node", "browser-performance-check.mjs"],
                cwd=ROOT / "gui/frontend",
                env=env,
                check=True,
                timeout=180,
            )
            (work / "server-memory.txt").write_text(
                Path(f"/proc/{process.pid}/status").read_text()
            )
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    print(("Current" if args.current else "Prototype") + " measurements: " + str(work))


if __name__ == "__main__":
    main()
