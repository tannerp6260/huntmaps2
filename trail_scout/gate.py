"""Complete additive-app gate; all test servers/state are isolated and retained."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from .storage import ROOT, atomic


def main():
    out = Path(tempfile.mkdtemp(prefix="trailscout-gate-"))
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
    )
    node_modules = (ROOT / "trail_scout/web/node_modules").resolve()
    results = []

    def check(name, args, extra=None):
        print(name, flush=True)
        start = time.perf_counter()
        with (out / (name + ".log")).open("w") as log:
            result = subprocess.run(
                args,
                cwd=ROOT,
                env={**env, **(extra or {})},
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        results.append(
            dict(
                stage=name,
                exit_code=result.returncode,
                seconds=time.perf_counter() - start,
            )
        )
        atomic(out / "gate.json", dict(results=results, evidence=str(out)))
        if result.returncode:
            raise RuntimeError(f'{name} failed; inspect {out/(name+".log")}')

    check("python-format", [sys.executable, "-m", "black", "--check", "trail_scout"])
    check(
        "frontend-format",
        [
            "node",
            str(node_modules / "prettier/bin/prettier.cjs"),
            "--check",
            "trail_scout/web/src",
        ],
    )
    check("build", [str(ROOT / "trailscout"), "build"])
    check(
        "backend",
        [sys.executable, "-m", "unittest", "discover", "-s", "trail_scout/tests", "-v"],
    )
    check(
        "legacy-compatibility",
        [
            sys.executable,
            "-m",
            "unittest",
            "test_gui_habitat",
            "test_gui_unit_packs",
            "-v",
        ],
        dict(
            PYTHONPATH="tests",
            HUNTMAPS_SOURCE_DIR=str(ROOT),
            HUNTMAPS_STATE_DIR=str(out / "legacy-state"),
            HUNTMAPS_WORKSPACE=str(out / "legacy-workspace"),
        ),
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    log = (out / "server.log").open("w")
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "trail_scout.app",
            "serve",
            "--state",
            str(out / "browser-state"),
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 30
        while True:
            try:
                urllib.request.urlopen(base + "/api/health", timeout=1).close()
                break
            except OSError:
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Isolated browser server failed to start")
                time.sleep(0.1)
        check(
            "browser",
            ["node", "trail_scout/checks/browser.mjs"],
            dict(TRAILSCOUT_URL=base, TRAILSCOUT_SCREENSHOTS=str(out / "browser")),
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
        log.close()
    print("PASSED. Evidence:", out, flush=True)


if __name__ == "__main__":
    main()
