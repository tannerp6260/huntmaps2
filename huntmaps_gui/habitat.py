"""GUI structural preference v1. Pure arrays, metric areas; no wildlife predictions."""

import math
import numpy as np
from scipy.ndimage import label
from scipy.signal import fftconvolve

VERSION = "rcmap-structure-v1"
NAMES = ("background", "browse", "mixed", "cover")
DEFAULTS = dict(
    version=1,
    preset="fall-mixed",
    local_radius_m=90,
    landscape_radius_m=270,
    weights=[0.10, 0.45, 0.25, 0.20],
    tree_penalty=0.90,
    shrub_penalty=0.65,
    habitat_threshold=0.45,
    glassability_threshold=0.45,
)


def validate(value=None):
    if value is None:
        value = {}
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError("Unknown habitat setting")
    s = dict(DEFAULTS, **value)
    if (
        type(s["version"]) is not int
        or s["version"] != 1
        or s["preset"] not in ("fall-mixed", "custom")
    ):
        raise ValueError("Unsupported habitat preset/version")
    for k, choices in (
        ("local_radius_m", (60, 90, 120)),
        ("landscape_radius_m", (180, 270, 360)),
    ):
        if type(s[k]) is not int or s[k] not in choices:
            raise ValueError("Use a supported habitat neighborhood in metres")
    w = s["weights"]
    if (
        not isinstance(w, (list, tuple))
        or len(w) != 4
        or any(
            type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
            for v in w
        )
        or sum(w) <= 0
    ):
        raise ValueError(
            "Use four finite nonnegative habitat weights with a positive total"
        )
    s["weights"] = [float(v / sum(w)) for v in w]
    for key in (
        "tree_penalty",
        "shrub_penalty",
        "habitat_threshold",
        "glassability_threshold",
    ):
        if (
            type(s[key]) not in (int, float)
            or not math.isfinite(s[key])
            or not 0 <= s[key] <= 1
        ):
            raise ValueError("Habitat penalties/thresholds must be finite within 0–1")
        s[key] = float(s[key])
    if s["preset"] == "fall-mixed" and any(
        s[k] != DEFAULTS[k] for k in DEFAULTS if k != "preset"
    ):
        raise ValueError("Changed habitat settings require the Custom profile")
    return s


def valid_cover(a):
    return np.isfinite(a) & (a >= 0) & (a <= 1)


def patches(mask):
    """At least three 4-connected coarse cells; no isolated texture reward."""
    ids, _ = label(mask)
    counts = np.bincount(ids.ravel())
    counts[0] = 0
    return counts[ids] >= 3


def neighborhood(value, known, resolution, radius):
    n = int(np.ceil(radius / resolution))
    r, c = np.mgrid[-n : n + 1, -n : n + 1]
    disk = ((r * r + c * c) * resolution**2 <= radius**2).astype(float)
    count = np.rint(fftconvolve(known.astype(float), disk, mode="same"))
    total = fftconvolve(np.where(known, value, 0), disk, mode="same")
    if value.dtype == np.bool_:
        # Integral patch counts must not create tiny positive FFT rewards.
        total = np.rint(total)
    # Full intended disk is the denominator, including outside source bounds.
    return np.clip(total / np.maximum(count, 1), 0, 1), count / disk.sum()


def features(tree, shrub, resolution, settings):
    s = validate(settings)
    if (
        tree.shape != shrub.shape
        or tree.ndim != 2
        or not math.isfinite(resolution)
        or resolution < 30
    ):
        raise ValueError(
            "Habitat needs aligned two-dimensional cover at >=30 m support"
        )
    known = valid_cover(tree) & valid_cover(shrub)
    t, b = np.where(known, tree, 0), np.where(known, shrub, 0)
    cover = patches(known & (np.maximum(t, b) >= 0.35))
    opening = patches(known & (t <= 0.20) & (b >= 0.05))
    oc, local_support = neighborhood(opening, known, resolution, s["local_radius_m"])
    cc, _ = neighborhood(cover, known, resolution, s["local_radius_m"])
    landscape, landscape_support = neighborhood(
        cover, known, resolution, s["landscape_radius_m"]
    )
    return dict(
        tree=t,
        shrub=b,
        browse=b / (b + 0.15),
        mixed=np.minimum(oc / 0.30, 1) * np.minimum(cc / 0.30, 1),
        cover=np.minimum(landscape / 0.30, 1),
        known=known & (local_support >= 0.8 - 1e-9) & (landscape_support >= 0.8 - 1e-9),
        support=np.minimum(local_support, landscape_support),
    )


def evaluate(f, settings):
    s = validate(settings)
    components = (
        np.stack([np.ones_like(f["tree"]), f["browse"], f["mixed"], f["cover"]])
        * np.array(s["weights"])[:, None, None]
    )
    h = components.sum(axis=0)
    g = (1 - s["tree_penalty"] * f["tree"]) * (1 - s["shrub_penalty"] * f["shrub"])
    return dict(h=h, g=g, known=f["known"], components=components)


def priority(layers, settings):
    if "priority_fraction" in layers:
        return layers["priority_fraction"]
    return (
        layers["known"]
        & (layers["h"] >= settings["habitat_threshold"])
        & (layers["g"] >= settings["glassability_threshold"])
    )


def metrics(layers, visible, matching, area_m2, settings):
    if (
        not math.isfinite(area_m2)
        or area_m2 <= 0
        or visible.shape != matching.shape
        or visible.shape != layers["known"].shape
    ):
        raise ValueError(
            "Habitat metrics need aligned masks and positive metric cell area"
        )
    matched = visible & matching
    known = matched & layers["known"]
    n = int(known.sum())
    adjusted = layers.get(
        "effective_components", layers["components"] * layers["g"][None, :, :]
    )
    contributions = {
        name: float(np.sum(component[known], dtype=np.float64) * area_m2)
        for name, component in zip(NAMES, adjusted)
    }
    # Identical additive equation for E and the displayed reconciled explanation.
    e = sum(contributions.values()) if n else None
    return dict(
        status="scored" if n else "insufficient_data",
        effective_m2=e,
        current_visible_m2=float(visible.sum() * area_m2),
        matching_m2=float(matched.sum() * area_m2),
        scorable_m2=float(n * area_m2),
        scorable_fraction=float(n / matched.sum()) if matched.any() else None,
        habitat_unknown_m2=float((matched & ~layers["known"]).sum() * area_m2),
        high_habitat_m2=float(
            np.sum(
                layers.get(
                    "high_fraction", layers["h"] >= settings["habitat_threshold"]
                )[known],
                dtype=np.float64,
            )
            * area_m2
        ),
        priority_m2=float(
            np.sum(priority(layers, settings)[known], dtype=np.float64) * area_m2
        ),
        component_effective_m2=contributions,
        observation_penalty_m2=float(
            np.sum(
                layers.get("observation_penalty", layers["h"] * (1 - layers["g"]))[
                    known
                ],
                dtype=np.float64,
            )
            * area_m2
        ),
        mean_glassability=float(layers["g"][known].mean()) if n else None,
    )


def order(row):
    h = row.get("habitat", row)
    return (
        h.get("effective_m2") is None,
        -(h.get("effective_m2") or 0),
        -h.get("matching_m2", 0),
        -h.get("current_visible_m2", 0),
        row["id"],
    )


def grid(ds):
    gt, sr = ds.GetGeoTransform(), ds.GetSpatialRef()
    if (
        sr is None
        or not sr.IsProjected()
        or abs(sr.GetLinearUnits() - 1) > 1e-9
        or gt[2] != 0
        or gt[4] != 0
        or gt[1] <= 0
        or gt[5] >= 0
        or not all(math.isfinite(v) for v in gt)
    ):
        raise ValueError("Habitat requires a north-up projected metric grid")
    if ds.RasterXSize * ds.RasterYSize > 3_000_000:
        raise ValueError("Habitat grid exceeds the existing cell limit")
    return gt, abs(gt[1] * gt[5])
