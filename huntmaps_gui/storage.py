"""Crash-safe JSON persistence with locked transactions and recoverable migration."""

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid
import math
import threading
from .config import STATE

VERSION = 1


_locks = {}
_guard = threading.Lock()
_held = threading.local()


@contextmanager
def locked(path):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _guard:
        mutex = _locks.setdefault(str(path), threading.RLock())
    with mutex:
        held = getattr(_held, "paths", set())
        if path in held:
            yield
            return
        with path.with_name(path.name + ".lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            _held.paths = held | {path}
            try:
                yield
            finally:
                _held.paths = held
                fcntl.flock(handle, fcntl.LOCK_UN)


def atomic_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, indent=2, allow_nan=False) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix="." + path.name + "-", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_json(path, default=None):
    path = Path(path)
    try:
        with path.open() as handle:
            value = json.load(handle)
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as error:
        raise ValueError(
            f"Cannot read {path}: {error}. Preserve this file and restore a backup in Storage; no records were reset."
        ) from error
    if isinstance(value, dict) and "_store_version" in value:
        if value["_store_version"] != VERSION or not isinstance(
            value.get("records"), dict
        ):
            raise ValueError(
                f"Unsupported or damaged record schema in {path}. Restore a compatible backup; no records were reset."
            )
        validate(path, value["records"])
        return value["records"]
    if durable(path):
        validate(path, value)
    return value


def durable(path):
    path = Path(path)
    return path.parent.name in ("annotations", "manual-observers") or (
        path.name == "state.json" and path.parent.parent.name == "working-waypoints"
    )


def validate(path, records):
    if not isinstance(records, dict):
        raise ValueError(
            f"Invalid records in {path}; expected an object. Restore a backup."
        )
    if Path(path).name == "state.json":
        if not all(isinstance(records.get(k), dict) for k in ("overrides", "pending")):
            raise ValueError(
                f"Invalid waypoint state in {path}; overrides and pending must be objects."
            )
        for key, record in records["overrides"].items():
            if (
                not isinstance(record, dict)
                or record.get("id") != key
                or not isinstance(record.get("revision"), str)
            ):
                raise ValueError(
                    f"Invalid working waypoint identity or revision in {path}; restore a backup."
                )
            validate_coordinates(path, record)
        for key, record in records["pending"].items():
            if (
                not isinstance(record, dict)
                or not all(
                    isinstance(record.get(field), str)
                    for field in ("job_id", "revision", "status")
                )
                or not isinstance(record.get("proposal"), dict)
            ):
                raise ValueError(
                    f"Invalid pending waypoint in {path}; restore or retry the update."
                )
    else:
        for key, record in records.items():
            if not isinstance(key, str) or not isinstance(record, dict):
                raise ValueError(
                    f"Invalid record in {path}; preserve the file and restore a backup."
                )
            if Path(path).parent.name == "manual-observers":
                if record.get("id") != key:
                    raise ValueError(
                        f"Invalid manual waypoint identity in {path}; restore a backup."
                    )
                validate_coordinates(path, record)
            if "status" in record and record["status"] not in (
                "unmarked",
                "keep",
                "reject",
                "needs inspection",
            ):
                raise ValueError(
                    f"Invalid review decision in {path}; restore a backup."
                )
            if "notes" in record and not isinstance(record["notes"], str):
                raise ValueError(f"Invalid notes in {path}; expected text.")


def validate_coordinates(path, record):
    for field, bound in [("longitude", 180), ("latitude", 90)]:
        value = record.get(field)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or abs(value) > bound
        ):
            raise ValueError(
                f"Invalid {field} in {path}; restore a backup. No coordinates were changed."
            )


def write(path, value):
    path = Path(path)
    if durable(path):
        validate(path, value)
        if path.exists():
            old = json.loads(path.read_text())
            if not isinstance(old, dict) or "_store_version" not in old:
                # Validate and retain the exact legacy bytes before replacing them.
                validate(path, old)
                backup = path.with_name(
                    path.name + ".legacy-" + uuid.uuid4().hex + ".bak"
                )
                shutil.copy2(path, backup)
            elif old["_store_version"] != VERSION:
                raise ValueError(
                    f"Unsupported record version in {path}; migration refused."
                )
        value = dict(_store_version=VERSION, records=value)
    atomic_write(path, value)


@contextmanager
def transaction(path, default=None):
    with locked(STATE / "maintenance"), locked(path):
        value = read_json(path, default)
        if durable(path):
            validate(path, value)
        yield value
        write(path, value)


def migrate_records():
    """Upgrade valid legacy records; damaged files stay untouched for recovery."""
    paths = [
        *(STATE / "annotations").glob("*.json"),
        *(STATE / "manual-observers").glob("*.json"),
        *(STATE / "working-waypoints").glob("*/state.json"),
    ]
    errors = []
    with locked(STATE / "maintenance"):
        for path in paths:
            try:
                value = read_json(path)
                raw = json.loads(path.read_text())
                if "_store_version" not in raw:
                    with locked(path):
                        write(path, value)
            except (OSError, ValueError) as error:
                errors.append(str(error))
    return errors
