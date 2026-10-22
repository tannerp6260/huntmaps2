"""Bounded desktop context, never a canopy-transmission or clear-sightline model."""

import math
import numpy as np
from shapely.geometry import Polygon, Point
from trail_scout.sources import feature, collection
from trail_scout.storage import digest
from trail_scout.render import image_overlay
from . import model


def sector(point, patch, **properties):
    angles = np.linspace(patch["azimuth_start"], patch["azimuth_end"], 9)

    def arc(radius, values):
        return [
            (
                point["x"] + radius * math.sin(math.radians(a)),
                point["y"] + radius * math.cos(math.radians(a)),
            )
            for a in values
        ]

    polygon = Polygon(
        arc(patch["outer_m"], angles) + arc(patch["inner_m"], angles[::-1])
    )
    return feature(
        polygon, kind="selected scan footprint", point=point["id"], **properties
    )


def coarse_risk(tree, shrub, valid):
    tree, shrub, valid = np.asarray(tree), np.asarray(shrub), np.asarray(valid, bool)
    if not valid.any():
        return dict(
            status="unknown/uninspected", valid_fraction=0, elevated_cover_fraction=None
        )
    return dict(
        status="coarse risk",
        valid_fraction=float(valid.mean()),
        elevated_cover_fraction=float(
            ((tree[valid] >= 0.35) | (shrub[valid] >= 0.50)).mean()
        ),
        note="Thresholds reuse the existing coarse observer screen. Cover is not measured horizontal obstruction; low cover does not certify an opening, high cover does not prove blockage.",
    )


def direction_risk(point, patch, terrain, old):
    # Three coarse transects through the full selected azimuth, independent of
    # target eligibility and terrain-visible target cells. No transmission claim.
    angle = np.deg2rad(
        np.linspace(patch["azimuth_start"] + 3, patch["azimuth_end"] - 3, 3)
    )
    result = []
    for inner, outer in ((10, 50), (50, 150), (150, 500)):
        distance = np.arange(inner, outer + 1, 10)
        x = point["x"] + np.sin(angle[:, None]) * distance
        y = point["y"] + np.cos(angle[:, None]) * distance
        cc = np.floor((x - terrain.gt[0]) / terrain.gt[1]).astype(int)
        rr = np.floor((y - terrain.gt[3]) / terrain.gt[5]).astype(int)
        inside = (
            (rr >= 0)
            & (cc >= 0)
            & (rr < terrain.a.shape[0])
            & (cc < terrain.a.shape[1])
        )
        rr = np.clip(rr, 0, terrain.a.shape[0] - 1)
        cc = np.clip(cc, 0, terrain.a.shape[1] - 1)
        tree, shrub = old["tree"][rr, cc], old["shrub"][rr, cc]
        valid = (
            inside
            & np.isfinite(tree)
            & np.isfinite(shrub)
            & (tree >= 0)
            & (tree <= 1)
            & (shrub >= 0)
            & (shrub <= 1)
        )
        result.append(dict(from_m=inner, to_m=outer, **coarse_risk(tree, shrub, valid)))
    return result


def finalists(
    options, objective, terrain, old, paths, cancel=lambda: None, folder=None
):
    """No providers/owner mutations. At most eight distinct points in retained plans."""
    inspected = {}
    gt = terrain.gt
    for option in options:
        option["inspection"] = []
        for point in option["viewpoints"]:
            cancel()
            ident = point["id"]
            if ident not in inspected and len(inspected) < 8:
                x, y = point["x"], point["y"]
                # A 150 m local neighborhood, independent from target eligibility.
                cc = np.arange(
                    max(0, int((x - 150 - gt[0]) / gt[1])),
                    min(terrain.a.shape[1], int((x + 150 - gt[0]) / gt[1]) + 1),
                )
                rr = np.arange(
                    max(0, int((y + 150 - gt[3]) / gt[5])),
                    min(terrain.a.shape[0], int((y - 150 - gt[3]) / gt[5]) + 1),
                )
                yy, xx = np.meshgrid(rr, cc, indexing="ij")
                within = (gt[0] + (xx + 0.5) * gt[1] - x) ** 2 + (
                    gt[3] + (yy + 0.5) * gt[5] - y
                ) ** 2 <= 150**2
                tree, shrub = old["tree"][yy, xx][within], old["shrub"][yy, xx][within]
                valid = (
                    np.isfinite(tree)
                    & np.isfinite(shrub)
                    & (tree >= 0)
                    & (shrub >= 0)
                    & (tree <= 1)
                    & (shrub <= 1)
                )
                inspected[ident] = dict(
                    id=ident,
                    longitude=point["longitude"],
                    latitude=point["latitude"],
                    local_radius_m=150,
                    **coarse_risk(tree, shrub, valid),
                    source="Prepared RCMAP 2023 tree/shrub components; 40 m analytical information support on 10 m terrain grid",
                    source_package=objective.package.spec["id"],
                    eye_m=1.7,
                    target_m=0.8,
                    measured_obstruction="unavailable: no compatible local measured foreground input registered for these positions",
                    perspective_url=None,
                    numerical_adjustment=False,
                    checks=[
                        "Confirm the exact standing opening and selected directions on the ground; relocate/pin if needed",
                        "Inspect trunks, understory, mixed evergreen crowns and terrain; leaf state is assumed",
                        "Current access, parking and target-side permission/stalk/retrieval are unresolved",
                    ],
                    context=feature(
                        Point(x, y).buffer(150), kind="coarse inspection neighborhood"
                    ),
                )
            option["inspection"].append(
                inspected.get(
                    ident,
                    dict(
                        id=ident,
                        status="unknown/uninspected",
                        note="Eight-point finalist inspection bound; no numerical adjustment",
                    ),
                )
            )
        for mode in ("am", "pm"):
            practical = option["schedules"][mode].get("practical")
            if not practical:
                continue
            features = []
            for point, visit in zip(option["viewpoints"], practical["visits"]):
                visit["id"] = point["id"]
                visit["reason"] = (
                    "Adds positive best-view habitat in these selected fixed search sectors; marginal utility excludes already better-covered cells."
                )
                for rank, patch in enumerate(visit["patches"]):
                    patch["foreground_transects"] = direction_risk(
                        point, patch, terrain, old
                    )
                    features.append(
                        sector(
                            point,
                            patch,
                            order=rank + 1,
                            mode=mode,
                            relative_m2=patch["relative_m2"],
                            minutes=patch["minutes"],
                        )
                    )
            practical["sectors"] = collection(features)
            if folder is not None:
                rgba = np.zeros((*terrain.a.shape, 4), np.uint8)
                searched = np.zeros(terrain.a.size, bool)
                known_union = np.zeros(terrain.a.size, bool)
                positive = np.zeros(terrain.a.size, bool)
                for point, visit in zip(option["viewpoints"], practical["visits"]):
                    support = objective.support[point["id"]]
                    chosen = np.isin(support.patch, [p["id"] for p in visit["patches"]])
                    indices = support.indices[chosen]
                    searched[indices] = True
                    known_union[indices] |= support.known[chosen]
                    positive[indices] |= support.q[chosen] > 0
                pixels = rgba.reshape(-1, 4)
                pixels[searched & ~known_union] = [235, 165, 48, 180]
                pixels[searched & known_union & ~positive] = [150, 150, 150, 110]
                pixels[positive] = [28, 174, 128, 175]
                token = digest([option["id"], mode, "selected-support-1"])[:32]
                name = f"coverage-{token}.png"
                image_overlay(terrain, rgba, folder / name)
                practical["coverage_url"] = f"/artifacts/{folder.name}/{name}"
    return inspected
