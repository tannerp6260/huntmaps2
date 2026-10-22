"""Reuse sealed route/visibility evidence for schedule/policy edits only.

Profile/date/entry/access/geometry edits miss this cache and use the full planner.
No source check, actual route traversal or mask cell is removed for responsiveness.
"""

from copy import deepcopy
import shutil
import time

import numpy as np
from shapely.geometry import LineString

from trail_scout import render, schedule
from trail_scout.analysis import npz_read
from trail_scout.sources import feature, collection
from trail_scout.storage import atomic, checked, digest, implementation, now, read, seal
from .timed import Objective
from .selection import select_options
from .inspection import finalists


def key(paths, pack, config):
    geometry = {
        k: v
        for k, v in config.items()
        if k not in ("schedule", "practical", "practical_plan")
    }
    return (
        paths.state
        / "cache/timed-routes"
        / digest(
            dict(
                version=1,
                implementation=implementation(),
                sources=pack.revision,
                geometry=geometry,
            )
        )
    )


def store(folder, result, options, paths_by_id, evidence_folder):
    folder.mkdir(parents=True, exist_ok=True)
    clean = [
        {
            k: v
            for k, v in o.items()
            if k not in ("_mask", "schedules", "inspection", "practical_dominated")
        }
        for o in options
    ]
    base = {k: v for k, v in result.items() if k not in ("options", "marginal")}
    base["options"] = []
    base["marginal"] = []
    atomic(
        folder / "basis.json",
        dict(result=base, options=clean, paths_by_id=paths_by_id),
    )
    seal(folder / "basis.json")
    shutil.copyfile(evidence_folder / "relief.png", folder / "relief.png")
    seal(folder / "relief.png")


def run(
    paths, pack, c, folder, terrain, layers, target, basis_folder, progress, cancel
):
    begin = time.perf_counter()
    basis = read(checked(basis_folder / "basis.json"))
    result = deepcopy(basis["result"])
    folder.mkdir(parents=True, exist_ok=True)
    progress(
        "cached-routes",
        0,
        1,
        "Rechecking sealed source/route/mask evidence; allocating new schedule sectors",
    )
    masks = {}
    viable = [r for r in result["candidates"] if r["feasible"]]
    for r in viable:
        cancel()
        z = npz_read(paths.state / "cache/viewsheds" / r["mask_key"] / "mask.npz")
        masks[r["id"]] = (
            np.unpackbits(z["bits"], count=terrain.a.size)
            .reshape(terrain.a.shape)
            .astype(bool)
        )
    objective = Objective(
        paths,
        pack,
        terrain,
        layers,
        target,
        [dict(r, radius_m=c["view_radius_m"]) for r in viable],
        masks,
        c["practical_plan"],
        cancel,
    )
    selection = time.perf_counter()
    options = basis["options"]
    for o in options:
        cancel()
        o["id"] = digest([digest(c), [r["id"] for r in o["viewpoints"]]])[:32]
        o["schedules"] = {
            m: schedule.variant(
                c["date"], result["start"], o["legs"], c["profile"], c["schedule"], m
            )
            for m in ("am", "pm")
        }
        for m in ("am", "pm"):
            v = o["schedules"][m]
            v["practical"] = objective.score(
                [r["id"] for r in o["viewpoints"]], v, cancel
            )
            if v["practical"] and v["practical"]["relative_m2"] is None:
                v["feasible"] = False
                v["reasons"].append(
                    "Insufficient supported community/structure data for practical planning"
                )
        for m in ("combined", "stay"):
            o["schedules"][m] = dict(
                mode=m,
                feasible=False,
                events=[],
                reasons=[
                    "Combined/stay days are established-mode-only; practical mode evaluates one AM or PM outing"
                ],
            )
    frontier, recommended = select_options(options, cancel)
    preferred = [o for o in frontier if o["id"] in recommended.values()]
    retained = []
    for o in preferred + frontier:
        if o not in retained and len(retained) < 6:
            retained.append(o)
    selection_seconds = time.perf_counter() - selection
    inspection = time.perf_counter()
    finalists(retained, objective, terrain, layers, paths, cancel, folder)
    inspection_seconds = time.perf_counter() - inspection
    shutil.copyfile(checked(basis_folder / "relief.png"), folder / "relief.png")
    lines = []
    for o in retained:
        union = np.logical_or.reduce([masks[r["id"]] for r in o["viewpoints"]])
        render.coverage_image(
            terrain, union, layers, target, folder / f"coverage-{o['id']}.png"
        )
        o["coverage_url"] = f"/artifacts/{folder.name}/coverage-{o['id']}.png"
        for r in o["viewpoints"]:
            for segment in basis["paths_by_id"][r["id"]]:
                if segment["offtrail"]:
                    lines.append(
                        feature(
                            LineString(segment["coords"]),
                            kind="offtrail",
                            option=o["id"],
                        )
                    )
    result.update(
        created_utc=now(),
        input_token=digest(c),
        settings=c,
        analysis_id=folder.name,
        options=retained,
        recommended=recommended,
    )
    result["map"].update(
        relief_url=f"/artifacts/{folder.name}/relief.png", spurs=collection(lines)
    )
    result["search"].update(
        returned_variants=len(retained),
        viewshed_cache_hits=len(viable),
        route_basis_reused=True,
    )
    result["practical_plan"].update(
        settings=c["practical_plan"],
        status=(
            "scored_conditional" if retained else "no_positive_supported_feasible_plan"
        ),
        support_cache_hits=objective.hits,
        support_bytes=objective.bytes,
    )
    result["marginal"] = [
        dict(
            id=o["id"],
            viewpoint_ids=[r["id"] for r in o["viewpoints"]],
            hours_high=o["movement"]["hours_high"],
            ascent_m=o["movement"]["ascent_m"],
            effective_m2=o["coverage"]["effective_m2"],
            movement=o["movement"],
            modes={m: o["schedules"][m].get("practical") for m in ("am", "pm")},
        )
        for o in options
    ]
    result["performance"] = dict(
        support_seconds=objective.seconds,
        plan_selection_seconds=selection_seconds,
        inspection_seconds=inspection_seconds,
        route_replan_seconds=time.perf_counter() - begin,
    )
    if not retained:
        result["empty_reason"] = (
            "No feasible supported practical plan in these schedule windows; review time, pins and data support. No objective/profile/start was substituted."
        )
    else:
        result.pop("empty_reason", None)
    pack.recheck()
    return result
