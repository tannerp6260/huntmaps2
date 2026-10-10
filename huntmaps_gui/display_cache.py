"""Bound only regenerable display files; never evict scene or waypoint records."""

from functools import wraps
from contextlib import contextmanager
import threading
import os
import time
from pathlib import Path
from .config import STATE, current
from .storage import locked, read_json, write
from .jobs import ACTIVE


_pins = {}
_pin_lock = threading.RLock()
_checked = {}
_dirty = set()


def generation():
    marker = STATE / "display-cache.generation"
    try:
        stat = marker.stat()
        return stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns
    except FileNotFoundError:
        return None


def changed():
    """Call under maintenance lock before creating/replacing display assets."""
    _dirty.add(STATE.resolve())
    # Other processes must also notice growth, including a writer that exits
    # while eviction is paused for an active job. A stat replaces a full scan.
    marker = STATE / "display-cache.generation"
    marker.touch()
    now = time.time_ns()
    os.utime(marker, ns=(now, now))


def maybe_evict():
    """Hits cannot grow the cache. Scan on writes, first use or a budget change."""
    key = (STATE.resolve(), current().display_budget_bytes)
    if key not in _checked or _checked[key] != generation() or key[0] in _dirty:
        return evict()
    return 0


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


def remember(folder, run, cid, viewed):
    """Display ownership is disposable metadata, never an analysis/decision record."""
    marker = folder / ".coverage-owner.json"
    old = read_json(marker, {})
    value = dict(run=run, cid=cid, viewed=bool(viewed or old.get("viewed")))
    if old != value:
        folder.mkdir(parents=True, exist_ok=True)
        changed()
        write(marker, value)


def evict():
    with locked(STATE / "maintenance"):
        return _evict()


def _evict():
    state = STATE.resolve()
    if any(read_json(p)["status"] in ACTIVE for p in (STATE / "jobs").glob("*.json")):
        _dirty.add(state)  # Retry once the job is idle, including on a cached hit.
        return 0
    files = [
        p for p in (STATE / "cache").rglob("*") if p.is_file() and not p.is_symlink()
    ]
    total = sum(p.stat().st_size for p in files)
    _dirty.discard(state)
    if len(_checked) > 128:
        _checked.clear()
    _checked[(state, current().display_budget_bytes)] = generation()
    if total <= current().display_budget_bytes:
        return 0  # Ownership/decision reads and sorting are only for eviction.
    reclaimed = 0
    owners, decisions = {}, {}

    def priority(path):
        folder = path.parent
        if folder not in owners:
            owners[folder] = read_json(folder / ".coverage-owner.json", {})
        owner = owners[folder]
        run = owner.get("run")
        if not isinstance(run, str) or "/" in run or "\\" in run or run in (".", ".."):
            return (1, path.name == ".coverage-owner.json", path.stat().st_atime_ns)
        if run not in decisions:
            decisions[run] = read_json(STATE / "workflows" / (run + ".json"), {}).get(
                "points", {}
            )
        dismissed = decisions[run].get(owner.get("cid"), {}).get("dismissed", False)
        return (
            0 if dismissed else 2 if owner.get("viewed") else 1,
            path.name == ".coverage-owner.json",
            path.stat().st_atime_ns,
        )

    for path in sorted(files, key=priority):
        if total <= current().display_budget_bytes:
            break
        with _pin_lock:
            if path in _pins:
                continue
            size = path.stat().st_size
            path.unlink()
        total -= size
        reclaimed += size
    if total > current().display_budget_bytes:
        _dirty.add(state)  # Pinned files can outlive this request.
    return reclaimed


def bounded(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with locked(STATE / "maintenance"):
            result = function(*args, **kwargs)
            maybe_evict()
            return result

    return wrapped
