"""Bound only regenerable display files; never evict scene or waypoint records."""

from functools import wraps
from contextlib import contextmanager
import threading
import os
import time
from pathlib import Path
from .config import STATE, current
from .storage import locked, read_json
from .jobs import ACTIVE


_pins = {}
_pin_lock = threading.RLock()


@contextmanager
def pin(paths):
    with _pin_lock:
        for path in paths:
            _pins[path] = _pins.get(path, 0) + 1
    try:
        yield
    finally:
        with _pin_lock:
            for path in paths:
                _pins[path] -= 1
                if not _pins[path]:
                    del _pins[path]


def touch(path):
    path = Path(path)
    if path.is_relative_to(STATE / "cache") and path.exists():
        stat = path.stat()
        os.utime(path, ns=(time.time_ns(), stat.st_mtime_ns))


def evict():
    if any(read_json(p)["status"] in ACTIVE for p in (STATE / "jobs").glob("*.json")):
        return 0
    files = [
        p for p in (STATE / "cache").rglob("*") if p.is_file() and not p.is_symlink()
    ]
    total = sum(p.stat().st_size for p in files)
    reclaimed = 0
    for path in sorted(files, key=lambda p: p.stat().st_atime_ns):
        if total <= current().display_budget_bytes:
            break
        with _pin_lock:
            if path in _pins:
                continue
            size = path.stat().st_size
            path.unlink()
        total -= size
        reclaimed += size
    return reclaimed


def bounded(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with locked(STATE / "maintenance"):
            result = function(*args, **kwargs)
            evict()
            return result

    return wrapped
