"""GUI-only import of verified raw sources into an independent local store."""

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import parse_qs, urlparse

from glassing.acquire import digest
from .acquisition import validate, validating
from .config import STATE, WORKSPACE
from .downloads import check_space
from .storage import locked, read_json, write

KEYS = ("tree", "shrub", "herb", "summer", "winter")


def compatible(key, entry, request, bounds, epsg):
    """Match the approved product, year and query semantics, never just a filename."""
    if not isinstance(entry.get("url"), str):
        return False
    old, new = urlparse(entry["url"]), urlparse(request["url"])
    if (old.scheme, old.netloc, old.path) != (new.scheme, new.netloc, new.path):
        return False
    q, expected = parse_qs(old.query), parse_qs(new.query)
    if key in ("summer", "winter"):
        # Older authoritative responses omitted this default-true option.
        q.setdefault("returnGeometry", ["true"])
        from shapely.geometry import box
        from shapely.ops import transform
        from glassing.transfer import project

        try:
            b = list(map(float, q.pop("geometry")[0].split(",")))
            sr = int(q.pop("inSR")[0])
            required = box(*bounds).segmentize(160)
            region = transform(project(epsg, sr), required)
            if len(b) != 4 or not box(*b).covers(region):
                return False
        except (ValueError, TypeError, KeyError):
            return False
        expected.pop("geometry")
        expected.pop("inSR")
    else:
        q.pop("bbox", None)
        expected.pop("bbox", None)
    return q == expected


def manifests():
    """Managed entries first, then project-local raw manifests in stable order."""
    store = STATE / "sources"
    managed = (
        sorted(store.glob("*/*/manifest.json"))
        if store.resolve().is_relative_to(STATE.resolve())
        else []
    )
    workspace = WORKSPACE.resolve()
    raw = sorted(
        p
        for name, pattern in (
            ("data", "**/manifest.json"),
            ("results", "*/downloads/manifest.json"),
        )
        if (workspace / name).resolve().is_relative_to(workspace)
        for p in (workspace / name).glob(pattern)
    )
    return [(p, STATE.resolve()) for p in managed] + [(p, workspace) for p in raw]


def checked_entries():
    for manifest, root in manifests():
        if not manifest.resolve().is_relative_to(root):
            continue
        try:
            raw = manifest.read_bytes()
            entries = json.loads(raw)
            if not isinstance(entries, dict):
                continue
        except (OSError, ValueError):
            continue
        stamp = hashlib.sha256(raw).hexdigest()
        for name, entry in sorted(entries.items()):
            if not isinstance(name, str) or Path(name).name != name:
                continue
            if not isinstance(entry, dict) or not re.fullmatch(
                "[0-9a-f]{64}", str(entry.get("sha256", ""))
            ):
                continue
            path = manifest.parent / name
            if not path.resolve().is_relative_to(root) or not path.is_file():
                continue
            yield name, path, entry, manifest, stamp


def unchanged(path, entry, manifest, stamp):
    if not all(
        any(
            p.resolve().is_relative_to(root)
            for root in (WORKSPACE.resolve(), STATE.resolve())
        )
        for p in (path, manifest)
    ):
        raise ValueError(f"Local source escaped the project: {path}")
    if digest(path) != entry["sha256"] or digest(manifest) != stamp:
        raise ValueError(f"Changed input during local source validation: {path}")


def self_contained(path):
    if path.suffix != ".tif":
        return
    from osgeo import gdal

    ds = gdal.Open(str(path))
    dependencies = [Path(p).resolve() for p in ds.GetFileList()] if ds else []
    ds = None
    if dependencies != [path.resolve()]:
        raise ValueError(
            "Raw raster has unrecorded companion files; an exact single-file import would lose source information"
        )


def import_source(key, path, entry, manifest, stamp):
    """Atomic content/provenance publication; originals are never moved or edited."""
    provenance = {k: v for k, v in entry.items() if k != "reuse_origin"}
    identity = hashlib.sha256(
        json.dumps(provenance, sort_keys=True).encode()
    ).hexdigest()
    folder = STATE / "sources" / key / identity
    target = folder / (key + path.suffix)
    record = folder / "manifest.json"
    if not folder.resolve().is_relative_to(
        STATE.resolve() / "sources"
    ) or not target.resolve().is_relative_to(STATE.resolve() / "sources"):
        raise ValueError(f"Managed source escaped its local store: {target}")
    with locked(STATE / "sources/import"):
        folder.mkdir(parents=True, exist_ok=True)
        existing = read_json(record, {})
        if not isinstance(existing, dict):
            raise ValueError(f"Corrupt managed source provenance retained: {record}")
        if target.exists():
            if digest(target) != entry["sha256"]:
                raise ValueError(f"Corrupt managed source retained: {target}")
            validate(
                target, target.name, entry, scratch_dir=STATE / "source-validation"
            )
            self_contained(target)
            if digest(target) != entry["sha256"]:
                raise ValueError(f"Changed managed source during validation: {target}")
            unchanged(path, entry, manifest, stamp)
            if existing:
                saved = existing.get(target.name)
                if (
                    not saved
                    or {k: v for k, v in saved.items() if k != "reuse_origin"}
                    != provenance
                ):
                    raise ValueError(f"Changed managed source provenance: {record}")
                return dict(saved, path=str(target))
        else:
            check_space(folder, path.stat().st_size)
            fd, temporary = tempfile.mkstemp(
                prefix=".import-", suffix=".partial", dir=folder
            )
            partial = Path(temporary)
            try:
                with os.fdopen(fd, "wb") as destination, path.open("rb") as source:
                    while block := source.read(1024 * 1024):
                        check_space(folder, len(block))
                        destination.write(block)
                    destination.flush()
                    os.fsync(destination.fileno())
                if digest(partial) != entry["sha256"]:
                    raise ValueError(f"Changed input during local source copy: {path}")
                validate(
                    partial, target.name, entry, scratch_dir=STATE / "source-validation"
                )
                if digest(partial) != entry["sha256"]:
                    raise ValueError(f"Changed local copy during validation: {partial}")
                unchanged(path, entry, manifest, stamp)
                partial.replace(target)
                directory = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            finally:
                partial.unlink(missing_ok=True)
        saved = dict(
            provenance,
            reuse_origin=entry.get("reuse_origin")
            or dict(path=str(path), manifest=str(manifest), manifest_sha256=stamp),
        )
        write(record, {target.name: saved})
        return dict(saved, path=str(target))


def cached(config, inputs, original_cached):
    from glassing.owner_data import grid_bounds, plan

    # A selected managed file is an input, not an opportunity to fall back to
    # another source if its bytes or recorded provenance have changed.
    for key in KEYS:
        spec = config["data"].get(key)
        if not isinstance(spec, dict):
            continue
        raw = spec.get("raw_source", spec)
        if raw.get("reuse_origin"):
            path = Path(raw["path"])
            if not path.resolve().is_relative_to(STATE.resolve() / "sources"):
                raise ValueError(f"Managed source escaped its local store: {path}")
            entry = {k: v for k, v in raw.items() if k != "path"}
            record = path.parent / "manifest.json"
            if (
                read_json(record, {}).get(path.name) != entry
                or digest(path) != raw["sha256"]
            ):
                raise ValueError(f"Changed managed source input or provenance: {path}")
            with validating(config, inputs):
                validate(
                    path,
                    key + path.suffix,
                    entry,
                    scratch_dir=STATE / "source-validation",
                )
            self_contained(path)
            if (
                digest(path) != raw["sha256"]
                or read_json(record, {}).get(path.name) != entry
            ):
                raise ValueError(f"Changed managed source during validation: {path}")

    # Retain the original DEM discovery. Vegetation/ranges need the stronger
    # product/query validation before automatic reuse from any raw source cache.
    probe = dict(config, data=dict(config["data"]))
    for key in KEYS:
        probe["data"].setdefault(key, True)
        if not probe["data"][key]:
            probe["data"][key] = True
    found = original_cached(probe, inputs)
    config["data"].update(found)
    missing = [key for key in KEYS if not config["data"].get(key)]
    if not missing:
        return found
    probe = dict(config, data=dict(config["data"], dem=True))
    requests = {item["key"]: item for item in plan(probe, inputs)[0]}
    bounds = grid_bounds(config, inputs)
    with validating(config, inputs):
        for name, path, entry, manifest, stamp in checked_entries():
            key = next(
                (
                    k
                    for k in missing
                    if name in (k + ".tif", k + "_padded120.tif", k + ".geojson")
                ),
                None,
            )
            if (
                not key
                or key not in requests
                or not compatible(key, entry, requests[key], bounds, config["epsg"])
            ):
                continue
            try:
                unchanged(path, entry, manifest, stamp)
                validate(path, name, entry, scratch_dir=STATE / "source-validation")
                self_contained(path)
                unchanged(path, entry, manifest, stamp)
            except (ValueError, OSError, RuntimeError) as error:
                print(f"Local {key} source not reused: {path}: {error}", flush=True)
                continue
            selected = import_source(key, path, entry, manifest, stamp)
            config["data"][key] = found[key] = selected
            missing.remove(key)
            print(
                f"Reusing verified local {key}: {selected['path']} ({entry.get('acquisition_date', 'date unknown')})",
                flush=True,
            )
            if not missing:
                break
    return found
