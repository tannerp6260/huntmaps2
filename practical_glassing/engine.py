"""Windowed adapters and exact sparse five-arm desktop comparison."""

from collections import OrderedDict
import csv
import math
from pathlib import Path
import time

import numpy as np
from osgeo import gdal
from pyproj import Transformer

from huntmaps_gui import habitat, habitat_service
from huntmaps_gui import complementary as legacy_union
from trail_scout.storage import (
    atomic,
    checked,
    digest,
    file_hash,
    read,
    seal,
    implementation,
)
from . import model

ARMS = (
    "terrain",
    "fall_mixed_v1",
    "community_fixed_observation",
    "observation_fixed_habitat",
    "combined",
)


def community_layers(package, dem, policy=None):
    gt, area = habitat.grid(dem)
    if (
        abs(gt[1] + gt[5]) > 1e-8
        or dem.GetSpatialRef().GetAuthorityCode(None) != "32613"
    ):
        raise ValueError("Practical adapter requires square EPSG:32613 metric grid")
    res = 30
    bounds = [
        math.floor((gt[0] - 240) / res) * res,
        math.floor((gt[3] + gt[5] * dem.RasterYSize - 240) / res) * res,
        math.ceil((gt[0] + gt[1] * dem.RasterXSize + 240) / res) * res,
        math.ceil((gt[3] + 240) / res) * res,
    ]
    raw, cg, wkt = package.window(bounds, res)
    coarse = model.community(
        raw["EVT"], raw["EVC"], raw["EVH"], package.legend, res, policy
    )
    layers = {
        k: habitat_service.warp(a.astype(float), cg, wkt, dem, "near")
        for k, a in coarse.items()
    }
    layers["known"] = layers["known"] >= 1 - 1e-9
    layers["group"] = layers["group"].astype(np.uint8)
    layers["short_aspen"] = layers["short_aspen"] == 1
    return layers


class Visits:
    """Disk-backed sparse visits with a bounded LRU; no dense candidate cube."""

    def __init__(self, folder, cap=128 * 1024**2):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.cap, self.bytes = cap, 0
        self.cache = OrderedDict()

    def write(self, ident, indices, values):
        # Candidate identity is encoded, never used as a filesystem path.
        path = self.folder / (digest(ident) + ".npz")
        with path.open("wb") as f:
            np.savez_compressed(f, indices=indices.astype(np.int32), **values)
        seal(path)

    def get(self, ident, arm):
        key = (ident, arm)
        if key not in self.cache:
            with np.load(
                checked(self.folder / (digest(ident) + ".npz")), allow_pickle=False
            ) as z:
                arrays = {"indices": z["indices"], arm: z[arm]}
            n = sum(a.nbytes for a in arrays.values())
            while self.cache and self.bytes + n > self.cap:
                _, removed = self.cache.popitem(last=False)
                self.bytes -= sum(a.nbytes for a in removed.values())
            self.cache[key] = arrays
            self.bytes += n
        self.cache.move_to_end(key)
        arrays = self.cache[key]
        return model.Visit(arrays["indices"], arrays[arm])


def packed_indices(indices, width):
    if not len(indices):
        return legacy_union.Packed(0, 0, np.zeros((0, 0), np.uint8), 0)
    rr, cc = np.divmod(indices, width)
    row, byte = int(rr.min()), int(cc.min()) // 8
    bits = np.zeros((int(rr.max()) - row + 1, int(cc.max()) // 8 - byte + 1), np.uint8)
    np.bitwise_or.at(
        bits, (rr - row, cc // 8 - byte), (128 >> (cc % 8)).astype(np.uint8)
    )
    bits.flags.writeable = False
    return legacy_union.Packed(row, byte, bits, len(indices))


def evaluate(row, indices, shape, gt, old, new, radius, policy):
    s = model.settings(policy)
    rr, cc = np.divmod(indices, shape[1])
    dx = gt[0] + (cc + 0.5) * gt[1] - row["x"]
    dy = gt[3] + (rr + 0.5) * gt[5] - row["y"]
    distance = np.hypot(dx, dy)
    get = lambda a: np.asarray(a).ravel()[indices]
    old_known = get(old["known"])
    new_known = get(new["known"]) & (old_known | (get(new["h"]) == 0))
    h0, h1, g = get(old["h"]), get(new["h"]), get(old["g"])
    base = get(old.get("q", old["h"] * old["g"]))
    if s["leaf"] in ("partial", "off"):
        g = model.concealment(
            get(old["tree"]), get(old["shrub"]), get(new["deciduous"]), s["leaf"]
        )
    dist = model.distance_preference(distance, s["task"])
    values = dict(
        terrain=np.ones(len(indices)),
        fall_mixed_v1=np.where(old_known, base, 0),
        community_fixed_observation=np.where(
            new_known, np.where(h1 == 0, 0, h1 * get(old["g"])), 0
        ),
    )
    allocations = {}
    for arm, known, h in (
        ("observation_fixed_habitat", old_known, h0),
        ("combined", new_known, h1),
    ):
        q = np.where(known, np.where(h == 0, 0, h * g * dist), 0)
        selected, allocation = model.allocate(
            dx, dy, q, abs(gt[1] * gt[5]), radius, s["scan_minutes"]
        )
        values[arm] = np.where(selected, q, 0)
        allocations[arm] = allocation
    area = abs(gt[1] * gt[5])
    totals = {k: float(v.sum(dtype=np.float64) * area) for k, v in values.items()}
    for arm in ARMS[1:]:
        known = (
            old_known
            if arm in ("fall_mixed_v1", "observation_fixed_habitat")
            else new_known
        )
        if not np.any(known):
            totals[arm] = None
    groups = get(new["group"])
    class_areas = {
        name: float((groups == i).sum() * area) for i, name in enumerate(model.GROUPS)
    }
    codes, counts = np.unique(get(new["evt"]).astype(int), return_counts=True)
    bands = []
    for lo, hi in ((0, 500), (500, 1000), (1000, 1500), (1500, 2000), (2000, 3000)):
        m = (distance >= lo) & (distance < hi)
        bands.append(
            dict(
                from_m=lo,
                to_m=hi,
                physical_m2=float(m.sum() * area),
                supported_m2=float((m & new_known).sum() * area),
                relative_m2=float(values["combined"][m].sum(dtype=np.float64) * area),
            )
        )
    return values, dict(
        scores=totals,
        visible_matching_m2=len(indices) * area,
        scorable_m2=float(new_known.sum() * area),
        support_fraction=float(new_known.mean()) if len(indices) else None,
        habitat_unknown_m2=float((~new_known).sum() * area),
        raw_class_m2={str(k): float(n * area) for k, n in zip(codes, counts)},
        foreground_status="uninspected; conditional bare-earth opportunity",
        foreground_unknown_m2=len(indices) * area,
        bounds=dict(
            lower_relative_m2=0,
            upper_relative_m2=float(
                np.sum(np.where(new_known, h1, 1), dtype=np.float64) * area
            ),
            explanation="Loose assumption envelope includes complete foreground obstruction and unknown habitat; not a confidence interval",
        ),
        community_m2=class_areas,
        short_aspen_proxy_m2=float(get(new["short_aspen"]).sum() * area),
        bands=bands,
        scan=allocations["combined"],
        observation_scan=allocations["observation_fixed_habitat"],
        status="scored_conditional" if new_known.any() else "insufficient_data",
    )


def compare(
    dem,
    rows,
    mask,
    matching,
    old,
    package,
    folder,
    identity,
    radius,
    separation=0,
    policy=None,
    progress=lambda *a: None,
    cancel=lambda: None,
    make_maps=True,
):
    started = time.perf_counter()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    policy = model.settings(policy)
    gt, area = habitat.grid(dem)
    shape = (dem.RasterYSize, dem.RasterXSize)
    elevations = dem.ReadAsArray()
    nodata = dem.GetRasterBand(1).GetNoDataValue()
    if not np.isfinite(elevations).all() or (
        nodata is not None and np.any(elevations == nodata)
    ):
        raise ValueError(
            "Obstruction terrain contains NoData; target exclusion cannot remove it"
        )
    if matching.shape != shape or matching.dtype != np.bool_:
        raise ValueError("Exact boolean target/filter domain required")
    new = community_layers(package, dem, policy)
    key = digest(
        dict(
            model=model.VERSION,
            implementation=implementation(),
            traits=model.TRAITS,
            policy=policy,
            inputs=identity,
            package=package.spec["id"],
            grid=[gt, shape],
            rows=rows,
            radius=radius,
            separation=separation,
        )
    )
    store = Visits(folder / "visits")
    output = []
    xy_to_ll = Transformer.from_crs(32613, 4326, always_xy=True)
    for i, row in enumerate(rows):
        cancel()
        progress(
            "practical",
            i,
            len(rows),
            f"Comparing exact view {i+1}/{len(rows)}; habitat and foreground unknowns retained",
        )
        visible = mask(row["id"])
        if visible.shape != shape or visible.dtype != np.bool_:
            raise ValueError("Terrain mask must exactly match metric grid")
        indices = np.flatnonzero(visible & matching)
        values, info = evaluate(row, indices, shape, gt, old, new, radius, policy)
        store.write(row["id"], indices, values)
        lon, lat = xy_to_ll.transform(row["x"], row["y"])
        lon, lat = row.get("longitude", lon), row.get("latitude", lat)
        output.append(dict(row, longitude=lon, latitude=lat, **info))
    scoring_seconds = time.perf_counter() - started
    collections = {}
    orders = {}
    packed = {}

    def old_mask(row):
        ident = row["id"]
        if ident not in packed:
            packed[ident] = packed_indices(
                store.get(ident, "terrain").indices, shape[1]
            )
        return packed[ident]

    shared_weights = {
        "terrain": None,
        "fall_mixed_v1": np.where(old["known"], old.get("q", old["h"] * old["g"]), 0)
        * area,
        "community_fixed_observation": np.where(
            new["known"] & old["known"], new["h"] * old["g"], 0
        )
        * area,
    }
    for arm in ARMS:
        cancel()
        # Same eligible pool in every arm; unsupported scores are null and last.
        ranked = sorted(
            output,
            key=lambda r: (
                r["scores"][arm] is None,
                -(r["scores"][arm] or 0),
                -r["visible_matching_m2"],
                -r.get("original_physical_m2", r["visible_matching_m2"]),
                r["id"],
            ),
        )
        orders[arm] = [r["id"] for r in ranked]
        usable = [
            r
            for r in ranked
            if r.get("eligible", True) and r["scores"][arm] is not None
        ]
        if arm in shared_weights:
            control_rows = [dict(r, point={}) for r in usable]
            control, _, _ = legacy_union.greedy(
                control_rows,
                [],
                old_mask,
                shape,
                5,
                separation,
                shared_weights[arm],
                np.zeros(shape),
            )
            ids = [r["id"] for r in control["suggestions"]]
            collections[arm] = model.shortlist(
                usable,
                lambda ident: store.get(ident, arm),
                matching.size,
                area,
                5,
                separation,
                kept=ids,
                swaps=False,
            )
            for member in collections[arm]["members"]:
                member["retained"] = False
            collections[arm][
                "guarantee"
            ] = "Original packed exact-union greedy, including canonical individual tie order"
        else:
            collections[arm] = model.shortlist(
                usable,
                lambda ident: store.get(ident, arm),
                matching.size,
                area,
                5,
                separation,
                swaps=arm == "combined",
            )
        if output and arm != "terrain" and not usable:
            collections[arm].update(
                relative_m2=None, status="insufficient_data", known_lower_bound_m2=0
            )
    by_id = {r["id"]: r for r in output}
    unions = {}
    for arm, collection in collections.items():
        collection["common_policies"] = {
            other: model.best_view(
                (store.get(i, other) for i in collection["ids"]), matching.size, area
            )[0]
            for other in ARMS
        }
        union = np.zeros(matching.size, bool)
        for ident in collection["ids"]:
            union[store.get(ident, "terrain").indices] = True
        unions[arm] = union
        collection["physical_m2"] = float(union.sum() * area)
        collection["habitat_unknown_m2"] = float(
            (union & ~(new["known"] & old["known"]).ravel()).sum() * area
        )
        collection["nearest_baseline_displacement_m"] = [
            min(
                (
                    math.hypot(
                        by_id[i]["x"] - by_id[j]["x"], by_id[i]["y"] - by_id[j]["y"]
                    )
                    for j in collections["terrain"]["ids"]
                ),
                default=None,
            )
            for i in collection["ids"]
        ]
    overlap = []
    for ia, a in enumerate(ARMS):
        for b in ARMS[ia + 1 :]:
            shared = unions[a] & unions[b]
            either = unions[a] | unions[b]
            q = np.where(old["known"], old.get("q", old["h"] * old["g"]), 0).ravel()
            denominator = float(q[either].sum(dtype=np.float64))
            overlap.append(
                dict(
                    a=a,
                    b=b,
                    physical_shared_m2=float(shared.sum() * area),
                    coverage_jaccard=(
                        float(shared.sum() / either.sum()) if either.any() else None
                    ),
                    v1_weighted_jaccard=(
                        float(q[shared].sum(dtype=np.float64) / denominator)
                        if denominator
                        else None
                    ),
                    top20_overlap=len(set(orders[a][:20]) & set(orders[b][:20])),
                )
            )
    report = dict(
        version=model.VERSION,
        implementation=implementation(),
        identity=key,
        inputs=identity,
        package=package.spec["id"],
        policy=policy,
        arms=list(ARMS),
        orders=orders,
        rows=output,
        collections=collections,
        overlap=overlap,
        grid=dict(gt=gt, shape=shape, epsg=32613, area_m2=area),
        radius_m=radius,
        separation_m=separation,
        scoring_seconds=scoring_seconds,
        total_seconds=time.perf_counter() - started,
        units="relative-index m²; not literal acres searched",
        type="static desktop comparison, not timed or access-certified plan",
        assumptions=[
            "Terrain and old v1 are preserved",
            "Community support 30 m; old habitat support unchanged (typically 40 m)",
            "2023 structural cover and LF2025 communities are separate dated hypotheses, not contemporaneous understory",
            "Foreground and intervening vegetation are unverified; lower assumption bound is zero",
            "No measured hunter pressure or deer probability",
            "Unknown target-side hunt/stalk/retrieval permission is not inferred from unit membership",
        ],
        promotion="experimental_opt_in",
    )
    report["class_traits"] = {
        str(code): dict(
            name=package.legend["EVT"][code]["EVT_NAME"],
            **{
                k: v
                for k, v in model.TRAITS["classes"]
                .get(
                    str(code),
                    dict(
                        group="unsupported",
                        lifeform=package.legend["EVT"][code]["EVT_LF"],
                    ),
                )
                .items()
                if k != "name"
            },
        )
        for code in package.spec["sources"]["EVT"]["codes"]
    }
    report["source_provenance"] = {
        k: {
            field: source[field]
            for field in (
                "provider",
                "product",
                "release",
                "observation_dates",
                "observation_note",
                "retrieved_utc",
                "raw",
                "legend",
                "units",
                "crs",
                "grid",
                "shape",
                "license",
                "gaps",
            )
        }
        for k, source in package.spec["sources"].items()
    }
    atomic(folder / "comparison.json", report)
    seal(folder / "comparison.json")
    with (folder / "points.csv").open("w", newline="") as f:
        fields = [
            "id",
            "longitude",
            "latitude",
            "x",
            "y",
            "eligible",
            "support_fraction",
            "habitat_unknown_m2",
            *ARMS,
        ]
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        for r in output:
            writer.writerow(
                {**{k: r.get(k) for k in fields if k not in ARMS}, **r["scores"]}
            )
    if make_maps:
        from .packet import maps

        maps(folder, dem, new, matching, report, store, unions)
    report["total_seconds"] = time.perf_counter() - started
    atomic(folder / "comparison.json", report)
    seal(folder / "comparison.json")
    if make_maps:
        from .packet import publish

        publish(folder, report)
    # Verify pinned source bytes again before returning a complete artifact.
    from .package import CommunityPackage

    CommunityPackage(package.root, package.spec["id"])
    return report
