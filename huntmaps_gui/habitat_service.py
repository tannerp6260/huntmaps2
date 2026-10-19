"""Verified local sources → immutable GUI profiles → revision-bound derived metrics.

This adapter never acquires sources or evaluates visibility. Runtime paths resolve
through AppConfig; derived assets have their own seals outside analysis directories.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from functools import lru_cache
import hashlib
import io
import json
import math
import re
from pathlib import Path
import threading
from collections import OrderedDict
from urllib.parse import parse_qs, urlparse

import numpy as np
from osgeo import gdal
from glassing.core import digest as file_digest
from .config import STATE, WORKSPACE
from .storage import read_json, write, atomic_bytes, locked
from .catalog import check_hash
from . import habitat, scouting_filters as filters

EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="habitat")
ADMISSION = threading.BoundedSemaphore(3)
TILE_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="habitat-tile")
TILE_ADMISSION = threading.BoundedSemaphore(128)
BUILD = threading.RLock()
TRANSFER = threading.RLock()
PREPARED = OrderedDict()
METRICS = OrderedDict()


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


async def background(fn, *args):
    if not ADMISSION.acquire(blocking=False):
        raise ValueError(
            "Habitat/collection work is busy; retry after the pending calculation"
        )
    context = copy_context()
    future = EXECUTOR.submit(context.run, fn, *args)
    future.add_done_callback(lambda _: ADMISSION.release())
    return await asyncio.wrap_future(future)


async def background_tile(fn):
    # Ordinary viewport bursts wait asynchronously on two dedicated tile workers;
    # they must not compete for the small preference/collection admission queue.
    if not TILE_ADMISSION.acquire(blocking=False):
        raise ValueError("Too many habitat tiles pending; retry the viewport")
    context = copy_context()
    future = TILE_EXECUTOR.submit(context.run, fn)
    future.add_done_callback(lambda _: TILE_ADMISSION.release())
    return await asyncio.wrap_future(future)


def identity(path):
    st = Path(path).stat()
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]


def verify(path, expected):
    st = Path(path).stat()
    check_hash(
        str(Path(path).resolve()),
        st.st_mtime_ns,
        st.st_size,
        expected,
        (st.st_dev, st.st_ino, st.st_ctime_ns),
    )


def source_inventory(config, resolve, validator=None):
    sources = {}
    year = None
    for name in ("tree", "shrub"):
        spec = config["data"][name]
        path = Path(resolve(spec["path"])).resolve()
        if validator:
            validator(path)
        verify(path, spec["sha256"])
        q = parse_qs(urlparse(spec.get("url", "")).query)
        coverage = q.get("coverage", [""])[0]
        component = spec.get("component")
        product = spec.get("product", "") + " " + spec.get("provider", "")
        synthetic = config.get("input_kind") == "synthetic_fixture"
        annual = spec.get("observation_year", spec.get("year"))
        if annual is None and q.get("time"):
            annual = int(q["time"][0][:4])
        encoded_year = re.search(r"_(\d{4})$", coverage)
        if encoded_year and int(encoded_year[1]) != annual:
            raise ValueError("Habitat observation year disagrees with the source layer")
        if q.get("time") and int(q["time"][0][:4]) != annual:
            raise ValueError(
                "Habitat observation year disagrees with its temporal query"
            )
        if not synthetic and (
            "rcmap" not in product.lower()
            or (component is not None and component != name)
            or name not in coverage
            or type(annual) is not int
            or not 1985 <= annual <= 2100
        ):
            raise ValueError(
                "Habitat requires verified RCMAP tree/shrub identity and observation year"
            )
        if year is not None and annual != year:
            raise ValueError("Habitat vegetation years differ")
        year = annual
        units = spec.get("units", "").lower()
        expected_coverages = {
            f"rcmap_{name}:rcmap_{name}_{annual}",
            f"mrlc_{name}_westernconus_year_data:{name}_westernconus_year_data",
        }
        if not synthetic and coverage not in expected_coverages:
            raise ValueError(
                "Ambiguous or incompatible RCMAP component coverage identifier"
            )
        if not synthetic and "percent" not in units:
            raise ValueError(
                "Habitat raw sources require documented percent cover units"
            )
        ds = gdal.Open(str(path))
        if ds is None or ds.RasterCount != 1:
            raise ValueError("Habitat cover raster is unavailable or ambiguous")
        gt, _ = habitat.grid(ds)
        nodata = ds.GetRasterBand(1).GetNoDataValue()
        sources[name] = dict(
            path=str(path),
            sha256=spec["sha256"],
            provenance=spec,
            gt=list(gt),
            crs=ds.GetProjection(),
            shape=[ds.RasterYSize, ds.RasterXSize],
            nodata=(
                str(nodata)
                if nodata is not None and not math.isfinite(nodata)
                else nodata
            ),
            filesystem=identity(path),
        )
    # Components must be exactly co-registered; don't interpolate mismatched cover.
    a, b = sources.values()
    da, db = gdal.Open(a["path"]), gdal.Open(b["path"])
    if (
        a["gt"] != b["gt"]
        or a["shape"] != b["shape"]
        or not da.GetSpatialRef().IsSame(db.GetSpatialRef())
    ):
        raise ValueError("Habitat source components are not aligned")
    return sources


def authoritative(sources):
    return {
        k: {n: v for n, v in s.items() if n != "filesystem"} for k, s in sources.items()
    }


def recheck(sources):
    for s in sources.values():
        if identity(s["path"]) != s["filesystem"]:
            raise ValueError("Habitat sources changed during calculation; retry")


def array_dataset(a, gt, wkt, nodata=None):
    ds = gdal.GetDriverByName("MEM").Create(
        "", a.shape[1], a.shape[0], 1, gdal.GDT_Float64
    )
    ds.SetGeoTransform(gt)
    ds.SetProjection(wkt)
    ds.GetRasterBand(1).WriteArray(a)
    if nodata is not None:
        ds.GetRasterBand(1).SetNoDataValue(nodata)
    return ds


def warp(a, gt, wkt, destination, method="near"):
    dg = destination.GetGeoTransform()
    width = destination.RasterXSize
    height = destination.RasterYSize
    ds = gdal.Warp(
        "",
        array_dataset(a, gt, wkt),
        format="MEM",
        dstSRS=destination.GetProjection(),
        outputBounds=[dg[0], dg[3] + height * dg[5], dg[0] + width * dg[1], dg[3]],
        width=width,
        height=height,
        resampleAlg=method,
        dstNodata=0,
        outputType=gdal.GDT_Float64,
    )
    if ds is None:
        raise ValueError("Habitat grid transfer failed")
    return ds.ReadAsArray()


def cached_arrays(kind, key, builder, sources):
    home = STATE / "cache" / "habitat" / kind / key
    path = home / "arrays.npz"
    with locked(STATE / "maintenance"), BUILD:
        seal = read_json(home / "seal.json")
        if path.exists() and seal:
            verify(path, seal["sha256"])
            with np.load(path, allow_pickle=False) as loaded:
                return {k: loaded[k] for k in loaded.files}
        arrays = builder()
        recheck(sources)
        from .downloads import check_space

        check_space(STATE, sum(a.nbytes for a in arrays.values()))
        buffer = io.BytesIO()
        np.savez_compressed(buffer, **arrays)
        with locked(STATE / "maintenance"):
            recheck(sources)
            atomic_bytes(path, buffer.getvalue())
            write(
                home / "seal.json",
                dict(sha256=file_digest(path), identity=key, algorithm=habitat.VERSION),
            )
            from .display_cache import changed

            changed()
        return arrays


def context(sources, settings):
    s = habitat.validate(settings)
    first = sources["tree"]
    gt = first["gt"]
    # Globally aligned 10 m multiples, never finer than delivered or nominal support.
    res = math.ceil(max(30, gt[1], -gt[5]) / 10) * 10
    x = math.floor(gt[0] / res) * res
    y = math.ceil(gt[3] / res) * res
    width = math.ceil((gt[0] + first["shape"][1] * gt[1] - x) / res)
    height = math.ceil((y - (gt[3] + first["shape"][0] * gt[5])) / res)
    cg = (x, res, 0, y, 0, -res)
    key = digest(
        dict(
            version=habitat.VERSION,
            sources=authoritative(sources),
            grid=[cg, width, height],
            radii=[s["local_radius_m"], s["landscape_radius_m"]],
        )
    )

    def build():
        destination = array_dataset(np.zeros((height, width)), cg, first["crs"])
        arrays = []
        for source in sources.values():
            ds = gdal.Open(source["path"])
            a = ds.ReadAsArray().astype(float)
            nodata = ds.GetRasterBand(1).GetNoDataValue()
            known = np.isfinite(a) & (a >= 0) & (a <= 100)
            if nodata is not None:
                known &= a != nodata
            mean = warp(
                np.where(known, a / 100, 0), gt, first["crs"], destination, "average"
            )
            support = warp(
                known.astype(float), gt, first["crs"], destination, "average"
            )
            rr, cc = np.indices((height, width))
            # GDAL average ignores outside footprints; require complete coarse footprint.
            inside = (
                (x + cc * res >= gt[0])
                & (x + (cc + 1) * res <= gt[0] + first["shape"][1] * gt[1])
                & (y - rr * res <= gt[3])
                & (y - (rr + 1) * res >= gt[3] + first["shape"][0] * gt[5])
            )
            arrays.append(
                np.where(
                    inside & (support >= 0.999999),
                    mean / np.maximum(support, 1e-12),
                    np.nan,
                )
            )
        result = habitat.features(*arrays, res, s)
        result.update(gt=np.array(cg), wkt=np.array(first["crs"]))
        return result

    return key, cached_arrays("context", key, build, sources)


def prepare(sources, settings, dem):
    habitat.grid(dem)
    key, f = context(sources, settings)
    raster_key = digest([key, habitat.validate(settings)])

    def build():
        layers = habitat.evaluate(f, settings)
        layers["q"] = layers["h"] * layers["g"]
        layers["observation_penalty"] = layers["h"] * (1 - layers["g"])
        layers["priority_fraction"] = habitat.priority(layers, settings).astype(float)
        layers["high_fraction"] = (
            layers["known"] & (layers["h"] >= settings["habitat_threshold"])
        ).astype(float)
        layers["effective_components"] = layers["components"] * layers["g"][None, :, :]
        return layers

    coarse = cached_arrays("raster", raster_key, build, sources)
    transfer_key = digest(
        [
            str(STATE.resolve()),
            raster_key,
            dem.GetGeoTransform(),
            dem.GetProjection(),
            dem.RasterYSize,
            dem.RasterXSize,
        ]
    )
    with TRANSFER:
        with BUILD:
            cached = PREPARED.get(transfer_key)
        if cached is not None:
            return cached
        gt = tuple(f["gt"])
        wkt = str(f["wkt"])
        method = (
            "average"
            if max(dem.GetGeoTransform()[1], -dem.GetGeoTransform()[5]) > gt[1]
            else "near"
        )
        layers = {}
        for name, a in coarse.items():
            if a.ndim == 3:
                layers[name] = np.stack([warp(v, gt, wkt, dem, method) for v in a])
            else:
                layers[name] = warp(a.astype(float), gt, wkt, dem, method)
        layers["known"] = layers["known"] >= 0.999999
        result = dict(
            identity=digest(
                [
                    raster_key,
                    dem.GetGeoTransform(),
                    dem.GetProjection(),
                    dem.RasterYSize,
                    dem.RasterXSize,
                ]
            ),
            context_id=key,
            raster_id=raster_key,
            source_support_m=float(gt[1]),
            layers=layers,
        )
        if sum(a.nbytes for a in layers.values()) <= 384 * 1024**2:
            with BUILD:
                PREPARED.clear()
                PREPARED[transfer_key] = result
            for a in layers.values():
                a.flags.writeable = False
        return result


def selection(run):
    value = read_json(
        STATE / "habitat-selections" / f"{run}.json", dict(profile="", revision=0)
    )
    if (
        not isinstance(value, dict)
        or set(value) != {"profile", "revision"}
        or type(value["revision"]) is not int
        or value["revision"] < 0
        or not isinstance(value["profile"], str)
        or (value["profile"] and not re.fullmatch("[a-f0-9]{32}", value["profile"]))
    ):
        raise ValueError(
            "Damaged habitat selection; preserve the record and restore a Storage backup"
        )
    return value


def load(ident, run):
    from .scouting_network import checked_id

    value = read_json(STATE / "habitat-profiles" / f"{checked_id(ident)}.json")
    if (
        not isinstance(value, dict)
        or value.get("version") != 1
        or value.get("algorithm") != habitat.VERSION
        or value.get("run_id") != run
        or value.get("id") != digest({k: v for k, v in value.items() if k != "id"})[:32]
    ):
        raise ValueError(
            "Habitat profile is incompatible or changed; select a current profile"
        )
    habitat.validate(value["settings"])
    return value


def choose(run, body):
    from .working_waypoints import DisplayRun

    if set(body) - {"settings", "target_profile", "revision"}:
        raise ValueError("Unknown habitat preference field")
    if (
        "settings" not in body
        or type(body.get("revision")) is not int
        or body["revision"] < 0
        or not isinstance(body.get("target_profile", ""), str)
    ):
        raise ValueError(
            "Use explicit habitat settings, a nonnegative integer revision and a target profile identifier"
        )
    r = DisplayRun(run, None)
    old = selection(run)
    if body.get("revision") != old["revision"]:
        raise ValueError("Habitat preference changed in another window; reload")
    profile = ""
    if body.get("settings") is not None:
        settings = habitat.validate(body["settings"])
        target = body.get("target_profile", "")
        if target:
            filters.load(target, run)
        sources = source_inventory(r.config, r.path, r.validate)
        value = dict(
            algorithm=habitat.VERSION,
            version=1,
            run_id=run,
            settings=settings,
            target_profile=target,
            sources=authoritative(sources),
        )
        profile = digest(value)[:32]
        value["id"] = profile
    with locked(STATE / "maintenance"):
        if selection(run) != old:
            raise ValueError("Habitat preference changed; reload")
        if profile:
            recheck(sources)
            write(STATE / "habitat-profiles" / f"{profile}.json", value)
        saved = dict(profile=profile, revision=old["revision"] + 1)
        write(STATE / "habitat-selections" / f"{run}.json", saved)
    return saved


class HabitatRun:
    def __init__(self, run, profile):
        self.run = run
        self.habitat_profile = profile
        sources = source_inventory(run.config, run.path, run.validate)
        if authoritative(sources) != profile["sources"]:
            raise ValueError("Habitat source provenance changed; apply a new profile")
        self.sources = sources
        self.prepared = prepare(sources, profile["settings"], run.dem)
        self.layers = self.prepared["layers"]
        self.settings = profile["settings"]
        target = profile["target_profile"]
        fp = (
            filters.load(target, run.id)
            if target
            else dict(
                id="original-terrain",
                settings=filters.validate({}),
                sources=[],
                dem_sha256=run.hashes[str(run.dem_path.resolve())],
            )
        )
        self.filtered = filters.FilteredRun(run, fp)
        run.validate(run.analysis / "observer.tif")
        observer_ds = gdal.Open(str(run.analysis / "observer.tif"))
        if (
            observer_ds.GetGeoTransform() != run.dem.GetGeoTransform()
            or not observer_ds.GetSpatialRef().IsSame(run.dem.GetSpatialRef())
            or (observer_ds.RasterYSize, observer_ds.RasterXSize)
            != (run.dem.RasterYSize, run.dem.RasterXSize)
        ):
            raise ValueError("Habitat observer eligibility is not aligned")
        self.observer = observer_ds.ReadAsArray() == 1
        self.profile = profile  # tile identity, distinct from v1 target filters
        self.area = habitat.grid(run.dem)[1]
        paths = [
            run.dem_path,
            run.analysis / "target.tif",
            run.analysis / "observer.tif",
            run.analysis / "tree.tif",
            run.analysis / "shrub.tif",
            run.analysis / "scores.json",
            run.base.base / "scouting.json",
        ]
        for path in paths:
            run.validate(path)
        paths.extend(
            STATE / namespace / f"{ident}.json"
            for namespace, ident in [
                ("habitat-profiles", profile["id"]),
                ("filter-profiles", target),
            ]
            if ident
        )
        self.dependencies = {str(path): identity(path) for path in paths}
        self.mask_snapshots = {}

    def validate_snapshot(self):
        recheck(self.sources)
        if any(
            identity(path) != stamp
            for path, stamp in {**self.dependencies, **self.mask_snapshots}.items()
        ):
            raise ValueError("Habitat inputs changed during calculation; retry")
        from .working_waypoints import snapshot

        if snapshot(self.id, None)["overrides"] != self.run.working:
            raise ValueError(
                "Working waypoints changed during habitat calculation; retry"
            )

    def __getattr__(self, name):
        return getattr(self.run, name)

    def candidate_metrics(self, cid):
        path = self.run.visibility_path(cid)
        self.mask_snapshots[str(path)] = identity(path)
        cache_key = digest(
            [
                str(STATE.resolve()),
                self.prepared["identity"],
                self.filtered.profile,
                cid,
                str(path),
                identity(path),
                self.run.working.get(cid),
                self.run.rows.get(cid),
            ]
        )
        with BUILD:
            cached = METRICS.get(cache_key)
            if cached is not None:
                METRICS.move_to_end(cache_key)
                return dict(cached)
        mask, check = self.run.mask(cid)
        m = habitat.metrics(
            self.layers, mask, self.filtered.matching, self.area, self.settings
        )
        m["target_filter_unknown_m2"] = (
            float((mask & self.filtered.unknown).sum()) * self.area
        )
        result = dict(
            m,
            id=cid,
            working_revision=self.run.working.get(cid, {}).get("revision", "original"),
            mask_identity=digest(
                [
                    str(path),
                    identity(path),
                    self.run.working.get(cid, {}).get("revision", "original"),
                ]
            ),
        )
        with BUILD:
            while len(METRICS) >= 8192:
                METRICS.popitem(last=False)
            METRICS[cache_key] = result
        return dict(result)

    def results(self):
        from .manual_observers import records
        from .search import spread_recommendations

        ids = sorted(
            set(self.run.points) | set(self.run.working) | set(records(self.run.id))
        )
        values = []
        rows = []
        # Existing filter adapter evaluates only calculated points; manual uncalculated remain explicit.
        calculated = [
            cid for cid in ids if cid in self.run.points or cid in self.run.working
        ]
        # FilteredRun.results requires point metadata; don't manufacture it for manual masks.
        for cid in ids:
            if cid not in calculated:
                values.append(
                    dict(
                        id=cid,
                        status="mask_unavailable",
                        effective_m2=None,
                        qualifies=False,
                    )
                )
                continue
            try:
                m = self.candidate_metrics(cid)
            except (ValueError, FileNotFoundError) as error:
                if not isinstance(error, FileNotFoundError) and not any(
                    message in str(error)
                    for message in (
                        "No saved visibility",
                        "Current working mask is unavailable",
                    )
                ):
                    raise
                values.append(
                    dict(
                        id=cid,
                        status="mask_unavailable",
                        effective_m2=None,
                        qualifies=False,
                        reason=str(error),
                        working_revision=self.run.working.get(cid, {}).get(
                            "revision", "original"
                        ),
                    )
                )
                parent = (
                    (
                        STATE
                        / "working-waypoints"
                        / self.run.id
                        / "cache"
                        / self.run.working[cid]["revision"]
                    )
                    if cid in self.run.working
                    else (
                        self.run.vegetation / "viewsheds"
                        if self.run.experimental and cid.startswith("V")
                        else self.run.analysis / "additional_visibility"
                    )
                )
                while not parent.exists():
                    parent = parent.parent
                self.dependencies[str(parent)] = identity(parent)
                continue
            point = self.run.candidate(cid)
            from glassing.transfer import project

            x, y = project(4326, self.run.config["epsg"])(
                point["longitude"], point["latitude"]
            )
            if cid in self.run.points and cid not in self.run.working:
                x, y = self.run.points[cid]["x"], self.run.points[cid]["y"]
            p = dict(id=cid, x=x, y=y)
            access = filters.access_evidence(
                (x, y),
                self.filtered.lines,
                self.filtered.dem_array,
                self.run.dem.GetGeoTransform(),
                self.filtered.settings,
                self.filtered.network_index,
            )
            enabled = (
                self.filtered.settings["distance_m"] is not None
                or self.filtered.settings["height_m"] is not None
            )
            qualifies = (not enabled or access["status"] == "qualifies") and (
                self.filtered.standing is None or self.filtered.standing_at(p)
            )
            gt = self.run.dem.GetGeoTransform()
            row, col = math.floor((y - gt[3]) / gt[5]), math.floor((x - gt[0]) / gt[1])
            qualifies = bool(
                qualifies
                and 0 <= row < self.observer.shape[0]
                and 0 <= col < self.observer.shape[1]
                and self.observer[row, col]
            )
            m.update(
                qualifies=qualifies,
                access=access,
                historical_metrics=self.run.rows.get(cid),
                current_mask=True,
            )
            values.append(m)
            rows.append(
                dict(
                    p,
                    habitat=m,
                    raw_km2=m["current_visible_m2"] / 1e6,
                    matching_km2=m["matching_m2"] / 1e6,
                    standing_eligible=qualifies,
                    group=self.run.points.get(cid, {}).get("group", "manual"),
                )
            )
        values.sort(key=habitat.order)
        established_rows = sorted(
            rows, key=lambda p: (-p["matching_km2"], -p["raw_km2"], p["id"])
        )
        established_ranks = {p["id"]: i + 1 for i, p in enumerate(established_rows)}
        historical_ranks = {
            p["id"]: i + 1
            for i, p in enumerate(
                sorted(
                    self.run.rows.values(),
                    key=lambda p: (
                        -p.get("matching_km2", p["raw_km2"]),
                        -p["raw_km2"],
                        p["id"],
                    ),
                )
            )
        }
        for p in values:
            p["established_current_rank"] = established_ranks.get(p["id"])
            p["historical_original_rank"] = historical_ranks.get(p["id"])
        options = self.run.config.get("search", {})
        selected = spread_recommendations(
            rows,
            options.get("recommendation_count", 20),
            options.get("recommendation_separation_m", 0),
        )
        self.validate_snapshot()
        from .working_waypoints import snapshot

        if snapshot(self.run.id, None)["overrides"] != self.run.working:
            raise ValueError("Working waypoints changed while scoring; retry")
        return dict(
            run_id=self.run.id,
            profile=self.habitat_profile,
            identity=self.prepared["identity"],
            source_support_m=self.prepared["source_support_m"],
            candidates=values,
            recommendation_ids=[p["id"] for p in selected],
            nearby_ids={
                p["id"]: [
                    q["id"]
                    for q in sorted(rows, key=habitat.order)
                    if q["id"] not in {v["id"] for v in selected}
                    and q["group"] != "manual"
                    and math.hypot(p["x"] - q["x"], p["y"] - q["y"])
                    < options.get("recommendation_separation_m", 0)
                ]
                for p in selected
            },
        )


def score(run, profile):
    from .working_waypoints import DisplayRun

    selected = selection(run)
    if selected["profile"] != profile:
        raise ValueError("Habitat preference changed; reload")
    result = HabitatRun(DisplayRun(run, None), load(profile, run)).results()
    if selection(run) != selected:
        raise ValueError("Habitat preference changed during scoring; retry")
    # Preference-only re-ranking may issue no tile requests. Apply the existing
    # display budget here as well, so idle derived caches cannot grow unbounded.
    from .display_cache import maybe_evict

    with locked(STATE / "maintenance"):
        maybe_evict()
    return result


def overlay(run, cid):
    """Separate sealed display raster. Original terrain masks remain unchanged."""
    from .tiles import rgba_file

    mask, check = run.run.mask(cid)
    target = run.filtered.matching
    layers = run.layers
    path_source = run.run.visibility_path(cid)
    key = digest(
        [
            run.prepared["identity"],
            run.profile["id"],
            cid,
            run.run.working.get(cid, {}).get("revision", "original"),
            identity(path_source),
        ]
    )
    path = STATE / "cache" / "habitat" / "overlays" / key / "priority.tif"
    with locked(STATE / "maintenance"), BUILD:
        seal = read_json(path.parent / "seal.json")
        if path.exists() and seal:
            verify(path, seal["sha256"])
            return path
        rgba = np.zeros((*mask.shape, 4), np.uint8)
        matching = mask & target
        rgba[matching] = [90, 107, 120, 100]  # known, nonpriority
        rgba[matching & ~layers["known"]] = [235, 177, 70, 210]  # explicit unknown
        rgba[
            matching & layers["known"] & (habitat.priority(layers, run.settings) > 0)
        ] = [112, 226, 84, 235]
        before = identity(path_source)
        with locked(STATE / "maintenance"):
            recheck(run.sources)
            from .working_waypoints import snapshot

            if (
                before != identity(path_source)
                or snapshot(run.id, None)["overrides"] != run.run.working
            ):
                raise ValueError("Habitat mask changed during overlay creation")
            rgba_file(path, rgba, run.dem)
            write(
                path.parent / "seal.json", dict(sha256=file_digest(path), identity=key)
            )
        return path
