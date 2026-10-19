"""Greedy unique terrain coverage over verified saved analytical viewsheds.

Only one unpacked candidate mask is live at a time. Candidate windows are byte
aligned and packed; the LRU has a byte budget rather than a candidate-count budget.
No visibility computation, source acquisition, approach or confirmation occurs here.
"""

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import threading
import time

import numpy as np
from osgeo import gdal
from glassing.transfer import project
from .config import STATE
from .storage import read_json, write, locked
from . import scouting_filters as filters, workflow, manual_observers
from .working_waypoints import DisplayRun
from .display_cache import changed, touch

VERSION = "greedy-coverage-display-v2"
CACHE_BUDGET = 32 * 1024**2
CACHE_ITEMS = 8192  # Bound object overhead, including empty windows.
CACHE = OrderedDict()
CACHE_BYTES = 0
CALCULATION = threading.Lock()
POPCOUNT = np.array([i.bit_count() for i in range(256)], dtype=np.uint8)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def identity(path):
    st = Path(path).stat()
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]


@dataclass(frozen=True)
class Packed:
    row: int
    byte: int
    data: np.ndarray
    total: int

    def window(self, union):
        return union[
            self.row : self.row + self.data.shape[0],
            self.byte : self.byte + self.data.shape[1],
        ]

    def additional(self, union):
        return int(POPCOUNT[self.data & ~self.window(union)].sum())

    def weighted(self, union, weights):
        """Exact float64 reduction of cropped, newly covered bits; bounded rows."""
        total = 0.0
        width = min(self.data.shape[1] * 8, weights.shape[1] - self.byte * 8)
        for start in range(0, self.data.shape[0], 64):
            bits = self.data[start : start + 64]
            if union is not None:
                bits = bits & ~self.window(union)[start : start + 64]
            selected = np.unpackbits(bits, axis=1)[:, :width].astype(bool)
            window = weights[
                self.row + start : self.row + start + len(bits),
                self.byte * 8 : self.byte * 8 + width,
            ]
            total += float(np.sum(window[selected], dtype=np.float64))
        return total

    def include(self, union):
        self.window(union)[:] |= self.data

    def delta(self, union):
        result = np.zeros_like(union)
        self.window(result)[:] = self.data & ~self.window(union)
        return result


def pack(mask):
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    if not len(rows):
        return Packed(0, 0, np.zeros((0, 0), dtype=np.uint8), 0)
    row, end = int(rows.min()), int(rows.max()) + 1
    byte, last = int(cols.min()) // 8, int(cols.max()) // 8 + 1
    data = np.packbits(mask[row:end, byte * 8 : last * 8], axis=1)
    data.flags.writeable = False
    return Packed(row, byte, data, int(mask.sum()))


def greedy(rows, kept, loader, shape, count, separation, weights=None, priority=None):
    """Count includes retained positions. Rank order is supplied by the adapter."""
    union = np.zeros((shape[0], (shape[1] + 7) // 8), dtype=np.uint8)
    included, retained, suggestions, deltas = list(kept), [], [], {}

    def evidence(p, coverage, additional):
        total = coverage.total if coverage is not None else None
        value = dict(
            id=p["id"],
            total_cells=total,
            additional_cells=additional,
            overlap_percent=(100 * (total - additional) / total if total else None),
            point=p["point"],
        )
        if weights is not None:
            for name, raster in (("effective", weights), ("priority", priority)):
                value[f"total_{name}_m2"] = (
                    coverage.weighted(None, raster) if coverage is not None else None
                )
                value[f"additional_{name}_m2"] = (
                    coverage.weighted(union, raster) if coverage is not None else None
                )
            total_e, added_e = (
                value["total_effective_m2"],
                value["additional_effective_m2"],
            )
            value["weighted_overlap_percent"] = (
                100 * (total_e - added_e) / total_e if total_e else None
            )
        return value

    for p in kept:
        coverage = loader(p)
        additional = coverage.additional(union) if coverage is not None else None
        retained.append(evidence(p, coverage, additional))
        if coverage is not None:
            coverage.include(union)
    initial = int(POPCOUNT[union].sum())
    initial_effective = (
        pack(np.unpackbits(union, axis=1)[:, : shape[1]].astype(bool)).weighted(
            None, weights
        )
        if weights is not None
        else None
    )
    initial_priority = (
        pack(np.unpackbits(union, axis=1)[:, : shape[1]].astype(bool)).weighted(
            None, priority
        )
        if weights is not None
        else None
    )
    remaining = [p for p in rows if p["id"] not in {q["id"] for q in kept}]
    while len(included) < count:
        best, maximum = None, 0
        for p in remaining:
            if not p["eligible"] or any(
                math.hypot(p["x"] - q["x"], p["y"] - q["y"]) < separation
                for q in included
            ):
                continue
            coverage = loader(p)
            additional = (
                (
                    coverage.weighted(union, weights)
                    if weights is not None
                    else coverage.additional(union)
                )
                if coverage is not None
                else 0
            )
            # Strict > keeps the pre-existing individual order, then stable ID.
            if additional > maximum:
                best, maximum = p, additional
        if best is None:
            break
        coverage = loader(best)
        deltas[best["id"]] = coverage.delta(union)
        suggestions.append(evidence(best, coverage, coverage.additional(union)))
        coverage.include(union)
        included.append(best)
        remaining = [p for p in remaining if p["id"] != best["id"]]
    result = dict(
        kept=retained,
        suggestions=suggestions,
        initial_cells=initial,
        combined_cells=int(POPCOUNT[union].sum()),
    )
    if weights is not None:
        packed_union = pack(np.unpackbits(union, axis=1)[:, : shape[1]].astype(bool))
        result.update(
            initial_effective_m2=initial_effective,
            initial_priority_m2=initial_priority,
            combined_effective_m2=packed_union.weighted(None, weights),
            combined_priority_m2=packed_union.weighted(None, priority),
        )
    return (
        result,
        union,
        deltas,
    )


def decision_state(run):
    return dict(
        workflow=workflow.records(run),
        annotations=read_json(STATE / "annotations" / f"{run}.json", {}),
        manual=manual_observers.records(run),
        working=read_json(
            STATE / "working-waypoints" / run / "state.json",
            dict(overrides={}, pending={}),
        ),
    )


class Context:
    def __init__(self, ident, profile, jobs, connection_screen="", habitat_profile=""):
        self.run = DisplayRun(ident, jobs)
        r = self.run
        self.connection_screen = connection_screen
        if connection_screen:
            from .connectivity import eligible

            connection_ids = eligible(ident, connection_screen)
        else:
            connection_ids = None
        self.connection_ids = (
            sorted(connection_ids) if connection_ids is not None else []
        )
        if r.dem.RasterXSize * r.dem.RasterYSize > 3_000_000:
            raise ValueError("Collection coverage exceeds the existing grid limit")
        self.state = decision_state(ident)
        if r.working != self.state["working"]["overrides"]:
            raise ValueError(
                "Waypoints changed while reading; calculate the collection again"
            )
        options = r.config.get("search", {})
        self.profile_id = profile or ""
        if profile:
            self.profile = filters.load(profile, ident)
        else:
            # The UI automatically applies saved criteria as a profile. Empty means
            # the user chose Show original terrain; do not reintroduce old filters.
            settings = filters.validate({})
            self.profile = dict(
                id="original-terrain",
                settings=settings,
                sources=[],
                dem_sha256=r.hashes[str(r.dem_path.resolve())],
            )
        self.filtered = filters.FilteredRun(r, self.profile)
        self.habitat_profile = habitat_profile
        from .habitat_service import selection as habitat_selection

        self.habitat_selection = habitat_selection(ident)
        self.habitat = None
        self.weights = self.priority = None
        if habitat_profile:
            from . import habitat_service, habitat

            selected = habitat_service.selection(ident)
            if selected["profile"] != habitat_profile:
                raise ValueError("Habitat preference changed; calculate again")
            spec = habitat_service.load(habitat_profile, ident)
            if spec["target_profile"] != profile:
                raise ValueError(
                    "Habitat and target profiles differ; apply the current preference"
                )
            self.habitat = habitat_service.HabitatRun(r, spec)
            layers = self.habitat.layers
            area_m2 = self.habitat.area
            self.weights = np.where(
                layers["known"] & self.filtered.matching, layers["q"] * area_m2, 0
            )
            self.priority = np.where(
                layers["known"] & self.filtered.matching,
                habitat.priority(layers, spec["settings"]) * area_m2,
                0,
            )
        self.shape = (r.dem.RasterYSize, r.dem.RasterXSize)
        self.cell_km2 = (
            abs(r.dem.GetGeoTransform()[1] * r.dem.GetGeoTransform()[5]) / 1e6
        )
        self.separation = options.get("recommendation_separation_m", 0)
        self.paths = {}
        self.sources = {}
        if self.habitat:
            for source in self.habitat.sources.values():
                self.sources[source["path"]] = [source["sha256"], source["filesystem"]]
            selection_path = STATE / "habitat-selections" / f"{ident}.json"
            self.sources[str(selection_path)] = [None, identity(selection_path)]
        # Include source content hashes AND filesystem identity. Cached masks cannot
        # hide corruption or replacement even when size and mtime are preserved.
        for name in ("dem", "target", "tree", "shrub", "observer"):
            path = r.analysis / (name + ".tif")
            r.validate(path)
            self.sources[str(path)] = [r.hashes[str(path.resolve())], identity(path)]
        for path in (r.analysis / "scores.json", r.base.base / "scouting.json"):
            r.validate(path)
            self.sources[str(path)] = [r.hashes[str(path.resolve())], identity(path)]
        # Validate cover alignment as well as bytes before using cached criteria.
        for name in ("tree", "shrub"):
            r.cover(name)
        target_ds = gdal.Open(str(r.analysis / "target.tif"))
        if (
            target_ds.GetGeoTransform() != r.dem.GetGeoTransform()
            or not target_ds.GetSpatialRef().IsSame(r.dem.GetSpatialRef())
            or (target_ds.RasterYSize, target_ds.RasterXSize) != self.shape
        ):
            raise ValueError("Target mask is not aligned to terrain")
        ds = gdal.Open(str(r.analysis / "observer.tif"))
        if (
            ds.GetGeoTransform() != r.dem.GetGeoTransform()
            or not ds.GetSpatialRef().IsSame(r.dem.GetSpatialRef())
            or (ds.RasterYSize, ds.RasterXSize) != self.shape
        ):
            raise ValueError("Observer eligibility is not aligned to terrain")
        observer = ds.ReadAsArray() == 1
        xy = project(4326, r.config["epsg"])
        self.rows, self.kept, self.unknown = [], [], []
        decisions = self.state["workflow"]["points"]
        ids = sorted(set(r.points) | set(self.state["manual"]) | set(r.working))
        for cid in ids:
            try:
                p = r.candidate(cid)
                point = workflow.point(ident, cid, jobs, r)
            except (ValueError, FileNotFoundError) as error:
                if not self.habitat or (
                    not isinstance(error, FileNotFoundError)
                    and not any(
                        message in str(error)
                        for message in (
                            "No saved visibility",
                            "Current working mask is unavailable",
                        )
                    )
                ):
                    raise
                if cid in r.working:
                    p = r.working[cid]
                    revision = p["revision"]
                else:
                    saved = r.points[cid]
                    lon, lat = r.ll(saved["x"], saved["y"])
                    p = dict(longitude=lon, latitude=lat, metrics=r.rows[cid])
                    revision = workflow.digest([lon, lat])
                point = dict(
                    id=cid,
                    longitude=p["longitude"],
                    latitude=p["latitude"],
                    revision=revision,
                )
            x, y = xy(point["longitude"], point["latitude"])
            if cid in r.points and cid not in r.working:
                # Preserve the original exact projected coordinates, including
                # spacing ties at grid multiples; avoid inverse-CRS roundoff.
                x, y = r.points[cid]["x"], r.points[cid]["y"]
            annotation = (
                r.working.get(cid)
                or self.state["manual"].get(cid)
                or self.state["annotations"].get(cid, {})
            )
            decision = decisions.get(cid, {})
            dismissed = decision.get("dismissed", False)
            kept = (
                decision.get("shortlisted", annotation.get("status") == "keep")
                and not dismissed
            )
            manual = (
                cid.startswith("manual-")
                or r.points.get(cid, {}).get("group") == "manual"
            )
            uncalculated = cid.startswith("manual-") and cid not in r.working
            if not uncalculated:
                try:
                    path = r.visibility_path(cid)
                    self.paths[cid] = path
                    self.sources[str(path)] = [
                        r.hashes.get(
                            str(path.resolve()), r.working.get(cid, {}).get("revision")
                        ),
                        identity(path),
                    ]
                except (ValueError, FileNotFoundError) as error:
                    if not self.habitat or (
                        not isinstance(error, FileNotFoundError)
                        and not any(
                            message in str(error)
                            for message in (
                                "No saved visibility",
                                "Current working mask is unavailable",
                            )
                        )
                    ):
                        raise
                    uncalculated = True
                    parent = (
                        (
                            STATE
                            / "working-waypoints"
                            / ident
                            / "cache"
                            / r.working[cid]["revision"]
                        )
                        if cid in r.working
                        else (
                            r.vegetation / "viewsheds"
                            if r.experimental and cid.startswith("V")
                            else r.analysis / "additional_visibility"
                        )
                    )
                    while not parent.exists():
                        parent = parent.parent
                    self.sources[str(parent)] = [None, identity(parent)]
            gt = r.dem.GetGeoTransform()
            row, col = math.floor((y - gt[3]) / gt[5]), math.floor((x - gt[0]) / gt[1])
            eligible = (
                0 <= row < self.shape[0]
                and 0 <= col < self.shape[1]
                and bool(observer[row, col])
            )
            if connection_ids is not None:
                eligible = eligible and cid in connection_ids
            if self.filtered.standing is not None:
                eligible = eligible and bool(self.filtered.standing[row, col])
            settings = self.filtered.settings
            if settings["distance_m"] is not None or settings["height_m"] is not None:
                eligible = (
                    eligible
                    and filters.access_evidence(
                        (x, y),
                        self.filtered.lines,
                        self.filtered.dem_array,
                        gt,
                        settings,
                        self.filtered.network_index,
                    )["status"]
                    == "qualifies"
                )
            value = dict(
                id=cid,
                point=point,
                x=x,
                y=y,
                eligible=bool(
                    eligible and not dismissed and not manual and not uncalculated
                ),
                raw_km2=p.get("metrics", {}).get("raw_km2", 0),
                foreground_category=r.points.get(cid, {}).get(
                    "foreground_category", "insufficient coverage"
                ),
            )
            self.rows.append(value)
            if kept:
                self.kept.append(value)
                if uncalculated:
                    self.unknown.append(cid)
        self.mask_identity = digest(
            dict(
                version=VERSION,
                profile=self.profile,
                sources=self.sources,
                config=r.config,
                points=r.points,
                working=r.working,
            )
        )
        self.stamp = digest(
            dict(
                version=VERSION,
                run=ident,
                state=self.state,
                profile=self.profile,
                sources=self.sources,
                config=r.config,
                rows=self.rows,
                connection_screen=connection_screen,
                habitat_profile=habitat_profile,
                habitat_selection=self.habitat_selection,
                habitat_identity=(
                    self.habitat.prepared["identity"] if self.habitat else None
                ),
            )
        )

    def coverage(self, p):
        global CACHE_BYTES
        cid = p["id"]
        if cid not in self.paths:
            return None
        key = (self.mask_identity, cid)
        if key in CACHE:
            CACHE.move_to_end(key)
            return CACHE[key]
        # Existing adapters check exact alignment, radius, target intersection and
        # saved area. The current working revision replaces the original mask.
        mask, _ = self.run.mask(cid)
        value = pack(mask & self.filtered.matching)
        while CACHE and (
            CACHE_BYTES + value.data.nbytes > CACHE_BUDGET or len(CACHE) >= CACHE_ITEMS
        ):
            _, old = CACHE.popitem(last=False)
            CACHE_BYTES -= old.data.nbytes
        if value.data.nbytes <= CACHE_BUDGET:
            CACHE[key] = value
            CACHE_BYTES += value.data.nbytes
        return value

    def ranked(self):
        for p in self.rows:
            coverage = self.coverage(p)
            p["matching_cells"] = coverage.total if coverage is not None else 0
        from .search import rank

        rows = [
            dict(p, matching_km2=p["matching_cells"] * self.cell_km2) for p in self.rows
        ]
        if self.habitat:
            for p in rows:
                coverage = self.coverage(p)
                m = (
                    self.habitat.candidate_metrics(p["id"])
                    if coverage is not None
                    else dict(effective_m2=None)
                )
                p["habitat"] = m
            return rank(rows)
        # Historical pre-filter search uses its saved individual cover ordering.
        if (
            not self.profile_id
            and self.run.config.get("search", {}).get("ranking_version", 2) < 2
        ):
            for p in rows:
                p.pop("matching_km2")
        return rank(rows)


def folder(token):
    from .scouting_network import checked_id

    return STATE / "cache" / "collections" / checked_id(token)


def write_mask(path, packed, run, width):
    mask = np.unpackbits(packed, axis=1)[:, :width]
    from .tiles import rgba_file

    rgba = np.zeros((*mask.shape, 4), dtype=np.uint8)
    rgba[:, :, :3] = (
        (0, 192, 232)
        if path.stem == "combined"
        else (170, 111, 255) if path.stem == "shared" else (255, 103, 130)
    )
    rgba[:, :, 3] = mask * 255
    rgba_file(path, rgba, run.dem)


def calculate(
    ident, count=5, profile="", jobs=None, connection_screen="", habitat_profile=""
):
    if type(count) is not int or count not in (3, 4, 5):
        raise ValueError("Choose a collection size from three to five positions")
    started = time.perf_counter()
    with CALCULATION:
        context = Context(ident, profile, jobs, connection_screen, habitat_profile)
        token = digest([context.stamp, count])[:32]
        home = folder(token)
        cached = read_json(home / "result.json")
        if cached and all((home / f"{key}.tif").exists() for key in cached["layers"]):
            touch(home / "result.json")
            return dict(cached, cached=True, elapsed_s=time.perf_counter() - started)
        result, union, deltas = greedy(
            context.ranked(),
            context.kept,
            context.coverage,
            context.shape,
            count,
            context.separation,
            weights=context.weights,
            priority=context.priority,
        )
        area = context.cell_km2
        for p in [*result["kept"], *result["suggestions"]]:
            p["total_km2"] = (
                p["total_cells"] * area if p["total_cells"] is not None else None
            )
            p["additional_km2"] = (
                p["additional_cells"] * area
                if p["additional_cells"] is not None
                else None
            )
            if context.habitat and p["id"] in context.paths:
                metrics = context.habitat.candidate_metrics(p["id"])
                p.update(
                    habitat_status=metrics["status"],
                    scorable_m2=metrics["scorable_m2"],
                    habitat_unknown_m2=metrics["habitat_unknown_m2"],
                )
                if metrics["effective_m2"] is None:
                    p["total_effective_m2"] = p["additional_effective_m2"] = None
        members = [*result["kept"], *result["suggestions"]]
        counts = np.zeros(context.shape, dtype=np.uint16)
        masks = {}
        for member in members:
            packed = context.coverage(dict(id=member["id"]))
            if packed is None:
                continue
            full = np.zeros_like(union)
            packed.include(full)
            mask = np.unpackbits(full, axis=1)[:, : context.shape[1]].astype(bool)
            counts += mask
            masks[member["id"]] = full
        shared = np.packbits(counts >= 2, axis=1)
        if context.habitat:
            covered = counts > 0
            known = context.habitat.layers["known"]
            result.update(
                combined_scorable_m2=float((covered & known).sum()) * area * 1e6,
                combined_habitat_unknown_m2=float((covered & ~known).sum())
                * area
                * 1e6,
                habitat_status=(
                    "scored" if (covered & known).any() else "insufficient_data"
                ),
            )
        unique = {
            cid: np.packbits(
                (np.unpackbits(full, axis=1)[:, : context.shape[1]] > 0)
                & (counts == 1),
                axis=1,
            )
            for cid, full in masks.items()
        }
        layers = [
            "combined",
            "shared",
            *["additional-" + cid for cid in deltas],
            *["unique-" + cid for cid in unique],
        ]
        result.update(
            id=token,
            run_id=ident,
            profile=profile,
            habitat_profile=habitat_profile,
            habitat_selection=context.habitat_selection,
            habitat_identity=(
                context.habitat.prepared["identity"] if context.habitat else None
            ),
            connection_screen=connection_screen,
            connection_eligible=context.connection_ids,
            count=count,
            stamp=context.stamp,
            version=VERSION,
            state=context.state,
            sources=context.sources,
            layers=layers,
            profile_spec=context.profile,
            shared_km2=float((counts >= 2).sum()) * area,
            combined_km2=result["combined_cells"] * area,
            initial_km2=result["initial_cells"] * area,
            unknown_ids=context.unknown,
            separation_m=context.separation,
            cache_bytes=CACHE_BYTES,
            eligible_count=sum(p["eligible"] for p in context.rows),
            evaluated_count=len(context.rows),
            method="Deterministic greedy coverage recommendation; not a proven global optimum or visiting order",
            overlap_denominator="This position's total matching visible area; overlap is the part already covered when it is included",
        )
        from .downloads import check_space

        with locked(STATE / "maintenance"):
            check_space(STATE, len(layers) * context.shape[0] * context.shape[1] * 4)
            if decision_state(ident) != context.state:
                raise ValueError(
                    "Decisions or waypoints changed; calculate the collection again"
                )
            if any(
                identity(path) != saved[1] for path, saved in context.sources.items()
            ):
                raise ValueError("Sources changed during collection calculation; retry")
            write_mask(home / "combined.tif", union, context.run, context.shape[1])
            write_mask(home / "shared.tif", shared, context.run, context.shape[1])
            for cid, mask in unique.items():
                write_mask(
                    home / f"unique-{cid}.tif", mask, context.run, context.shape[1]
                )
            for cid, delta in deltas.items():
                write_mask(
                    home / f"additional-{cid}.tif", delta, context.run, context.shape[1]
                )
            result["layer_hashes"] = {}
            from glassing.core import digest as file_digest

            for key in layers:
                path = home / f"{key}.tif"
                result["layer_hashes"][key] = file_digest(path)
                touch(path)
            result["elapsed_s"] = time.perf_counter() - started
            changed()
            write(home / "result.json", result)
            touch(home / "result.json")
            from .display_cache import maybe_evict, pin

            with pin([home / "result.json", *[home / f"{key}.tif" for key in layers]]):
                maybe_evict()
        return dict(result, cached=False)


def load_result(ident, token):
    result = read_json(folder(token) / "result.json")
    if not result or result["run_id"] != ident or result["version"] != VERSION:
        raise ValueError("Collection preview expired; calculate the collection again")
    if decision_state(ident) != result["state"]:
        raise ValueError(
            "Decisions or waypoints changed; calculate the collection again"
        )
    from .habitat_service import selection as habitat_selection

    if result.get(
        "habitat_selection", dict(profile="", revision=0)
    ) != habitat_selection(ident):
        raise ValueError("Habitat preference changed; calculate the collection again")
    if result.get("connection_screen"):
        from .connectivity import eligible

        ids = eligible(ident, result["connection_screen"])
        if sorted(ids) != result.get("connection_eligible", []):
            raise ValueError(
                "Connection eligibility changed; calculate the collection again"
            )
    if result.get("habitat_profile"):
        from . import habitat_service

        if habitat_service.selection(ident)["profile"] != result["habitat_profile"]:
            raise ValueError(
                "Habitat preference changed; calculate the collection again"
            )
        habitat_service.HabitatRun(
            DisplayRun(ident, None),
            habitat_service.load(result["habitat_profile"], ident),
        )
    for path, (_, expected) in result["sources"].items():
        if identity(path) != expected:
            raise ValueError(
                "Collection sources changed; calculate the collection again"
            )
    if result["profile"]:
        # FilteredRun checks current network provenance and raster integrity too.
        r = DisplayRun(ident, None)
        profile = filters.load(result["profile"], ident)
        if profile != result["profile_spec"]:
            raise ValueError("Collection filters changed; apply the criteria again")
        filters.FilteredRun(r, profile)
    return result


def public_result(result):
    """Do not send source manifests and internal seals to the browser."""
    return {
        key: value
        for key, value in result.items()
        if key not in ("state", "sources", "layer_hashes", "profile_spec", "stamp")
    }


def add(ident, token, jobs):
    """Atomically add the reviewed suggestions. Preserve every existing decision."""
    with CALCULATION, locked(STATE / "maintenance"), locked(workflow.path(ident)):
        result = load_result(ident, token)
        context = Context(
            ident,
            result["profile"],
            jobs,
            result.get("connection_screen", ""),
            result.get("habitat_profile", ""),
        )
        if context.stamp != result["stamp"]:
            raise ValueError(
                "Collection inputs changed; calculate the collection again"
            )
        value = workflow.records(ident)
        for suggestion in result["suggestions"]:
            cid = suggestion["id"]
            current = workflow.point(ident, cid, jobs, context.run)
            if current != suggestion["point"]:
                raise ValueError(
                    "Suggested waypoint changed; calculate the collection again"
                )
            # A suggestion was neither retained nor dismissed in the sealed snapshot.
            value["points"][cid] = dict(
                value["points"].get(cid, {}),
                point=current,
                shortlisted=True,
                dismissed=False,
                confirmed=False,
                updated=time.time(),
            )
        if result["suggestions"]:
            value["version"] = workflow.VERSION
            value["revision"] += 1
            write(workflow.path(ident), value)
    return workflow.get(ident, jobs)


class CollectionRun:
    """Two display layers, using existing tile guards, cache and reprojection limits."""

    collection_preview = True

    def __init__(self, ident, token):
        self.result = load_result(ident, token)
        self.base = DisplayRun(ident, None)
        self.token = token

    def __getattr__(self, name):
        return getattr(self.base, name)

    def visibility_path(self, key):
        if key not in self.result["layers"]:
            raise ValueError("Unknown collection preview layer")
        path = folder(self.token) / f"{key}.tif"
        from .catalog import check_hash

        st = path.stat()
        check_hash(
            str(path),
            st.st_mtime_ns,
            st.st_size,
            self.result["layer_hashes"][key],
            (st.st_dev, st.st_ino, st.st_ctime_ns),
        )
        touch(path)
        return path

    def mask(self, key):
        ds = gdal.Open(str(self.visibility_path(key)))
        return ds.GetRasterBand(4).ReadAsArray() > 0, dict(collection=self.token)
