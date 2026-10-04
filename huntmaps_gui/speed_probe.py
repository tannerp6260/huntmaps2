"""Small interruptible provider probe; actual transfer rates take precedence."""

import os
import threading
import time
import urllib.request
from pathlib import Path
from .config import current, configured
from .storage import read_json, write, locked

URL = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/n39w108/USGS_13_n39w108.tif"
MAX_BYTES = 2_000_000
DEFAULT_RATE = 2_500_000  # 20 megabits/s, not megabytes/s
_running = set()
_cancel = {}
_guard = threading.Lock()


def estimate_rate():
    value = read_json(current().state_dir / "speed-probe.json", {})
    rate = value.get("bytes_per_s")
    if (
        isinstance(rate, (int, float))
        and rate > 0
        and 0 <= time.time() - value.get("updated", 0) < 86400
    ):
        return rate, "startup probe"
    return DEFAULT_RATE, "20 Mbps default"


def start(jobs):
    config = current()
    path = config.state_dir / "speed-probe.json"
    if os.environ.get("HUNTMAPS_DISABLE_SPEED_PROBE") == "1":
        return dict(status="disabled")
    if any(
        j.get("status") in ("queued", "running", "cancelling")
        for j in jobs.list(include_logs=False)
    ):
        return dict(status="paused")
    with _guard:
        if str(path) in _running:
            return dict(status="running")
        saved = read_json(path, {})
        if time.time() - saved.get("attempted", 0) < 86400:
            return dict(status="recent")
        _running.add(str(path))
        cancel = threading.Event()
        _cancel[str(path)] = cancel

    def measure():
        with configured(config):
            started = time.monotonic()
            total = 0
            result = dict(attempted=time.time(), status="unavailable")
            try:
                # No owner job can start during a read. Foreground work gets priority
                # between small reads; socket waits are bounded to half a second.
                with urllib.request.urlopen(
                    urllib.request.Request(
                        URL,
                        headers={
                            "Range": f"bytes=0-{MAX_BYTES - 1}",
                            "Cache-Control": "no-cache",
                        },
                    ),
                    timeout=0.5,
                ) as response:
                    while total < MAX_BYTES and time.monotonic() - started < 5:
                        if cancel.is_set():
                            result["status"] = "cancelled"
                            break
                        with jobs.lock:
                            if any(
                                j.get("status") in ("queued", "running", "cancelling")
                                for j in jobs.list(include_logs=False)
                            ):
                                result["status"] = "cancelled"
                                break
                            block = response.read(min(65536, MAX_BYTES - total))
                        if not block:
                            break
                        total += len(block)
                    else:
                        result["status"] = "complete"
                elapsed = time.monotonic() - started
                if total >= 256000 and result["status"] != "cancelled":
                    result.update(
                        bytes_per_s=total / max(elapsed, 0.01),
                        updated=time.time(),
                        status="complete",
                    )
            except (OSError, ValueError):
                pass
            finally:
                result["received_bytes"] = total
                write(path, result)
                with _guard:
                    _running.discard(str(path))
                    _cancel.pop(str(path), None)

    threading.Thread(target=measure, daemon=True, name="huntmaps-speed-probe").start()
    return dict(status="started")


def memory_available():
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    return 0


def interrupt():
    with _guard:
        event = _cancel.get(str(current().state_dir / "speed-probe.json"))
        if event:
            event.set()
