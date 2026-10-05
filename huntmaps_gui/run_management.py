"""Reviewed management of generated runs; never delete frozen or shared inputs."""

import hashlib
import json
import re
import shutil
from pathlib import Path
from .config import STATE, SOURCE, WORKSPACE
from .storage import read_json, write, locked
from .maintenance import ensure_idle


def records():
    value = read_json(STATE / "run-management.json", dict(version=1, runs={}))
    if value.get("version") != 1 or not isinstance(value.get("runs"), dict):
        raise ValueError("Invalid run management records; restore a compatible backup")
    return value


def entries():
    from .catalog import runs

    saved = records()["runs"]
    return [
        dict(r, archived=bool(saved.get(r["id"], {}).get("archived"))) for r in runs()
    ]


def archive(ident, archived):
    if type(archived) is not bool:
        raise ValueError("Choose archive or unarchive")
    if ident not in [r["id"] for r in entries()]:
        raise ValueError("Unknown saved run")
    with locked(STATE / "maintenance"):
        value = records()
        value["runs"][ident] = dict(archived=archived)
        write(STATE / "run-management.json", value)
    return entries()


def preview(ident):
    from .catalog import Run, runs

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", ident):
        raise ValueError("Invalid run identifier")
    run = Run(ident)
    folder = run.base
    protected = read_json(Path(SOURCE) / "docs/gui/CLEANUP_PRESERVED.json", {}).get(
        "sha256", {}
    )
    if run.experimental or folder.is_symlink() or not run.config.get("normal_scouting"):
        raise ValueError(
            "Historical controls and supplied results cannot be deleted; archive instead"
        )
    if any((Path(SOURCE) / name).is_relative_to(folder) for name in protected):
        raise ValueError(
            "This run contains protected historical evidence; archive instead"
        )
    allowed = [
        Path(SOURCE).resolve() / "results",
        Path(WORKSPACE).resolve() / "results",
    ]
    if folder.parent.resolve() not in allowed:
        raise ValueError("Run is outside the permitted generated results directory")
    for entry in runs():
        if entry["id"] == ident:
            continue
        other = Run(entry["id"])
        if any(Path(p).is_relative_to(folder) for p in other.hashes):
            raise ValueError(
                f"Run {entry['id']} references these outputs; archive instead"
            )
    candidates = [folder]
    for group, suffix in [
        ("workflows", ".json"),
        ("approach-reviews", ".json"),
        ("annotations", ".json"),
        ("manual-observers", ".json"),
        ("working-waypoints", ""),
        ("filter-profiles", ""),
        ("first-person/ready", ""),
    ]:
        path = Path(STATE) / group / (ident + suffix)
        if path.exists():
            candidates.append(path)
    for path in (Path(STATE) / "approaches").glob("*/scenario.json"):
        if read_json(path, {}).get("run_id") == ident:
            candidates.append(path.parent)
    # Plans may retain references to this run; deleting the run is an explicit removal
    # of its workflow, not permission to delete their source inputs or ready bundles.
    file_records = []
    for path in candidates:
        paths = path.rglob("*") if path.is_dir() else [path]
        if path.is_symlink():
            raise ValueError("Symlink in deletion inventory; archive instead")
        for item in paths:
            if item.is_symlink():
                raise ValueError("Symlink in deletion inventory; archive instead")
            if item.is_file():
                digest = hashlib.sha256()
                with item.open("rb") as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(block)
                file_records.append(
                    (str(item), item.stat().st_size, digest.hexdigest())
                )
    file_records.sort()
    token = hashlib.sha256(json.dumps(file_records).encode()).hexdigest()
    return dict(
        run=ident,
        token=token,
        paths=[str(p) for p in candidates],
        bytes=sum(p[1] for p in file_records),
        files=len(file_records),
        retained="Shared source data, prepared scene bundles, supplied inputs and historical controls remain retained.",
    )


def delete(ident, token):
    with locked(STATE / "maintenance"):
        ensure_idle()
        value = preview(ident)
        if not isinstance(token, str) or token != value["token"]:
            raise ValueError("Saved results changed; review deletion again")
        for name in value["paths"]:
            path = Path(name)
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        saved = records()
        saved["runs"].pop(ident, None)
        write(STATE / "run-management.json", saved)
        from .catalog import static_json, check_hash

        static_json.cache_clear()
        check_hash.cache_clear()
    return dict(deleted=ident, reclaimed_bytes=value["bytes"])
