"""Durable, throttled worker progress; counters describe this job, not lifetime totals."""

import os
import math
import time
import threading
from collections import deque
from pathlib import Path
from urllib.parse import urlparse
from .config import current
from .storage import write, read_json, locked

_lock = threading.RLock()
_samples = deque()
_last_write = 0.0


def progress_path():
    value = os.environ.get("HUNTMAPS_PROGRESS_FILE")
    return Path(value) if value else None


def recent_rate(provider):
    p = current().state_dir / "transfer-rates.json"
    try:
        value = read_json(p, {}).get(provider, {})
        rate = value.get("bytes_per_s")
        age = time.time() - value.get("updated", 0)
        if (
            not 0 <= age <= 7 * 86400
            or type(rate) not in (int, float)
            or not math.isfinite(rate)
            or rate <= 0
        ):
            return None
        return rate
    except (ValueError, TypeError, AttributeError):
        return None


def emit(phase, label, completed=0, total=None, force=False, **extra):
    global _last_write
    path = progress_path()
    if path is None:
        return
    with _lock, locked(path):
        previous = read_json(path, {})
        now = time.time()
        value = dict(
            previous,
            phase=phase,
            label=label,
            completed=completed,
            total=total,
            updated=now,
            phase_started=(
                extra.pop(
                    "phase_started",
                    (
                        previous.get("phase_started", now)
                        if previous.get("phase") == phase
                        else now
                    ),
                )
            ),
            **extra
        )
        if phase != "download":
            value.pop("bytes_per_s", None)
            if "remaining_s" not in extra:
                value.pop("remaining_s", None)
        if force or now - _last_write >= 1:
            write(path, value)
            _last_write = now


def start_download(total):
    global _last_write
    _samples.clear()
    _last_write = 0
    for name in (
        "path",
        "phase_started",
        "completed",
        "total",
        "bytes_per_s",
        "remaining_s",
        "provider",
    ):
        if hasattr(received, name):
            delattr(received, name)
    emit(
        "download",
        "Downloading reviewed sources",
        0,
        total,
        force=True,
        phase_started=time.time(),
        bytes_per_s=None,
        remaining_s=None,
    )


def received(count, url):
    """Called after a network read, before publication; shared range threads serialize."""
    global _last_write
    path = progress_path()
    if path is None:
        return
    with _lock:
        value = read_json(path, {})
        now = time.time()
        completed = value.get("completed", 0) + count
        # Persist actual accounting every read in memory; flush at most once a second.
        # Independent child processes inherit the sidecar, reading its latest saved count.
        if getattr(received, "path", None) != path or getattr(
            received, "phase_started", None
        ) != value.get("phase_started"):
            received.completed = value.get("completed", 0)
            received.path = path
            received.phase_started = value.get("phase_started")
        received.completed = max(received.completed, value.get("completed", 0)) + count
        completed = received.completed
        provider = urlparse(url).hostname
        if getattr(received, "provider", None) != provider:
            _samples.clear()
            received.provider = provider
        if not _samples:
            _samples.append((now, completed - count))
        _samples.append((now, completed))
        while len(_samples) > 2 and now - _samples[1][0] > 30:
            _samples.popleft()
        duration = now - _samples[0][0]
        rate = (completed - _samples[0][1]) / duration if duration >= 3 else None
        total = value.get("total")
        if total is not None and completed > total:
            total = None
        eta = max(0, total - completed) / rate if total is not None and rate else None
        received.total = total
        received.bytes_per_s = rate
        received.remaining_s = eta
        if now - _last_write >= 1:
            emit(
                "download",
                "Downloading reviewed sources",
                completed,
                total,
                force=True,
                bytes_per_s=rate,
                remaining_s=eta,
                provider=urlparse(url).hostname,
            )
            if rate and duration >= 5:
                history = current().state_dir / "transfer-rates.json"
                with locked(history):
                    records = read_json(history, {})
                    records[urlparse(url).hostname] = dict(
                        bytes_per_s=rate, updated=now
                    )
                    write(history, records)


def flush_download():
    path = progress_path()
    if path is None:
        return
    with _lock:
        value = read_json(path, {})
        if value.get("phase") == "download":
            same = getattr(received, "path", None) == path and getattr(
                received, "phase_started", None
            ) == value.get("phase_started")
            completed = max(
                getattr(received, "completed", 0) if same else 0,
                value.get("completed", 0),
            )
            total = (
                getattr(received, "total", value.get("total"))
                if same
                else value.get("total")
            )
            emit(
                "download",
                value.get("label", "Downloading"),
                completed,
                total,
                force=True,
                bytes_per_s=(
                    getattr(received, "bytes_per_s", value.get("bytes_per_s"))
                    if same
                    else value.get("bytes_per_s")
                ),
                remaining_s=(
                    getattr(received, "remaining_s", value.get("remaining_s"))
                    if same
                    else value.get("remaining_s")
                ),
            )
