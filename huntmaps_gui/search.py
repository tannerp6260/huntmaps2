"""Normal GUI search; frozen terrain calculations and historical generators stay intact."""

import shutil
import math
import time
from pathlib import Path
import numpy as np
from osgeo import gdal
from glassing import core, transfer
from .progress import emit
from .downloads import check_space
from .storage import write
from . import target_filters

VERSION = 1
SAMPLING_VERSION = 2


def validate(c):
    options = c.get("search", {})
    budget = c.get("candidate_count")
    count = options.get("recommendation_count")
    threshold = options.get("tree_threshold_percent")
    target_filters.validate(options.get("target_filters"))
    if (
        options.get("version") != VERSION
        or type(budget) is not int
        or not 12 <= budget <= 5000
    ):
        raise ValueError("Expanded search requires version 1 and 12–5000 evaluations")
    if type(count) is not int or not 1 <= count <= min(200, budget):
        raise ValueError(
            "Recommendations must be 1–200 and cannot exceed the evaluation budget"
        )
    if (
        options.get("nearby_radius_m") not in [10, 30, 60, 120]
        or type(threshold) not in [int, float]
        or not math.isfinite(threshold)
        or not 0 <= threshold <= 100
    ):
        raise ValueError(
            "Choose a supported nearby-cover radius and a finite 0–100% threshold"
        )


def nearby_cover(tree, shrub, gt, point, radius=30, threshold=10):
    """Circular cell-centre neighborhood; missing/outside cells remain unknown."""
    n = math.ceil(radius / abs(gt[1]))
    rr, cc = np.mgrid[
        point["row"] - n : point["row"] + n + 1, point["col"] - n : point["col"] + n + 1
    ]
    inside = ((rr - point["row"]) ** 2 + (cc - point["col"]) ** 2) * gt[
        1
    ] ** 2 <= radius**2
    valid = inside & (rr >= 0) & (rr < tree.shape[0]) & (cc >= 0) & (cc < tree.shape[1])
    tv = tree[rr[valid], cc[valid]]
    sv = shrub[rr[valid], cc[valid]]
    known = np.isfinite(tv) & (tv >= 0) & (tv <= 1)
    sknown = np.isfinite(sv) & (sv >= 0) & (sv <= 1)
    fraction = float(known.sum() / inside.sum())
    mean = float(tv[known].mean()) if known.any() else None
    category = (
        "insufficient coverage"
        if fraction < 0.8
        else "low mapped tree cover" if mean < threshold / 100 else "other known cover"
    )
    return dict(
        foreground_tree_mean=mean,
        foreground_known_fraction=fraction,
        foreground_shrub_mean=float(sv[sknown].mean()) if sknown.any() else None,
        foreground_radius_m=radius,
        foreground_category=category,
    )


def rank(rows):
    if rows and "matching_km2" in rows[0]:
        return sorted(rows, key=lambda p: (-p["matching_km2"], -p["raw_km2"], p["id"]))
    order = {
        "low mapped tree cover": 0,
        "other known cover": 1,
        "insufficient coverage": 2,
    }
    return sorted(
        rows, key=lambda p: (order[p["foreground_category"]], -p["raw_km2"], p["id"])
    )


def spread_recommendations(rows, count, separation):
    """Presentation diversity only: keep scores and all evaluated locations intact."""
    if not math.isfinite(separation) or not 0 <= separation <= 2000:
        raise ValueError("Recommendation separation must be 0–2000 metres")
    selected = []
    for p in rank(
        [
            p
            for p in rows
            if p["group"] != "manual"
            and p.get("standing_eligible", True)
            and p.get("matching_km2", p["raw_km2"]) > 0
        ]
    ):
        if all(
            math.hypot(p["x"] - q["x"], p["y"] - q["y"]) >= separation for q in selected
        ):
            selected.append(p)
            if len(selected) == count:
                break
    return selected


def refine(points, grid, budget, seen, radius=150, spacing=50):
    ds, a, gt, masks = grid
    result = []
    # Round robin across leaders, so a small budget does not favor the first leader.
    offsets = [
        (dx, dy)
        for dx in range(-radius, radius + 1, spacing)
        for dy in range(-radius, radius + 1, spacing)
        if 0 < dx * dx + dy * dy <= radius * radius
    ]
    offsets.sort(key=lambda v: (v[0] * v[0] + v[1] * v[1], v))
    for dx, dy in offsets:
        for p in points[:10]:
            x, y = p["x"] + dx, p["y"] + dy
            r, col = math.floor((y - gt[3]) / gt[5]), math.floor((x - gt[0]) / gt[1])
            if (
                not (
                    0 <= r < a.shape[0]
                    and 0 <= col < a.shape[1]
                    and masks["observer"][r, col]
                )
                or (r, col) in seen
            ):
                continue
            seen.add((r, col))
            x, y = core.xy(gt, r, col)
            result.append(
                dict(
                    id=f"R{len(result)+1:04}",
                    group="refinement",
                    parent=p["id"],
                    x=x,
                    y=y,
                    row=r,
                    col=col,
                    provenance=["normal_search_local_refinement"],
                    access=core.UNKNOWN,
                )
            )
            if len(result) >= budget:
                return result
    return result


def candidates(c):
    root = Path(c["work"])
    bc = transfer.read(root / "core_config.json")
    sampling = root / "sampling"
    sampling.mkdir(exist_ok=True)
    ds, a, gt, masks = core.load_grid(bc)
    if not masks["observer"].any():
        raise ValueError(
            "No eligible observer cells remain; expand the boundary or adjust sampling restrictions"
        )
    manual = transfer.read(root / "manual_import.json")
    allowed = masks["observer"].copy()
    if c["search"].get("avoid_dense_vegetation"):
        tree = gdal.Open(str(root / "tree.tif")).ReadAsArray()
        allowed &= target_filters.standing_mask(
            tree,
            abs(gt[1]),
            c["search"]["nearby_radius_m"],
            c["search"]["tree_threshold_percent"],
        )
        if not allowed.any() and not manual:
            raise ValueError(
                "No standing locations meet the nearby vegetation requirement; relax it or disable Avoid standing in dense vegetation"
            )
    for point in manual:
        point["row"] = math.floor((point["y"] - gt[3]) / gt[5])
        point["col"] = math.floor((point["x"] - gt[0]) / gt[1])
        if (
            not (
                0 <= point["row"] < allowed.shape[0]
                and 0 <= point["col"] < allowed.shape[1]
            )
            or not masks["observer"][point["row"], point["col"]]
        ):
            raise ValueError(
                "Manual location falls in a raster-excluded boundary cell; never snap silently"
            )
        allowed[point["row"], point["col"]] = False
    requested = max(1, int(c["candidate_count"] * 0.8))
    bc.update(candidate_count=min(requested, int(allowed.sum())), work=str(sampling))
    # Give the unchanged generator its own matching preparation record. Main
    # preparation/configuration remains sealed for evaluation and verification.
    meta = transfer.read(root / "prepared.json")
    meta["config"] = bc
    for name in ["dem", "target", "observer"]:
        shutil.copy2(root / (name + ".tif"), sampling / (name + ".tif"))
    core.write_raster(
        sampling / "observer.tif", allowed.astype("uint8"), gt, ds.GetProjection(), 0
    )
    meta["observer_sha256"] = core.digest(sampling / "observer.tif")
    auto = []
    spacing = None
    if bc["candidate_count"]:
        for spacing in sorted(
            set([150, 100, 75, 50, 30, 20, abs(gt[1])]), reverse=True
        ):
            if spacing < abs(gt[1]):
                continue
            bc["spacing_m"] = spacing
            meta["config"] = dict(bc)
            transfer.dump(sampling / "prepared.json", meta)
            try:
                core.generate(bc)
            except ValueError as error:
                if not str(error).startswith(
                    "Only "
                ) or "separated candidates" not in str(error):
                    raise
                continue
            auto = transfer.read(sampling / "candidates.json")
            break
        else:
            # At grid resolution all eligible distinct cells are valid; protect
            # against floating-point distances falling just below that spacing.
            bc["spacing_m"] = abs(gt[1]) * (1 - 1e-9)
            meta["config"] = dict(bc)
            transfer.dump(sampling / "prepared.json", meta)
            core.generate(bc)
            auto = transfer.read(sampling / "candidates.json")
            spacing = abs(gt[1])
    transfer.dump(
        root / "sampling_summary.json",
        dict(
            version=SAMPLING_VERSION,
            requested_broad=requested,
            actual_broad=len(auto),
            spacing_m=spacing,
            eligible_automated_cells=int(allowed.sum()),
            exhaustion_reason=(
                "Eligible cells exhausted" if len(auto) < requested else None
            ),
        ),
    )
    for point in auto:
        point.update(group="automated", id="A" + point["id"][1:])
    for point in manual:
        point["row"] = math.floor((point["y"] - gt[3]) / gt[5])
        point["col"] = math.floor((point["x"] - gt[0]) / gt[1])
        x, y = core.xy(gt, point["row"], point["col"])
        point["containing_cell_centre_offset_m"] = math.hypot(
            x - point["x"], y - point["y"]
        )
        if not masks["observer"][point["row"], point["col"]]:
            raise ValueError(
                "Manual location falls in a raster-excluded boundary cell; never snap silently"
            )
    transfer.dump(root / "pool.json", auto + manual)


def prepare(c):
    try:
        return transfer.prepare(c)
    except ValueError as error:
        if str(error) == "Empty observer mask":
            raise ValueError(
                "No eligible observer cells remain; expand the boundary or adjust sampling restrictions"
            ) from error
        raise


def guard_checkpoint(root, identity=None):
    checkpoint = Path(root) / "search-checkpoint.json"
    saved = transfer.read(checkpoint) if checkpoint.exists() else {}
    if saved:
        old = saved.get("identity", {})
        compatible = (
            old == identity
            if identity is not None
            else (
                old.get("algorithm") == core.digest(Path(__file__))
                and old.get("sampling_version") == SAMPLING_VERSION
            )
        )
        if not compatible:
            raise ValueError(
                "Search checkpoint is incompatible with current inputs or implementation; retained unchanged. Use a new run name"
            )
    return saved


def score(c):
    root = Path(c["work"])
    options = c["search"]
    grid = core.load_grid(transfer.read(root / "core_config.json"))
    tree, shrub = [
        gdal.Open(str(root / (k + ".tif"))).ReadAsArray() for k in ["tree", "shrub"]
    ]
    pool = transfer.read(root / "pool.json")
    matching, unknown = target_filters.masks(
        grid[1], grid[2], options.get("target_filters"), tree, shrub
    )
    if options.get("avoid_dense_vegetation"):
        grid[3]["observer"] &= target_filters.standing_mask(
            tree,
            abs(grid[2][1]),
            options["nearby_radius_m"],
            options["tree_threshold_percent"],
        )
    identity = dict(
        version=VERSION,
        sampling_version=SAMPLING_VERSION,
        prepared=core.digest(root / "input_identity.json"),
        algorithm=core.digest(Path(__file__)),
        search_options=options,
        filters_algorithm=core.digest(Path(target_filters.__file__)),
        pool=core.digest(root / "pool.json"),
    )
    checkpoint = root / "search-checkpoint.json"
    saved = guard_checkpoint(root, identity)
    rows, patches = (
        (saved.get("rows", []), saved.get("patches", {}))
        if saved.get("identity") == identity
        else ([], {})
    )
    done = {p["id"] for p in rows}
    start = time.monotonic()
    initial = len(rows)
    total = c["candidate_count"] + sum(p["group"] == "manual" for p in pool)

    def evaluate(points):
        nonlocal rows, patches
        for offset in range(0, len(points), 20):
            batch = [p for p in points[offset : offset + 20] if p["id"] not in done]
            if not batch:
                continue
            check_space(root)
            size = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
            anticipated = len(batch) * (
                (2 * c["radius_m"] / c["resolution_m"] + 3) ** 2 * 2 + 150000
            )
            if size + anticipated >= c["disk_bytes"]:
                raise ValueError(
                    "Search output limit reached; checkpoint retained. Use a smaller search in a new run."
                )
            import signal

            signal.alarm(c["runtime_s"])
            scored, ps = transfer.evaluate(c, batch)
            signal.alarm(0)
            for p in scored:
                p.update(
                    nearby_cover(
                        tree,
                        shrub,
                        grid[2],
                        p,
                        options["nearby_radius_m"],
                        options["tree_threshold_percent"],
                    )
                )
            if options.get("ranking_version") == 2:
                from glassing.review_maps import visible_mask

                area = abs(grid[2][1] * grid[2][5]) / 1e6
                for p in scored:
                    vs = gdal.Open(
                        str(
                            root
                            / "additional_visibility"
                            / f'{p["id"]}_{c["radius_m"]}.tif'
                        )
                    )
                    visible, _ = visible_mask(
                        vs, grid[0], grid[3]["target"], p, c["radius_m"]
                    )
                    p.update(
                        matching_km2=float((visible & matching).sum() * area),
                        matching_unknown_km2=float((visible & unknown).sum() * area),
                        standing_eligible=not options.get("avoid_dense_vegetation")
                        or p["foreground_category"] == "low mapped tree cover",
                    )
            rows.extend(scored)
            patches.update(ps)
            done.update(p["id"] for p in scored)
            write(checkpoint, dict(identity=identity, rows=rows, patches=patches))
            elapsed = time.monotonic() - start
            measured = len(rows) - initial
            remaining = (
                max(0, total - len(rows)) * elapsed / measured if measured else None
            )
            emit(
                "processing",
                "Searching observation setups",
                len(rows),
                total,
                force=True,
                remaining_s=remaining,
            )

    write(checkpoint, dict(identity=identity, rows=rows, patches=patches))
    emit("processing", "Searching observation setups", len(rows), total, force=True)
    evaluate(pool)
    leaders = rank(
        [
            p
            for p in rows
            if p["group"] == "automated"
            and p.get("standing_eligible", True)
            and p.get("matching_km2", p["raw_km2"]) > 0
        ]
    )
    extras = refine(
        leaders,
        grid,
        c["candidate_count"] - sum(p["group"] == "automated" for p in pool),
        {(p["row"], p["col"]) for p in pool},
    )
    requested_total = total
    total = len(pool) + len(extras)
    emit("processing", "Searching observation setups", len(rows), total, force=True)
    evaluate(extras)
    recommended = spread_recommendations(
        rows,
        options["recommendation_count"],
        options.get("recommendation_separation_m", 0),
    )
    selected = {p["id"] for p in recommended}
    for p in rows:
        p["recommended"] = p["id"] in selected
    transfer.dump(root / "scores.json", rows)
    transfer.dump(root / "patches.json", patches)
    transfer.dump(
        root / "refinement.json",
        dict(
            points=[p for p in rows if p["group"] == "refinement"],
            centres=list(dict.fromkeys(p["parent"] for p in extras)),
            primary_pool_unchanged=True,
            warning="Normal-run search extension; historical diagnostics unchanged",
        ),
    )
    # Historical leading collection remains the inherited engine ranking.
    leading = sorted(
        [p for p in rows if p["group"] == "automated"],
        key=lambda p: (-p["selective_score"], p["id"]),
    )[:5] + [p for p in rows if p["group"] == "manual"]
    transfer.dump(root / "leading.json", leading)
    transfer.dump(
        root / "recommendations.json",
        dict(
            version=VERSION,
            options=options,
            evaluated_count=len(rows),
            budget=requested_total,
            ids=[p["id"] for p in recommended],
            nearby_ids={
                p["id"]: [
                    q["id"]
                    for q in rank(rows)
                    if q["id"] not in selected
                    and q["group"] != "manual"
                    and math.hypot(q["x"] - p["x"], q["y"] - p["y"])
                    < options.get("recommendation_separation_m", 0)
                ]
                for p in recommended
            },
            recommendation_note=(
                "Fewer spots have matching visible terrain and fit the eligibility/spacing requirements. Adjust filters or spacing, or review All setups."
                if len(recommended) < options["recommendation_count"]
                else None
            ),
            complete=True,
            unused_budget=requested_total - len(rows),
            sampling=transfer.read(root / "sampling_summary.json"),
            exhaustion_reason=(
                "Eligible cells or nearby refinement opportunities exhausted"
                if len(rows) < requested_total
                else None
            ),
        ),
    )
    vis = {}
    for p in leading:
        vs = gdal.Open(
            str(root / "additional_visibility" / f'{p["id"]}_{c["radius_m"]}.tif')
        )
        _, _, mask = core.score_mask(
            vs, grid[2], grid[1].shape, grid[3]["target"], p["x"], p["y"], c["radius_m"]
        )
        vg = vs.GetGeoTransform()
        r = round((vg[3] - grid[2][3]) / grid[2][5])
        col = round((vg[0] - grid[2][0]) / grid[2][1])
        rr, cc = np.where(mask)
        vis[p["id"]] = set(((rr + r) * grid[1].shape[1] + cc + col).tolist())
    overlap = []
    for i, p in enumerate(leading):
        for other in leading[i + 1 :]:
            u, v = vis[p["id"]], vis[other["id"]]
            inter = len(u & v)
            union = len(u | v)
            overlap.append(
                dict(
                    a=p["id"],
                    b=other["id"],
                    shared_km2=inter * grid[2][1] ** 2 / 1e6,
                    jaccard=inter / union if union else None,
                    fraction_a=inter / len(u) if u else None,
                    fraction_b=inter / len(v) if v else None,
                    distance_m=math.hypot(p["x"] - other["x"], p["y"] - other["y"]),
                )
            )
    transfer.dump(root / "overlap.json", overlap)
    emit(
        "processing",
        "Search complete; preparing review outputs",
        len(rows),
        len(rows),
        force=True,
    )


def guidance(c, root):
    summary = transfer.read(Path(c["work"]) / "recommendations.json")
    text = "# Expanded setup search\n\n"
    text += f"Evaluated {summary['evaluated_count']} locations against a maximum budget of {summary['budget']}; {summary['unused_budget']} evaluations unused. Recommended {len(summary['ids'])} setups.\n\n"
    text += "Recommendations: " + ", ".join(summary["ids"]) + ".\n\n"
    text += f"Broad terrain sampling uses 80% of the automated budget. The remaining 20% tests distinct nearby grid cells within 150 m of up to ten leading setups, at 50 m offsets. A small area may leave refinement budget unused.\n\n"
    text += f"Effective broad spacing: {summary['sampling']['spacing_m']} m. Spacing decreases for small observer areas, down to the analysis grid resolution. {summary.get('exhaustion_reason') or ''}\n\n"
    if c["search"].get("ranking_version") == 2:
        text += "Recommendations rank by visible area meeting all configured target-terrain criteria, then original visible area and stable point ID. Unknown required data does not count as matching area. Nearby vegetation eligibility applies only when enabled; zero-match points remain available but are not recommended.\n\n"
        text += f"Saved target criteria: {c['search'].get('target_filters')}. Avoid standing in dense vegetation: {c['search'].get('avoid_dense_vegetation', False)}.\n\n"
    else:
        text += f"Prefer mapped mean tree cover below {c['search']['tree_threshold_percent']}% within {c['search']['nearby_radius_m']} m, requiring at least 80% known neighborhood coverage. Other known cover follows; insufficient coverage remains last. Within each category order by original terrain-visible area. Shrub cover is shown separately.\n\n"
    text += "Coarse mapping cannot confirm a small clearing, individual trees or eye-height sightlines. Blue coverage uses bare-earth terrain. No global optimum, deer probability or verified access is claimed.\n\n"
    text += "All evaluated setups remain available in the GUI, with exact destination exports. Historical engine leading collections, inspection indices and existing review exports remain available separately. The original inspection assumption and numerical terrain calculations are unchanged.\n\n"
    text += "Search provenance: analysis/recommendations.json, scores.json, sampling/, search-metrics.json and implementation.json. Interrupted searches retain analysis/search-checkpoint.json. Per-batch memory/time, grid, output and free-storage guards remain enforced.\n"
    (root / "SEARCH.md").write_text(text)
    report = root / "REPORT.md"
    value = report.read_text().replace(
        "Local refinement is a density diagnostic and does not replace the original candidate pool.",
        "Expanded normal search includes nearby alternatives in recommendations; see SEARCH.md. Historical diagnostic behavior remains unchanged.",
    )
    report.write_text(
        value
        + "\n## Expanded normal search\n\nSee [SEARCH.md](SEARCH.md) for the GUI recommendations and nearby-cover evidence. The leading alternatives above retain the inherited engine ranking and are separate from the GUI recommendation collection.\n"
    )
