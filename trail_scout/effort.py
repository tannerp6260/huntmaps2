"""Along-route grade with explicit directional costs and every traversal counted."""

import numpy as np
from scipy.ndimage import median_filter


def clean_profile(distance, raw, noise_m=1.5):
    """Three-sample median, endpoint preservation, then 1.5 m vertical-error simplification.

    Input spacing >=20m. Short 40–60m sustained climbs survive; sub-1.5m
    profile deviations are suppressed. Raw and cleaned evidence retained.
    """
    d, raw = np.asarray(distance, float), np.asarray(raw, float)
    if (
        len(d) != len(raw)
        or len(d) < 2
        or not np.isfinite(raw).all()
        or not np.isfinite(d).all()
        or np.any(np.diff(d) <= 0)
    ):
        raise ValueError(
            "Profile needs finite elevations and strictly increasing distances"
        )
    z = median_filter(raw, size=3, mode="nearest")
    z[0], z[-1] = raw[0], raw[-1]
    # Vertical-error simplification preserves the onset/end of sustained climbs
    # while removing sub-threshold reversals. Unlike extrema-only interpolation,
    # it does not stretch a short climb across a preceding flat approach.
    anchors = {0, len(z) - 1}
    pending = [(0, len(z) - 1)]
    while pending:
        lo, hi = pending.pop()
        if hi - lo < 2:
            continue
        reference = z[lo] + (z[hi] - z[lo]) * (d[lo + 1 : hi] - d[lo]) / (d[hi] - d[lo])
        residual = np.abs(z[lo + 1 : hi] - reference)
        at = int(np.argmax(residual))
        if residual[at] > noise_m:
            middle = lo + 1 + at
            anchors.add(middle)
            pending.extend(((lo, middle), (middle, hi)))
    anchors = sorted(anchors)
    return np.interp(d, d[anchors], z[anchors])


def speed(grade, p, offtrail=False, tree=0, shrub=0):
    """Directional grade speed, anchored to entered flat pace; no extra ascent time.

    Exponential grade response (Tobler-shaped) capped at flat pace: cautious
    descent never receives a speed bonus. Brush is an explicit off-trail factor.
    """
    penalty = np.exp(-3.5 * np.maximum(0, np.abs(np.asarray(grade) + 0.05) - 0.05))
    brush = 1 + (
        0.5 + 1.5 * np.nan_to_num(tree, nan=1) + np.nan_to_num(shrub, nan=1)
    ) * np.asarray(offtrail)
    return p["pace_mph"] * 1609.344 * penalty / brush / p["condition_factor"]


def segments(distance, z, threshold, min_length=60):
    d, z = np.asarray(distance), np.asarray(z)
    delta, dz = np.diff(d), np.diff(z)
    grade = dz / delta
    result = []
    for sign, name in ((1, "uphill"), (-1, "downhill")):
        active = sign * grade >= threshold
        start = None
        for i in range(len(active) + 1):
            if i < len(active) and active[i] and start is None:
                start = i
            if start is not None and (i == len(active) or not active[i]):
                length = d[i] - d[start]
                if length >= min_length - 1e-8:
                    result.append(
                        dict(
                            start_m=float(d[start]),
                            end_m=float(d[i]),
                            length_m=float(length),
                            gain_m=float(abs(z[i] - z[start])),
                            grade=float((z[i] - z[start]) / length),
                            direction=name,
                        )
                    )
                start = None
    return result


def measure(xy, raw, offtrail, p, tree=None, shrub=None, distance=None):
    xy = np.asarray(xy, float)
    raw = np.asarray(raw, float)
    if len(xy) < 2:
        raise ValueError("A traveled route needs at least two distinct coordinates")
    delta = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    if distance is None and np.any(delta <= 1e-8):
        raise ValueError("Duplicate consecutive traveled coordinates")
    d = np.r_[0, np.cumsum(delta)] if distance is None else np.asarray(distance, float)
    delta = np.diff(d)
    z = clean_profile(d, raw)
    dz = np.diff(z)
    grade = dz / delta
    off = np.asarray(offtrail, bool)
    if off.shape != delta.shape:
        raise ValueError("Travel-mode edges must align with actual traversals")
    t = np.zeros(len(delta)) if tree is None else np.asarray(tree)
    s = np.zeros(len(delta)) if shrub is None else np.asarray(shrub)
    hours = delta / speed(grade, p, off, t, s)
    steep = segments(d, z, p["steep_grade"])
    climbs = segments(d, z, 0.001, min_length=0)
    support_starts = d[d <= d[-1] - 60]
    max_sustained = (
        float(
            np.max(
                np.abs(
                    (
                        np.interp(support_starts + 60, d, z)
                        - np.interp(support_starts, d, z)
                    )
                    / 60
                )
            )
        )
        if support_starts.size
        else 0.0
    )
    bands = {
        f"{low:g}–{high:g}%": float(
            delta[(np.abs(grade) >= low / 100) & (np.abs(grade) < high / 100)].sum()
        )
        for low, high in ((0, 5), (5, 10), (10, 15), (15, 25), (25, 1000))
    }
    return dict(
        distance_m=float(d[-1]),
        mapped_m=float(delta[~off].sum()),
        offtrail_m=float(delta[off].sum()),
        ascent_m=float(np.maximum(dz, 0).sum()),
        descent_m=float(np.maximum(-dz, 0).sum()),
        longest_climb_m=max(
            (a["gain_m"] for a in climbs if a["direction"] == "uphill"), default=0
        ),
        hours_low=float(hours.sum()),
        hours_high=float(hours.sum() * p["time_margin"]),
        offtrail_hours_high=float(hours[off].sum() * p["time_margin"]),
        sustained_steep_m=sum(a["length_m"] for a in steep),
        max_sustained_grade=max_sustained,
        steep_sections=steep,
        grade_bands_m=bands,
        profile=[
            dict(
                distance_m=float(a),
                elevation_m=float(b),
                raw_elevation_m=float(c),
                x=float(pt[0]),
                y=float(pt[1]),
            )
            for a, b, c, pt in zip(d, z, raw, xy)
        ],
        support_m=20,
        noise_m=1.5,
    )


def add_metrics(*rows):
    keys = (
        "distance_m",
        "mapped_m",
        "offtrail_m",
        "ascent_m",
        "descent_m",
        "hours_low",
        "hours_high",
        "offtrail_hours_high",
        "sustained_steep_m",
    )
    return {
        **{k: sum(row[k] for row in rows) for k in keys},
        "max_sustained_grade": max(r["max_sustained_grade"] for r in rows),
        "longest_climb_m": max(r["longest_climb_m"] for r in rows),
    }
