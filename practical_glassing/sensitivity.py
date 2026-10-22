"""Predeclared alternatives on unchanged real coordinates/masks. No retuning."""

import argparse
from pathlib import Path
import resource
import time

from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui.working_waypoints import DisplayRun
from huntmaps_gui import habitat, habitat_service
from trail_scout.storage import Paths, atomic, read, checked

from .package import CommunityPackage, installed_root
from .engine import Visits, evaluate, community_layers
from . import model

ALTERNATIVES = [
    ("conifer_0.20", dict(conifer=0.2)),
    ("conifer_0.50", dict(conifer=0.5)),
    ("meadow_0.35", dict(meadow=0.35)),
    ("meadow_0.65", dict(meadow=0.65)),
    ("context_none", dict(context_m=0)),
    ("context_180m", dict(context_m=180)),
    ("uniform_distance", dict(task="uniform")),
    ("spot", dict(task="spot")),
    ("assess", dict(task="assess")),
    ("scan_15min", dict(scan_minutes=15)),
    ("scan_60min", dict(scan_minutes=60)),
    ("partial_leaf", dict(leaf="partial")),
    ("leaf_off", dict(leaf="off")),
]


def calculate(paths, folder, output):
    report = read(checked(folder / "comparison.json"))
    ident = report["inputs"]["run"]
    base_store = Visits(folder / "visits")
    result = []
    begin = time.perf_counter()
    with configured(
        AppConfig(
            source_dir=paths.source,
            workspace=paths.source,
            state_dir=folder / "adapter-state",
        )
    ):
        run = DisplayRun(ident, None)
        profile = habitat_service.selection(ident)["profile"]
        hr = habitat_service.HabitatRun(run, habitat_service.load(profile, ident))
        old = dict(hr.layers)
        _, context = habitat_service.context(hr.sources, habitat.DEFAULTS)
        for k in ("tree", "shrub"):
            old[k] = habitat_service.warp(
                context[k], tuple(context["gt"]), str(context["wkt"]), run.dem
            )
        package = CommunityPackage(installed_root(paths))
        by_radius = {}
        for label, alternative in ALTERNATIVES:
            start = time.perf_counter()
            policy = model.settings(alternative)
            # Each alternative is evaluated independently, with bounded sparse visits.
            new = community_layers(package, run.dem, policy)
            visits = {}
            scores = {}
            support = {}
            total_bytes = 0
            for row in report["rows"]:
                indices = base_store.get(row["id"], "terrain").indices
                values, info = evaluate(
                    row,
                    indices,
                    tuple(report["grid"]["shape"]),
                    tuple(report["grid"]["gt"]),
                    old,
                    new,
                    report["radius_m"],
                    policy,
                )
                visit = model.Visit(indices, values["combined"])
                visits[row["id"]] = visit
                total_bytes += visit.indices.nbytes + visit.values.nbytes
                if total_bytes > 384 * 1024**2:
                    raise ValueError(
                        "Sensitivity sparse working set exceeds 384 MiB; use a bounded corridor"
                    )
                scores[row["id"]] = info["scores"]["combined"]
                support[row["id"]] = info["support_fraction"]
            rows = [
                r
                for r in report["rows"]
                if r.get("eligible", True) and scores[r["id"]] is not None
            ]
            selection = model.shortlist(
                rows,
                visits.__getitem__,
                hr.filtered.matching.size,
                report["grid"]["area_m2"],
                5,
                report["separation_m"],
            )
            order = sorted(
                scores, key=lambda i: (scores[i] is None, -(scores[i] or 0), i)
            )
            result.append(
                dict(
                    name=label,
                    policy=policy,
                    selection=selection,
                    seconds=time.perf_counter() - start,
                    sparse_bytes=total_bytes,
                    top20_overlap=len(
                        set(order[:20]) & set(report["orders"]["combined"][:20])
                    ),
                    top20=order[:20],
                    ranks={
                        k: order.index(k) + 1 for k in report["orders"]["combined"][:20]
                    },
                    common_reference={
                        arm: model.best_view(
                            (base_store.get(i, arm) for i in selection["ids"]),
                            hr.filtered.matching.size,
                            hr.area,
                        )[0]
                        for arm in ("terrain", "fall_mixed_v1", "combined")
                    },
                    support={i: support[i] for i in selection["ids"]},
                )
            )
            atomic(
                output,
                dict(
                    base_identity=report["identity"],
                    scenarios=result,
                    seconds=time.perf_counter() - begin,
                    peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    note="Assumption sensitivity, same real original coordinates and masks. No biological labels or independently verified sightlines.",
                ),
            )
            print(label, f'{result[-1]["seconds"]:.3f}s', selection["ids"], flush=True)
        hr.validate_snapshot()
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError(
            "Preserve prior sensitivity evidence; choose a new output path"
        )
    calculate(Paths(), a.folder.resolve(), a.out.resolve())


if __name__ == "__main__":
    main()
