"""Immutable local source packs. Explicit adapters; no catalog/provider requests.

Catalog publication is atomic. File identity (including ctime) bounds integrity
caching; checking a selector never reads raster pixels or hashes the whole pack.
Full validation occurs on installation and on first use after a process restart.
"""

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re

from shapely.geometry import box, shape, mapping
from shapely.ops import transform, unary_union
from glassing.transfer import project
from .config import current, STATE, WORKSPACE
from .storage import read_json, write, locked
from .catalog import check_hash

CONTRACT = 1
CORE = ("dem", "tree", "shrub", "herb", "summer", "winter")


def root():
    return current().pack_dir


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9_-]{0,79}", value
    ):
        raise ValueError("Invalid pack identity")
    return value


def identity(path):
    s = path.stat()
    return (
        str(path.resolve()),
        s.st_dev,
        s.st_ino,
        s.st_size,
        s.st_mtime_ns,
        s.st_ctime_ns,
    )


def asset_path(folder, name):
    if not isinstance(name, str):
        raise ValueError("Invalid pack dependency name; restore the sealed version")
    p = folder / name
    if Path(name).is_absolute() or not p.resolve().is_relative_to(folder.resolve()):
        raise ValueError("Pack dependency escaped its version directory")
    return p


def verify_file(path, spec):
    if (
        not isinstance(spec, dict)
        or type(spec.get("bytes")) is not int
        or spec["bytes"] < 0
        or not re.fullmatch("[0-9a-f]{64}", str(spec.get("sha256", "")))
    ):
        raise ValueError(
            f"Pack integrity record missing or damaged for {path}; restore its original seal or prepare a new version"
        )
    if not path.is_file() or path.stat().st_size != spec["bytes"]:
        raise ValueError(
            f"Missing or damaged pack asset: {path}. Retain this version and prepare a new version, or restore the exact original bytes."
        )
    s = path.stat()
    check_hash(
        str(path.resolve()),
        s.st_mtime_ns,
        s.st_size,
        spec["sha256"],
        (s.st_dev, s.st_ino, s.st_ctime_ns),
    )


def validate_manifest(v):
    if (
        not isinstance(v, dict)
        or v.get("contract") != CONTRACT
        or not isinstance(v.get("data"), dict)
        or not isinstance(v.get("assets"), dict)
        or not all(isinstance(v["data"].get(k), dict) for k in CORE)
        or not all(
            k in v
            for k in (
                "unit_id",
                "version",
                "label",
                "state",
                "gmu",
                "epsg",
                "boundary",
                "context",
                "bounds",
                "support",
                "detail",
                "networks",
            )
        )
    ):
        raise ValueError(
            "Pack contract incompatible or incomplete; prepare a new version"
        )
    if v.get("status") != "ready":
        raise ValueError(
            "Pack preparation is incomplete; resume its retained preparation"
        )
    identifier(v["unit_id"])
    identifier(v["version"])
    return v


@lru_cache(maxsize=32)
def _manifest(path, stamp):
    return validate_manifest(read_json(path))


def catalog_record():
    value = read_json(root() / "catalog.json", dict(contract=CONTRACT, units={}))
    if (
        not isinstance(value, dict)
        or value.get("contract") != CONTRACT
        or not isinstance(value.get("units"), dict)
    ):
        raise ValueError(
            "Local pack catalog is damaged or incompatible; restore catalog.json or explicitly register a validated version"
        )
    return value


def load(unit, version=None, verify=True):
    unit = identifier(unit)
    if version is None:
        catalog = catalog_record()
        version = catalog.get("units", {}).get(unit)
    if not version:
        raise ValueError("No ready pack registered for this unit; resume preparation")
    folder = root() / "versions" / unit / identifier(version)
    path = folder / "pack.json"
    if not path.is_file():
        raise ValueError(
            "Pack manifest missing; restore this version or prepare a new version"
        )
    v = _manifest(str(path), identity(path))
    if v["unit_id"] != unit or v["version"] != version:
        raise ValueError("Pack identity disagrees with its registration")
    # Catalog seals the manifest; pinned runs carry the same immutable seal.
    seal = read_json(folder / "seal.json", {})
    verify_file(path, seal)
    for spec in v["assets"].values():
        if not isinstance(spec, dict) or not isinstance(spec.get("path"), str):
            raise ValueError("Pack asset record is damaged; restore the sealed version")
        p = asset_path(folder, spec["path"])
        if verify:
            verify_file(p, spec)
        elif not p.is_file() or p.stat().st_size != spec["bytes"]:
            raise ValueError(
                f"Pack asset missing/damaged: {p}; restore it or prepare a new version"
            )
    if verify:
        from .source_reuse import self_contained

        for key in ("dem", "tree", "shrub", "herb"):
            self_contained(asset_path(folder, v["data"][key]["path"]))
    return folder, v


def catalog():
    value = catalog_record()
    rows = []
    for unit, version in value.get("units", {}).items():
        try:
            folder, v = load(unit, version)
            rows.append(
                dict(
                    unit_id=unit,
                    version=version,
                    state=v["state"],
                    gmu=v["gmu"],
                    label=v["label"],
                    status="ready",
                    core="Ready locally",
                    detail=v["detail"],
                    bounds=v["bounds"],
                    support=v["support"],
                    boundary=v["boundary"],
                )
            )
        except (OSError, ValueError, KeyError) as e:
            rows.append(
                dict(
                    unit_id=unit,
                    version=version,
                    label=unit,
                    status="unavailable",
                    error=str(e),
                )
            )
    preparations = []
    for path in (root() / "preparing").glob("*/progress.json"):
        try:
            preparations.append(read_json(path))
        except ValueError as error:
            preparations.append(dict(stage="Recovery needed", error=str(error)))
    return dict(units=rows, preparations=preparations)


def context(unit, version):
    folder, v = load(unit, version)
    return dict(
        **v,
        boundary_geojson=read_json(asset_path(folder, v["boundary"])),
        context_geojson=read_json(asset_path(folder, v["context"])),
    )


def pin(unit, version):
    folder, v = load(unit, version)
    return dict(
        unit_id=unit,
        version=version,
        label=v["label"],
        manifest_sha256=read_json(folder / "seal.json")["sha256"],
    )


def resolve(pinned):
    folder, v = load(pinned["unit_id"], pinned["version"])
    if read_json(folder / "seal.json")["sha256"] != pinned["manifest_sha256"]:
        raise ValueError(
            "Pinned pack manifest changed; restore exact version; existing run preserved"
        )
    return folder, v


def window(geometry, radius, config, pinned):
    """Observer eligibility is the unit; obstruction support is a separate halo."""
    folder, v = resolve(pinned)
    area = transform(project(4326, v["epsg"]), geometry)
    boundary = read_json(asset_path(folder, v["boundary"]))
    unit = transform(
        project(4326, v["epsg"]),
        unary_union([shape(f["geometry"]) for f in boundary["features"]]),
    )
    if not unit.buffer(0.01).covers(area):
        raise ValueError(
            "Observer area must lie inside the selected unit. Draw a smaller area within its outline, or choose Custom area."
        )
    res = config["resolution_m"]
    b = area.buffer(radius + 2 * res).bounds
    b = [
        math.floor(b[0] / res) * res,
        math.floor(b[1] / res) * res,
        math.ceil(b[2] / res) * res,
        math.ceil(b[3] / res) * res,
    ]
    cells = round((b[2] - b[0]) * (b[3] - b[1]) / res**2)
    if cells > config["max_cells"]:
        raise ValueError(
            f'This buffered area needs {cells:,} cells; limit {config["max_cells"]:,}. Choose a smaller local scouting area within the unit (begin around 10–50 km²).'
        )
    if radius > v["support"]["maximum_visibility_radius_m"] or not box(
        *v["support"]["bounds"]
    ).covers(box(*b)):
        raise ValueError(
            "Area exceeds this pack’s supported terrain halo; reduce the area/radius or prepare a new version"
        )
    return b


def configure(config, geometry, unit, version):
    pinned = pin(unit, version)
    folder, v = resolve(pinned)
    config["epsg"] = v["epsg"]
    bounds = window(geometry, config["radius_m"], config, pinned)
    config["unit_pack"] = pinned
    config["data"].update(
        {
            k: dict(v["data"][k], path=str(asset_path(folder, v["data"][k]["path"])))
            for k in CORE
        }
    )
    config["data"].update(prepare_window(pinned, bounds))
    config["hunt"] = dict(config.get("hunt", {}), state=v["state"], gmu=v["gmu"])
    return pinned


def prepare_window(pinned, bounds):
    """Persistent checked subsets: keep habitat neighborhoods off unit-sized arrays."""
    from osgeo import gdal
    from glassing.acquire import digest
    from .downloads import check_space

    folder, v = resolve(pinned)
    key = hashlib.sha256(
        json.dumps([pinned, bounds, 480, 2], sort_keys=True).encode()
    ).hexdigest()
    home = WORKSPACE / "data/pack-windows" / key
    seal = home / "window.json"
    with locked(seal):
        saved = read_json(seal)
        if saved:
            for spec in saved.values():
                verify_file(Path(spec["path"]), spec)
            return saved
        home.mkdir(parents=True, exist_ok=True)
        check_space(home, 512 * 1024**2)
        saved = {}
        for k in ("dem", "tree", "shrub", "herb"):
            res = 10 if k == "dem" else 30
            pad = 0 if k == "dem" else 480
            b = [
                math.floor((bounds[0] - pad) / res) * res,
                math.floor((bounds[1] - pad) / res) * res,
                math.ceil((bounds[2] + pad) / res) * res,
                math.ceil((bounds[3] + pad) / res) * res,
            ]
            if not box(*v["support"]["bounds"]).covers(box(*b)):
                raise ValueError(
                    "Pack neighborhood support missing; choose a smaller area"
                )
            path = home / (k + ".tif")
            temporary = home / (k + ".partial.tif")
            ds = gdal.Translate(
                str(temporary),
                str(asset_path(folder, v["data"][k]["path"])),
                format="GTiff",
                projWin=[b[0], b[3], b[2], b[1]],
                creationOptions=["TILED=YES", "COMPRESS=DEFLATE"],
            )
            if ds is None:
                raise ValueError(
                    "Pack window preparation failed; retry retains source pack"
                )
            ds = None
            from .source_reuse import self_contained

            self_contained(temporary)
            temporary.replace(path)
            saved[k] = dict(
                {
                    name: value
                    for name, value in v["data"][k].items()
                    if name != "reuse_origin"
                },
                pack_source_provenance={
                    name: value
                    for name, value in v["data"][k].items()
                    if name != "path"
                },
                path=str(path),
                sha256=digest(path),
                bytes=path.stat().st_size,
                unit_pack=pinned,
                pack_source_sha256=v["data"][k]["sha256"],
                local_window_bounds=b,
                preparation="Exact aligned pixel subset of pinned pack; habitat support includes 480m padding",
            )
        write(seal, saved)
        return saved


def install_networks(pinned, geometry):
    """Copy only bounded local network windows through the established importer."""
    from .scouting_network import save_network, load_networks

    folder, v = resolve(pinned)
    area = transform(project(4326, v["epsg"]), geometry).buffer(
        v["support"]["approach_radius_m"] + 60
    )
    bounds = list(
        transform(project(v["epsg"], 4326), box(*area.bounds).segmentize(100)).bounds
    )
    region = box(*bounds)
    ids = []
    for kind in ("roads", "trails"):
        key = hashlib.sha256(
            json.dumps([pinned, kind, bounds], sort_keys=True).encode()
        ).hexdigest()
        pointer = STATE / "pack-networks" / (key + ".json")
        with locked(pointer):
            old = read_json(pointer)
            if old:
                load_networks([old["id"]], 4326)
                ids.append(old["id"])
                continue
            features = {}
            for spec in v["networks"][kind]:
                if not box(*spec["bounds"]).intersects(region):
                    continue
                value = read_json(asset_path(folder, spec["path"]))
                for f in value["features"]:
                    g = shape(f["geometry"])
                    if g.intersects(region):
                        # Retain original measured vertices/properties. Bounded window
                        # selects whole features rather than inventing access connectors.
                        features[json.dumps(f, sort_keys=True)] = f
            raw = json.dumps(
                dict(type="FeatureCollection", features=list(features.values()))
            ).encode()
            record = save_network(
                raw,
                ".geojson",
                kind,
                f'{v["label"]} {v["version"]} · ' + v["network_provider"],
                v["created_utc"],
                coverage=bounds,
                unit_pack=pinned,
            )
            write(pointer, dict(id=record["id"], unit_pack=pinned))
            ids.append(record["id"])
    return ids


def publish(staging, manifest):
    """Seal/validate before rename, then change only the catalog pointer."""
    import os
    from .downloads import check_space
    from glassing.acquire import digest

    staging = Path(staging)
    target = (
        root()
        / "versions"
        / identifier(manifest["unit_id"])
        / identifier(manifest["version"])
    )
    with locked(root() / "publication"):
        if target.exists():
            raise ValueError("Immutable pack version exists; choose a new version")
        check_space(root(), 128 * 1024**2)
        validate_manifest(manifest)
        if manifest.get("contract") != CONTRACT or not all(
            k in manifest.get("data", {}) for k in CORE
        ):
            raise ValueError(
                "Incomplete/incompatible core contract cannot be published"
            )
        from .source_reuse import self_contained
        from osgeo import gdal

        for key in CORE:
            descriptor = manifest["data"][key]
            spec = manifest["assets"].get(descriptor["path"])
            if not spec or spec["sha256"] != descriptor["sha256"]:
                raise ValueError("Unsealed pack data dependency: " + key)
            verify_file(asset_path(staging, descriptor["path"]), spec)
            if key in ("dem", "tree", "shrub", "herb"):
                raster = asset_path(staging, descriptor["path"])
                self_contained(raster)
                ds = gdal.Open(str(raster))
                if (
                    not ds
                    or ds.RasterCount != 1
                    or not ds.GetSpatialRef().IsProjected()
                ):
                    raise ValueError("Incompatible core raster: " + key)
        for spec in manifest["assets"].values():
            verify_file(asset_path(staging, spec["path"]), spec)
        if manifest.get("status") != "ready":
            raise ValueError("Incomplete pack cannot be published")
        write(staging / "pack.json", manifest)
        write(
            staging / "seal.json",
            dict(
                sha256=digest(staging / "pack.json"),
                bytes=(staging / "pack.json").stat().st_size,
            ),
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        # Same-filesystem rename leaves incomplete work recoverable on interruption.
        os.rename(staging, target)
        value = catalog_record()
        value["units"][manifest["unit_id"]] = manifest["version"]
        write(root() / "catalog.json", value)
    return target


def register_existing(unit, version):
    """Recover a validated rename interrupted before catalog publication."""
    with locked(root() / "publication"):
        folder, value = load(unit, version)
        catalog = catalog_record()
        catalog["units"][unit] = version
        write(root() / "catalog.json", catalog)
        return folder
