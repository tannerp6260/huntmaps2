"""Isolated immutable artifacts, atomic publication and checked cache reads."""

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

ROOT = Path(__file__).resolve().parents[1]


class IntegrityError(ValueError):
    """Corrupt input/cache is a failed calculation, never an empty success."""

    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def identity(path):
    p = Path(path)
    s = p.stat()
    return (
        str(p.resolve()),
        s.st_dev,
        s.st_ino,
        s.st_size,
        s.st_mtime_ns,
        s.st_ctime_ns,
    )


@lru_cache(maxsize=2048)
def _verified(stamp, expected):
    if file_hash(stamp[0]) != expected:
        raise IntegrityError(
            f"Source/cache checksum mismatch: {stamp[0]}. Restore exact bytes or import a new version; retained files were not replaced."
        )
    return True


def verify(path, expected):
    if not expected or len(expected) != 64:
        raise IntegrityError(f"Missing SHA-256 identity: {path}")
    _verified(identity(path), expected)


def read(path, default=None):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default


def atomic(path, value, binary=False):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_name(p.name + "." + uuid.uuid4().hex + ".partial")
    data = value if binary else json.dumps(value, indent=2, allow_nan=False).encode()
    with temp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    temp.replace(p)


def seal(path):
    atomic(str(path) + ".seal.json", {"sha256": file_hash(path)})


def checked(path):
    spec = read(str(path) + ".seal.json")
    if not spec:
        raise IntegrityError(
            f"Incomplete cache: {path}. Retry this job; completed independent artifacts remain reusable."
        )
    verify(path, spec["sha256"])
    return path


def implementation():
    return digest(
        {
            str(p.relative_to(ROOT)): file_hash(p)
            for p in sorted((ROOT / "trail_scout").glob("*.py"))
        }
        | {"habitat.py": file_hash(ROOT / "huntmaps_gui/habitat.py")}
    )


class StateLease:
    """One live server/headless writer per state, independent of its TCP port."""

    def __init__(self, state):
        self.path = Path(state) / "application.lock"
        self.file = self.path.open("a+")
        try:
            fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.file.close()
            raise ValueError(
                f"TrailScout state is already open by another process: {state}. Use the running server, stop its own terminal, or choose a separate --state. No jobs were changed."
            ) from None
        self.file.seek(0)
        self.file.truncate()
        self.file.write(
            json.dumps(dict(pid=os.getpid(), opened_utc=now(), app="TrailScout"))
        )
        self.file.flush()
        os.fsync(self.file.fileno())

    def close(self):
        if not self.file.closed:
            fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


@dataclass(frozen=True)
class Paths:
    source: Path = Path("/home/tanner/Desktop/huntmaps2")
    state: Path = ROOT / ".trailscout"

    def __post_init__(self):
        for name in ("source", "state"):
            object.__setattr__(self, name, Path(getattr(self, name)).resolve())
        if (
            self.state == self.source
            or self.state.is_relative_to(self.source / ".gui")
            or any(
                self.state.is_relative_to(self.source / p)
                for p in ("data", "runs", "results")
            )
        ):
            raise ValueError(
                "TrailScout state must be separate from owner data, runs, results and .gui"
            )
        if not (self.source / "data/unit-packs/catalog.json").is_file():
            raise ValueError(
                f"Prepared data root missing at {self.source}; set TRAILSCOUT_SOURCE_ROOT explicitly. No empty replacement created."
            )
        self.state.mkdir(parents=True, exist_ok=True)

    def space(self, additional=0):
        if shutil.disk_usage(self.state).free - additional < 20 * 1024**3:
            raise ValueError(
                "Preparation must retain the existing 20 GiB free-space reserve"
            )
        used = sum(p.stat().st_size for p in self.state.rglob("*") if p.is_file())
        if used + additional > 2 * 1024**3:
            raise ValueError(
                "TrailScout's 2 GiB local budget would be exceeded; retain prior work and choose a smaller corridor or a new explicitly budgeted state directory"
            )

    def artifact(self, category, token):
        if (
            not token
            or any(c not in "0123456789abcdef" for c in token)
            or len(token) not in (32, 64)
        ):
            raise ValueError("Invalid artifact identity")
        return self.state / category / token
