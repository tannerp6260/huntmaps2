"""Read existing products without changing their sources, masks or owner decisions."""

from pathlib import Path

import numpy as np
from osgeo import gdal

from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui import habitat, habitat_service, scouting_filters, target_filters
from huntmaps_gui.working_waypoints import DisplayRun
from trail_scout.storage import atomic, digest, file_hash, seal

from .engine import compare
from .package import CommunityPackage, installed_root


def saved_run(paths, ident, folder, policy=None, progress=lambda *a: None):
    folder = Path(folder)
    # Explicit original-pool comparison: do not copy or overwrite live owner edits.
    config = AppConfig(
        source_dir=paths.source,
        workspace=paths.source,
        state_dir=folder / "adapter-state",
    )
    with configured(config):
        run = DisplayRun(ident, None)
        search = run.config.get("search", {})
        settings = {
            k: v
            for k, v in target_filters.validate(
                search.get("target_filters", {})
            ).items()
            if k in target_filters.KEYS
        }
        for k in (
            "avoid_dense_vegetation",
            "nearby_radius_m",
            "tree_threshold_percent",
        ):
            if k in search:
                settings[k] = search[k]
        target = scouting_filters.save(ident, settings)["id"]
        chosen = habitat_service.choose(
            ident, dict(settings={}, target_profile=target, revision=0)
        )
        hr = habitat_service.HabitatRun(
            run, habitat_service.load(chosen["profile"], ident)
        )
        baseline = hr.results()
        by_id = {r["id"]: r for r in baseline["candidates"]}
        rows = [
            dict(
                id=p["id"],
                x=p["x"],
                y=p["y"],
                eligible=by_id[p["id"]]["qualifies"],
                original_physical_m2=p["raw_km2"] * 1e6,
            )
            for p in run.points.values()
            if by_id[p["id"]]["status"] != "mask_unavailable"
        ]
        old = dict(hr.layers)
        _, context = habitat_service.context(hr.sources, habitat.DEFAULTS)
        for k in ("tree", "shrub"):
            old[k] = habitat_service.warp(
                context[k], tuple(context["gt"]), str(context["wkt"]), run.dem
            )
        identity = dict(
            run=ident,
            comparison="available real saved pool; NOT replication of missing 549/500 pools",
            coordinates="exact original saved coordinates; live owner edits untouched",
            manifest=run.hashes,
            source_context=hr.prepared["identity"],
            filters=settings,
            posture=dict(eye_m=run.config["eye_m"], target_m=run.config["target_m"]),
            mask_hashes={
                p["id"]: file_hash(run.visibility_path(p["id"])) for p in rows
            },
        )
        report = compare(
            run.dem,
            rows,
            lambda cid: run.mask(cid)[0],
            hr.filtered.matching,
            old,
            CommunityPackage(installed_root(paths)),
            folder,
            identity,
            run.config["radius_m"],
            search.get("recommendation_separation_m", 0),
            policy,
            progress,
        )
        # Independent established-service check: never silently change v1 scores.
        errors = [
            abs(
                (r["scores"]["fall_mixed_v1"] or 0)
                - (by_id[r["id"]]["effective_m2"] or 0)
            )
            for r in report["rows"]
        ]
        if max(errors, default=0) > 1e-6:
            raise ValueError(
                "V1 reproduction exceeded absolute 1e-6 relative-m² tolerance"
            )
        available_ids = {r["id"] for r in report["rows"]}
        canonical_order = [
            r["id"] for r in baseline["candidates"] if r["id"] in available_ids
        ]
        if report["orders"]["fall_mixed_v1"] != canonical_order:
            raise ValueError(
                "V1 canonical ranking differs, including equal-score tie order"
            )
        report["v1_canonical_order_match"] = True
        report["v1_reproduction_max_abs_m2"] = max(errors, default=0)
        report["missing_historical_pools"] = [
            name
            for name in ("scouting-2026-10-16222", "scouting-2026-10-18")
            if not (paths.source / "results" / name / "analysis/scores.json").exists()
        ]
        hr.validate_snapshot()
        from .packet import publish

        publish(folder, report)
        return report


def trail_review(
    paths,
    pack,
    result,
    terrain,
    layers,
    target,
    masks,
    folder,
    policy,
    progress,
    cancel,
):
    rows = [
        dict(
            id=p["id"],
            x=p["x"],
            y=p["y"],
            longitude=p["longitude"],
            latitude=p["latitude"],
            eligible=p["feasible"],
            pinned=p["pinned"],
            movement=p.get("movement"),
            access=p.get("access"),
        )
        for p in result["candidates"]
        if p["id"] in masks
    ]
    package = CommunityPackage(installed_root(paths))
    if package.spec["base_manifest_sha256"] != file_hash(pack.folder / "pack.json"):
        raise ValueError(
            "Community companion and terrain pack identities differ; explicitly prepare compatible sources"
        )
    report = compare(
        terrain.ds,
        rows,
        masks.__getitem__,
        target,
        layers,
        package,
        folder,
        dict(
            analysis=result["analysis_id"],
            source_revision=pack.revision,
            grid=result["grid"],
            settings=result["settings"],
            mask_hashes={k: digest(np.packbits(v).tolist()) for k, v in masks.items()},
        ),
        result["settings"]["view_radius_m"],
        0,
        policy,
        progress,
        cancel,
    )
    report["route_scope"] = (
        "Individual points passed inherited out-and-return screens. The five-point static collection has no combined route/time feasibility. Existing v1 route options stay separate."
    )
    report["original_options"] = [
        dict(
            id=o["id"],
            members=[p["id"] for p in o["viewpoints"]],
            movement=o["movement"],
            schedules=o["schedules"],
        )
        for o in result["options"]
    ]
    from .packet import publish

    publish(folder, report)
    pack.recheck()
    return dict(
        identity=report["identity"],
        policy=report["policy"],
        package=report["package"],
        collections=report["collections"],
        orders=report["orders"],
        rows=report["rows"],
        route_scope=report["route_scope"],
        report_url=f"/practical/{result['analysis_id']}/review.html",
        promotion="experimental_opt_in",
    )
