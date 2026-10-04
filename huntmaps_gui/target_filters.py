"""User-selected visible terrain criteria; never alter obstruction elevations."""

import numpy as np
from .approach_search import terrain_properties

ASPECTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
KEYS = ("elevation_m", "slope_deg", "aspects", "tree_percent", "shrub_percent")


def validate(value=None):
    value = value or {}
    if not isinstance(value, dict) or set(value) - set(KEYS) - {"version"}:
        raise ValueError("Unknown visible-terrain filter")
    if value.get("version", 1) != 1:
        raise ValueError("Unsupported visible-terrain filter version")
    result = dict(
        version=1,
        elevation_m=None,
        slope_deg=None,
        aspects=[],
        tree_percent=None,
        shrub_percent=None,
    )
    result.update(value)
    for key in ("elevation_m", "slope_deg", "tree_percent", "shrub_percent"):
        limits = result[key]
        if limits is None:
            continue
        if (
            not isinstance(limits, (list, tuple))
            or len(limits) != 2
            or not all(
                isinstance(n, (int, float))
                and not isinstance(n, bool)
                and np.isfinite(n)
                for n in limits
            )
            or limits[0] > limits[1]
        ):
            raise ValueError("Use ordered finite visible-terrain limits")
        maximum = 90 if key == "slope_deg" else 100 if key.endswith("percent") else None
        if maximum is not None and not 0 <= limits[0] <= limits[1] <= maximum:
            raise ValueError(f"{key} must be within 0–{maximum}")
        result[key] = list(limits)
    if not isinstance(result["aspects"], list) or any(
        not isinstance(a, str) or a not in ASPECTS for a in result["aspects"]
    ):
        raise ValueError("Select supported visible-terrain facing directions")
    result["aspects"] = [a for a in ASPECTS if a in result["aspects"]]
    return result


def masks(dem, gt, settings, tree=None, shrub=None):
    settings = validate(settings)
    matching = np.isfinite(dem)
    unknown = ~np.isfinite(dem)
    slope, aspect = (
        terrain_properties(dem, abs(gt[1]))
        if settings["slope_deg"] is not None or settings["aspects"]
        else (None, None)
    )
    for key, array in (
        ("elevation_m", dem),
        ("slope_deg", slope),
        ("tree_percent", tree),
        ("shrub_percent", shrub),
    ):
        if settings[key] is None:
            continue
        if array is None:
            raise ValueError(f"Missing data for {key}")
        known = np.isfinite(array)
        if key.endswith("percent"):
            known &= (array >= 0) & (array <= 1)
            array = array * 100
        low, high = settings[key]
        unknown |= ~known
        matching &= known & (array >= low) & (array <= high)
    if settings["aspects"]:
        known = np.isfinite(aspect)
        sectors = np.floor(((np.nan_to_num(aspect) + 22.5) % 360) / 45).astype(int)
        matching &= known & np.isin(
            sectors, [ASPECTS.index(a) for a in settings["aspects"]]
        )
        unknown |= ~known
    return matching, unknown


def standing_mask(tree, resolution, radius, threshold):
    from scipy.signal import fftconvolve

    n = int(np.ceil(radius / resolution))
    rr, cc = np.mgrid[-n : n + 1, -n : n + 1]
    kernel = ((rr * rr + cc * cc) * resolution * resolution <= radius * radius).astype(
        "float32"
    )
    known = np.isfinite(tree) & (tree >= 0) & (tree <= 1)
    count = fftconvolve(known.astype("float32"), kernel, mode="same")
    count = np.rint(count)
    total = fftconvolve(np.where(known, tree, 0).astype("float32"), kernel, mode="same")
    return (count / kernel.sum() >= 0.8) & (
        total / np.maximum(count, 1) < threshold / 100 - 1e-7
    )
