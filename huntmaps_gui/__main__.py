"""Launch one localhost server and open the locally served frontend."""

import argparse
import fcntl
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from .config import AppConfig, configured, PROJECT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--preflight",
        action="store_true",
        help="Check setup without starting the server",
    )
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--state-dir", type=Path, default=PROJECT / ".gui")
    ap.add_argument("--test-workspace", type=Path, help=argparse.SUPPRESS)
    a = ap.parse_args()
    config = AppConfig(state_dir=a.state_dir, workspace=a.test_workspace or PROJECT)
    os.environ.update(config.environment())
    if a.preflight:
        from .preflight import check
        import json

        report = check(a.port)
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 2
    if not 1 <= a.port <= 65535:
        raise SystemExit("Use a port from 1 to 65535")
    try:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", a.port))
    except OSError as error:
        raise SystemExit(
            f"Cannot bind 127.0.0.1:{a.port}: {error}. Choose --port with a free port."
        )
    ROOT = config.source_dir
    STATE = config.state_dir
    os.chdir(ROOT)
    STATE.mkdir(parents=True, exist_ok=True)
    lock = (STATE / "server.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(
            f"HuntMaps GUI already uses this state directory. Open http://127.0.0.1:{a.port} or use --state-dir for an isolated instance."
        )
    if not (ROOT / "gui/frontend/dist/index.html").exists():
        raise SystemExit(
            "Build local assets first: npm ci --prefix gui/frontend && npm run build --prefix gui/frontend"
        )
    import uvicorn

    url = f"http://127.0.0.1:{a.port}"
    print("HuntMaps2:", url, "— Ctrl+C stops the app and its active job.", flush=True)
    if not a.no_browser:

        def browser():
            for _ in range(100):
                try:
                    with socket.create_connection(("127.0.0.1", a.port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            try:
                result = subprocess.run(["xdg-open", url], check=False)
                if result.returncode:
                    print("Browser could not open; visit " + url, flush=True)
            except OSError as error:
                print(f"Browser could not open ({error}); visit {url}", flush=True)

        threading.Thread(target=browser, daemon=True).start()
    uvicorn.run(
        "huntmaps_gui.server:create_app",
        factory=True,
        host="127.0.0.1",
        port=a.port,
        log_level="warning",
    )


if __name__ == "__main__":
    sys.exit(main())
