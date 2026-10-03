"""Explicit record recovery and conservative regenerable-cache maintenance."""

import hashlib
import json
from pathlib import Path
import shutil
import time
import uuid
from fastapi import APIRouter, Request
from pydantic import BaseModel
from .config import STATE, current
from .storage import locked, read_json, write, atomic_write, validate
from .jobs import ACTIVE

router = APIRouter(prefix="/api/storage")


def records():
    return sorted(
        [
            *(STATE / "workflows").glob("*.json"),
            *(STATE / "first-person/ready").rglob("*.json"),
            *(STATE / "annotations").glob("*.json"),
            *(STATE / "manual-observers").glob("*.json"),
            *(STATE / "working-waypoints").glob("*/state.json"),
            *(STATE / "filter-profiles").glob("*.json"),
            *(STATE / "approaches").glob("*/*.json"),
            *(STATE / "networks").glob("*/*"),
        ]
    )


def backup():
    key = uuid.uuid4().hex
    folder = STATE / "backups" / key
    folder.mkdir(parents=True)
    for path in records():
        dest = folder / path.relative_to(STATE.resolve())
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    atomic_write(
        folder / "backup.json",
        dict(
            id=key,
            created=time.time(),
            files=[str(p.relative_to(STATE.resolve())) for p in records()],
        ),
    )
    return key


@router.get("")
def status(request: Request = None):
    problems = (
        list(request.app.state.jobs.storage_errors) if request is not None else []
    )
    for path in [
        *(p for p in records() if p.suffix == ".json"),
        *(STATE / "jobs").glob("*.json"),
    ]:
        try:
            read_json(path)
        except ValueError as error:
            problems.append(str(error))
    return dict(
        state_dir=str(STATE),
        records=len(records()),
        problems=problems,
        backups=[read_json(p) for p in (STATE / "backups").glob("*/backup.json")],
    )


@router.post("/backup")
def create_backup():
    with locked(STATE / "maintenance"):
        return dict(backup=backup())


class Reset(BaseModel):
    confirmation: str


@router.post("/reset")
def reset(body: Reset):
    if body.confirmation != "RESET GUI RECORDS":
        raise ValueError(
            "Type RESET GUI RECORDS to reset notes and waypoints. A backup will be retained."
        )
    with locked(STATE / "maintenance"):
        ensure_idle()
        key = backup()
        for path in records():
            if (
                path.is_relative_to(STATE / "workflows")
                or path.is_relative_to(STATE / "first-person")
                or path.is_relative_to(STATE / "approaches")
                or path.is_relative_to(STATE / "networks")
                or path.is_relative_to(STATE / "filter-profiles")
            ):
                continue
            # Explicit reset is also available for damaged records; retain exact bytes.
            atomic_write(
                path,
                dict(
                    _store_version=1,
                    records=(
                        dict(overrides={}, pending={})
                        if path.name == "state.json"
                        else {}
                    ),
                ),
            )
        return dict(backup=key, reset=True)


class Restore(BaseModel):
    backup: str


@router.post("/restore")
def restore(body: Restore):
    if len(body.backup) != 32 or any(c not in "0123456789abcdef" for c in body.backup):
        raise ValueError("Choose a listed backup")
    with locked(STATE / "maintenance"):
        ensure_idle()
        folder = STATE / "backups" / body.backup
        info = read_json(folder / "backup.json")
        if info is None:
            raise ValueError("Backup not found")
        restored = {}
        for relative in info["files"]:
            source = folder / relative
            target = STATE / relative
            if not source.resolve().is_relative_to(
                folder.resolve()
            ) or not target.resolve().is_relative_to(STATE.resolve()):
                raise ValueError("Invalid backup path")
            if any(
                part
                in (
                    "approaches",
                    "networks",
                    "filter-profiles",
                    "workflows",
                    "first-person",
                )
                for part in target.relative_to(STATE.resolve()).parts
            ):
                restored[target] = source.read_bytes()
                continue
            value = read_json(source)
            validate(target, value)
            if target.name == "state.json":
                value = dict(value, pending={})
            restored[target] = value
        key = backup()
        for target, value in restored.items():
            # Restore may replace malformed current records, with their bytes backed up.
            if isinstance(value, bytes):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(value)
            else:
                atomic_write(target, dict(_store_version=1, records=value))
        return dict(restored=len(restored), backup=key)


def ensure_idle():
    for path in (STATE / "jobs").glob("*.json"):
        if read_json(path)["status"] in ACTIVE:
            raise ValueError(
                "Wait for the active job or cancel it before storage maintenance."
            )


def inventory():
    protected = {
        p.parent.name
        for p in (STATE / "first-person/bundles").glob("*/scene.json")
        if read_json(p).get("status") == "ready"
    }
    # Published immutable scenes are retained, including earlier acquisitions.
    # Ready bundles and all recursively referenced base bundles stay available offline.
    queue = [
        read_json(p)["key"] for p in (STATE / "first-person/ready").rglob("*.json")
    ]
    for path in (STATE / "workflows").glob("*.json"):
        for record in read_json(path).get("points", {}).values():
            if record.get("viewed"):
                queue.append(record["viewed"])
    visited = set()
    queue.extend(protected)
    while queue:
        key = queue.pop()
        if key in visited:
            continue
        visited.add(key)
        if len(key) != 32 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("Invalid ready scene reference; cleanup refused")
        protected.add(key)
        meta = read_json(STATE / "first-person/bundles" / key / "scene.json")
        if meta is None:
            # A read-only source bundle is retained outside the writable cache.
            continue
        queue.extend(meta.get("asset_bundles", {}).values())
        if meta.get("reused_base_bundle"):
            queue.append(meta["reused_base_bundle"])
    revisions = set()
    waypoint_states = list((STATE / "working-waypoints").glob("*/state.json")) + list(
        (STATE / "backups").glob("*/working-waypoints/*/state.json")
    )
    for path in waypoint_states:
        data = read_json(path)
        revisions.update(
            (path.parent.name, p["revision"]) for p in data["overrides"].values()
        )
        revisions.update(
            (path.parent.name, p["revision"]) for p in data["pending"].values()
        )
    active = any(
        read_json(p)["status"] in ACTIVE for p in (STATE / "jobs").glob("*.json")
    )
    items = []

    def add(path, kind, retain):
        if path.is_symlink():
            retain = True
        size = (
            sum(
                p.stat().st_size
                for p in path.rglob("*")
                if p.is_file() and not p.is_symlink()
            )
            if path.is_dir()
            else path.stat().st_size
        )
        items.append(
            dict(
                path=str(path.relative_to(STATE.resolve())),
                kind=kind,
                bytes=size,
                protected=retain or active,
                reason=(
                    "Referenced or active-job asset"
                    if retain or active
                    else "Unreferenced regenerable asset"
                ),
            )
        )

    for path in (STATE / "cache").iterdir() if (STATE / "cache").exists() else []:
        add(path, "display", False)
    for path in (
        (STATE / "first-person/bundles").iterdir()
        if (STATE / "first-person/bundles").exists()
        else []
    ):
        add(path, "scene", path.name in protected)
    for path in (
        (STATE / "first-person/partial").iterdir()
        if (STATE / "first-person/partial").exists()
        else []
    ):
        add(path, "partial", False)
    for path in (STATE / "working-waypoints").glob("*/cache/*"):
        add(path, "mask", (path.parent.parent.name, path.name) in revisions)
    for path in (STATE / "working-waypoints").glob("*/partials/*"):
        add(path, "partial", False)
    for path in (STATE / "approaches").glob("*"):
        add(path, "saved approach scenario and referenced results", True)
    for path in (STATE / "networks").glob("*"):
        add(path, "referenced network source", True)
    for path in (STATE / "workflows").glob("*.json"):
        add(path, "saved workflow decisions and referenced results", True)
    for path in (STATE / "filter-profiles").glob("*.json"):
        add(path, "saved filter profile", True)
    return dict(
        items=items,
        total_bytes=sum(v["bytes"] for v in items),
        reclaimable_bytes=sum(v["bytes"] for v in items if not v["protected"]),
        active_job=active,
    )


@router.get("/cache")
def cache_inventory():
    with locked(STATE / "maintenance"):
        return inventory()


@router.post("/cache/preview")
def preview():
    with locked(STATE / "maintenance"):
        value = inventory()
        selected = [v["path"] for v in value["items"] if not v["protected"]]
        token = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        return dict(
            token=token, selected=selected, reclaimable_bytes=value["reclaimable_bytes"]
        )


class Cleanup(BaseModel):
    token: str


@router.post("/cache/cleanup")
def cleanup(body: Cleanup):
    with locked(STATE / "maintenance"):
        ensure_idle()
        value = inventory()
        token = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        if token != body.token:
            raise ValueError("Cache references changed. Preview cleanup again.")
        reclaimed = 0
        for item in value["items"]:
            if item["protected"]:
                continue
            path = STATE / item["path"]
            if not path.resolve().is_relative_to(STATE.resolve()) or path.is_symlink():
                raise ValueError("Cache path leaves writable state; cleanup refused")
            reclaimed += item["bytes"]
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        from . import tiles, terrain, first_person, vegetation_screen, foliage_clusters

        for module in (
            tiles,
            terrain,
            first_person,
            vegetation_screen,
            foliage_clusters,
        ):
            for value in vars(module).values():
                clear = getattr(value, "cache_clear", None)
                if clear:
                    clear()
        return dict(reclaimed_bytes=reclaimed)
