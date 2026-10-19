"""Disposable read-only real-area and spatial synthetic habitat benchmarks."""

import argparse
import json
import os
from pathlib import Path
import resource
import statistics
import tempfile
import time
from unittest.mock import patch

import numpy as np
from huntmaps_gui.config import AppConfig, configured, PROJECT
from huntmaps_gui import (
    habitat as h,
    habitat_service as s,
    complementary as c,
    scouting_filters,
)
from huntmaps_gui.working_waypoints import DisplayRun


def timing(fn):
    start = time.perf_counter()
    v = fn()
    return v, time.perf_counter() - start


def real(run, root):
    workspace = root / "workspace" / run
    workspace.mkdir(parents=True, exist_ok=True)
    with configured(AppConfig(state_dir=root / run, workspace=workspace)), patch(
        "urllib.request.urlopen", side_effect=AssertionError("No network")
    ), patch(
        "glassing.core.viewshed", side_effect=AssertionError("No visibility generation")
    ):
        r = DisplayRun(run, None)
        from huntmaps_gui.target_filters import KEYS

        search = r.config.get("search", {})
        saved_targets = search.get("target_filters", {})
        target = scouting_filters.save(run, {k: saved_targets.get(k) for k in KEYS})[
            "id"
        ]
        choice = s.choose(run, dict(settings={}, target_profile=target, revision=0))
        profile = s.load(choice["profile"], run)
        sources = s.source_inventory(r.config, r.path, r.validate)
        _, cold_context = timing(lambda: s.context(sources, h.validate()))
        _, warm_context = timing(lambda: s.context(sources, h.validate()))
        default, cold_score = timing(lambda: s.score(run, choice["profile"]))
        warm = []
        for _ in range(3):
            v, elapsed = timing(lambda: s.score(run, choice["profile"]))
            warm.append(elapsed)
        hr = s.HabitatRun(r, profile)
        layers = hr.layers
        selected = default["candidates"][0]["id"]
        _, overlay_cold = timing(lambda: s.overlay(hr, selected))
        _, overlay_warm = timing(lambda: s.overlay(hr, selected))
        collection, collection_cold = timing(
            lambda: c.calculate(
                run, 5, profile=target, habitat_profile=choice["profile"]
            )
        )
        _, collection_warm = timing(
            lambda: c.calculate(
                run, 5, profile=target, habitat_profile=choice["profile"]
            )
        )

        def common_utility(ids):
            union = np.zeros(layers["known"].shape, bool)
            increments = []
            for cid in ids:
                mask = r.mask(cid)[0] & hr.filtered.matching
                increments.append(
                    float(
                        np.sum(
                            (layers["h"] * layers["g"])[
                                mask & ~union & layers["known"]
                            ],
                            dtype=np.float64,
                        )
                        * hr.area
                    )
                )
                union |= mask
            return dict(
                effective_m2=float(
                    np.sum(
                        (layers["h"] * layers["g"])[union & layers["known"]],
                        dtype=np.float64,
                    )
                    * hr.area
                ),
                priority_m2=float(
                    np.sum(
                        h.priority(layers, hr.settings)[union & layers["known"]],
                        dtype=np.float64,
                    )
                    * hr.area
                ),
                increments=increments,
            )

        ids = [p["id"] for p in collection["suggestions"]]
        independently = common_utility(ids)
        assert (
            abs(independently["effective_m2"] - collection["combined_effective_m2"])
            < 1e-6
        )
        unweighted, _ = timing(lambda: c.calculate(run, 5, profile=target))
        terrain_ids = [p["id"] for p in unweighted["suggestions"]]
        established = [
            p["id"]
            for p in sorted(
                default["candidates"],
                key=lambda p: (
                    -p.get("matching_m2", 0),
                    -p.get("current_visible_m2", 0),
                    p["id"],
                ),
            )
        ]
        default_ids = [p["id"] for p in default["candidates"]]
        rank = {k: i + 1 for i, k in enumerate(default_ids)}
        scenarios = []
        base_context = c.Context(run, target, None)

        def scenario(label, settings):
            scenario_started = time.perf_counter()
            settings = h.validate(dict(settings, preset="custom"))
            derived, elapsed = timing(lambda: s.prepare(sources, settings, r.dem))
            vals = []
            for cid in r.points:
                m = h.metrics(
                    derived["layers"],
                    r.mask(cid)[0],
                    hr.filtered.matching,
                    hr.area,
                    settings,
                )
                vals.append(dict(m, id=cid))
            vals.sort(key=h.order)
            settings_score_s = time.perf_counter() - scenario_started
            n = [p["id"] for p in vals]
            # Exact greedy scenario collections are all evaluated under the same
            # default weights below; differently scaled profile totals aren't compared.
            rows = [
                dict(
                    r.points[p["id"]],
                    habitat=p,
                    standing_eligible=True,
                    eligible=(p["effective_m2"] or 0) > 0,
                    point={},
                )
                for p in vals
            ]
            scenario_layers = derived["layers"]
            weights = np.where(
                scenario_layers["known"] & hr.filtered.matching,
                scenario_layers["q"] * hr.area,
                0,
            )
            priority = np.where(
                scenario_layers["known"] & hr.filtered.matching,
                h.priority(scenario_layers, settings) * hr.area,
                0,
            )
            collection_started = time.perf_counter()
            selected, _, _ = c.greedy(
                rows,
                [],
                base_context.coverage,
                layers["known"].shape,
                5,
                r.config.get("search", {}).get("recommendation_separation_m", 0),
                weights,
                priority,
            )
            chosen = selected["suggestions"]
            settings_collection_s = time.perf_counter() - collection_started
            scenarios.append(
                dict(
                    name=label,
                    settings=settings,
                    prepare_s=elapsed,
                    settings_score_s=settings_score_s,
                    weighted_collection_s=settings_collection_s,
                    top20_overlap=len(set(n[:20]) & set(default_ids[:20])),
                    top20=n[:20],
                    ranks={k: n.index(k) + 1 for k in default_ids[:20]},
                    common_default_collection=common_utility([p["id"] for p in chosen]),
                    collection_ids=[p["id"] for p in chosen],
                )
            )

        for radii in [(60, 180), (120, 360)]:
            scenario(
                "radii-" + str(radii),
                dict(h.DEFAULTS, local_radius_m=radii[0], landscape_radius_m=radii[1]),
            )
        for i in (1, 2, 3):
            for multiplier in (0.8, 1.2):
                weights = list(h.DEFAULTS["weights"])
                weights[i] *= multiplier
                total = sum(weights)
                weights = [w / total for w in weights]
                scenario(
                    f"weight-{h.NAMES[i]}-{multiplier}",
                    dict(h.DEFAULTS, weights=weights),
                )
            weights = list(h.DEFAULTS["weights"])
            weights[i] = 0
            total = sum(weights)
            weights = [w / total for w in weights]
            scenario("ablate-" + h.NAMES[i], dict(h.DEFAULTS, weights=weights))
        for tp, sp in [(0.75, 0.5), (0.98, 0.8)]:
            scenario(
                "glassability-" + str((tp, sp)),
                dict(h.DEFAULTS, tree_penalty=tp, shrub_penalty=sp),
            )
        rows = default["candidates"]
        return dict(
            run=run,
            comparison_hard_filters=saved_targets,
            candidates=len(rows),
            grid=list(layers["known"].shape),
            source_support_m=default["source_support_m"],
            timings=dict(
                context_cold_s=cold_context,
                context_warm_s=warm_context,
                score_cold_s=cold_score,
                score_warm_repetitions_s=warm,
                overlay_cold_s=overlay_cold,
                overlay_warm_s=overlay_warm,
                collection_cold_s=collection_cold,
                collection_warm_s=collection_warm,
            ),
            top20_overlap=len(set(established[:20]) & set(default_ids[:20])),
            established_top20=established[:20],
            habitat_top20=default_ids[:20],
            top_metrics=rows[:20],
            rank_changes=[
                dict(id=k, established=i + 1, habitat=rank[k])
                for i, k in enumerate(established)
                if i < 20 or rank[k] <= 20
            ],
            habitat_collection=dict(ids=ids, common_default=independently),
            terrain_collection=dict(
                ids=terrain_ids, common_default=common_utility(terrain_ids)
            ),
            scenarios=scenarios,
            packed_cache_bytes=c.CACHE_BYTES,
            mask_density=float(
                np.mean(
                    [
                        base_context.coverage(p).total / np.prod(base_context.shape)
                        for p in base_context.rows
                        if p["id"] in base_context.paths
                    ]
                )
            ),
            peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        )


def synthetic(count):
    shape = (768, 1021)
    rr, cc = np.indices(shape)
    weights = 100 * (0.1 + 0.9 * ((rr + 2 * cc) % 113) / 112)
    priority = ((rr + cc) % 5 == 0) * 100
    masks = {}
    rows = []
    started = time.perf_counter()
    individual_s = 0.0
    for i in range(count):
        x = 60 + (i * 73) % 650
        y = 60 + (i * 97) % 900
        local = (rr - x) ** 2 / (45 + i % 25) ** 2 + (cc - y) ** 2 / (
            50 + i % 37
        ) ** 2 <= 1
        # Spatially varying terrain shadows rather than repeated trivial masks.
        local &= (rr * 3 + cc + i) % 19 > 3
        p = c.pack(local)
        masks[str(i)] = p
        reducing = time.perf_counter()
        utility = p.weighted(None, weights)
        individual_s += time.perf_counter() - reducing
        rows.append(
            dict(
                id=str(i),
                x=float(x),
                y=float(y),
                eligible=True,
                point={},
                utility=utility,
            )
        )
    rows.sort(key=lambda p: (-p["utility"], p["id"]))
    preparation_s = time.perf_counter() - started
    times = []
    for _ in range(3):
        (result, union, _), elapsed = timing(
            lambda: c.greedy(
                rows, [], lambda p: masks[p["id"]], shape, 5, 40, weights, priority
            )
        )
        times.append(elapsed)
    independent = np.zeros(shape, bool)
    for p in result["suggestions"]:
        full = np.zeros_like(union)
        masks[p["id"]].include(full)
        mask = np.unpackbits(full, axis=1)[:, : shape[1]].astype(bool)
        assert (
            abs(
                p["additional_effective_m2"] - float(weights[mask & ~independent].sum())
            )
            < 1e-6
        )
        independent |= mask
    assert (
        abs(result["combined_effective_m2"] - float(weights[independent].sum())) < 1e-6
    )
    return dict(
        candidates=count,
        grid=shape,
        mask_density=float(np.mean([m.total / weights.size for m in masks.values()])),
        packed_bytes=sum(p.data.nbytes for p in masks.values()),
        mask_preparation_and_individual_s=preparation_s,
        individual_packed_reduction_s=individual_s,
        individual_limit="Packed reduction only; saved-mask integrity/grid validation is covered by the real-area scoring timings",
        repetitions_s=times,
        median_s=statistics.median(times),
        ids=[p["id"] for p in result["suggestions"]],
        independent_union_verified=True,
        peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--synthetic-only", action="store_true")
    args = ap.parse_args()
    root = Path(tempfile.mkdtemp(prefix="huntmaps-habitat-benchmark-"))
    result = dict(
        artifacts=str(root),
        cold_definition="New disposable state; OS page cache is not flushed. Saved evaluated coordinates, no owner decisions imported.",
        budgets="After measured 549 baseline: warm scoring <=2s; cold <=15s per saved area; weighted 5000 masks <=30s; overlays cold <=2s/warm <=0.25s; context cold <=2s. Background work must leave API status responsive.",
        real=(
            []
            if args.synthetic_only
            else [
                real(run, root)
                for run in ("scouting-2026-10-16222", "scouting-2026-10-18")
            ]
        ),
        synthetic=[synthetic(n) for n in (549, 1500, 5000)],
    )
    out = Path(args.out) if args.out else root / "results.json"
    out.write_text(json.dumps(result, indent=2))
    print(out)


if __name__ == "__main__":
    main()
