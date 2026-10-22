"""Pure relative-opportunity policy. Values are assumptions, never probabilities."""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re

import numpy as np
from scipy.ndimage import convolve

from glassing.attention import select

VERSION = "community-search-1"
TRAITS = json.loads(Path(__file__).with_name("traits_lf2025.json").read_text())
GROUPS = (
    "unsupported",
    "aspen",
    "aspen_conifer",
    "conifer",
    "mountain_shrub",
    "sage_browse",
    "meadow",
    "nonhabitat",
)
CURVES = {
    "spot": [1, 1, 0.85, 0.6, 0.35, 0],
    "identify": [1, 1, 0.6, 0.25, 0.1, 0],
    "assess": [1, 0.7, 0.25, 0.08, 0.02, 0],
    "uniform": [1, 1, 1, 1, 1, 1],
}
DEFAULTS = dict(
    task="identify",
    leaf="unknown",
    scan_minutes=30,
    context_m=90,
    conifer=0.35,
    meadow=0.5,
)


def settings(value=None):
    if value is not None and (
        not isinstance(value, dict) or set(value) - set(DEFAULTS)
    ):
        raise ValueError("Unknown practical policy setting")
    s = dict(DEFAULTS, **(value or {}))
    if s["task"] not in CURVES or s["leaf"] not in ("unknown", "on", "partial", "off"):
        raise ValueError("Unsupported task or leaf assumption")
    if type(s["context_m"]) is not int or s["context_m"] not in (0, 90, 180):
        raise ValueError("Unsupported context radius")
    for k, lo, hi in (("scan_minutes", 0, 120), ("conifer", 0, 1), ("meadow", 0, 1)):
        if (
            type(s[k]) not in (int, float)
            or not math.isfinite(s[k])
            or not lo <= s[k] <= hi
        ):
            raise ValueError("Invalid practical policy " + k)
    return s


def decode_structure(legend, product):
    """Decode official labels, not numeric offsets or timeless category IDs."""
    if product not in ("EVC", "EVH"):
        raise ValueError("Only EVC/EVH have structural labels")
    quantity, unit = ("Cover", "%") if product == "EVC" else ("Height", "meters?")
    pattern = re.compile(rf"^(Tree|Shrub|Herb) {quantity} = ([0-9.]+)\s*{unit}$")
    decoded = {}
    for code, row in legend.items():
        match = pattern.fullmatch(row["CLASSNAMES"])
        if match:
            lifeform, value = match.groups()
            value = float(value)
            if value < 0 or (product == "EVC" and value > 100):
                raise ValueError("Invalid structure units")
            decoded[int(code)] = dict(
                lifeform=lifeform,
                value=value,
                units="percent" if product == "EVC" else "metres",
            )
    if not decoded:
        raise ValueError("No recognized release-specific structure labels")
    return decoded


def community(evt, evc, evh, legends, resolution=30, policy=None):
    s = settings(policy)
    if (
        evt.ndim != 2
        or evt.shape != evc.shape
        or evt.shape != evh.shape
        or not 30 <= resolution <= 120
    ):
        raise ValueError("Aligned coarse community arrays required")
    for a, key in ((evt, "EVT"), (evc, "EVC"), (evh, "EVH")):
        if not np.isfinite(a).all() or np.any(a != np.trunc(a)):
            raise ValueError("Categorical values must be finite exact codes")
        if set(int(x) for x in np.unique(a)) - set(legends[key]):
            raise ValueError("Class code absent from pinned release legend")
    group = np.zeros(evt.shape, dtype=np.uint8)
    for code, trait in TRAITS["classes"].items():
        if (
            int(code) not in legends["EVT"]
            or legends["EVT"][int(code)]["EVT_NAME"] != trait["name"]
        ):
            raise ValueError("Release/class meaning mismatch")
        group[evt == int(code)] = GROUPS.index(trait["group"])
    known = (group > 0) & (evc != -9999) & (evh != -9999)
    nonhabitat = group == GROUPS.index("nonhabitat")
    cover = np.isin(group, [1, 2, 3, 4, 5]).astype(float)
    if s["context_m"]:
        n = math.ceil(s["context_m"] / resolution)
        yy, xx = np.mgrid[-n : n + 1, -n : n + 1]
        kernel = ((xx**2 + yy**2) * resolution**2 <= s["context_m"] ** 2).astype(float)
        support = (
            convolve(known.astype(float), kernel, mode="constant", cval=0)
            / kernel.sum()
        )
        # Entire disk denominator. Unknown neighbors cannot inflate a normalized mean.
        context = (
            convolve(cover * known, kernel, mode="constant", cval=0) / kernel.sum()
        )
        known &= (support >= 1 - 1e-9) | nonhabitat
    else:
        support = known.astype(float)
        context = np.zeros(evt.shape)
    forage = np.array([0, 1, 1, s["conifer"], 1, 1, s["meadow"], 0])[group]
    h = np.where(nonhabitat, 0, 0.8 * forage + 0.2 * context)
    # A single bounded juxtaposition term; no diversity/edge multiplier.
    h = np.where(known, h, np.nan)
    deciduous = np.array([0, 1, 0.5, 0, 0.5, 0, 0, 0])[group]
    height = np.full(evt.shape, np.nan)
    cover_percent = np.full(evt.shape, np.nan)
    for product, array, out in (("EVH", evh, height), ("EVC", evc, cover_percent)):
        for code, decoded in decode_structure(legends[product], product).items():
            out[array == code] = decoded["value"]
    tree_height_codes = [
        c
        for c, d in decode_structure(legends["EVH"], "EVH").items()
        if d["lifeform"] == "Tree" and 1 <= d["value"] <= 5
    ]
    short_aspen = (group == 1) & np.isin(evh, tree_height_codes)
    return dict(
        h=h,
        known=known,
        group=group,
        deciduous=deciduous,
        support=support,
        height=height,
        dominant_cover_percent=cover_percent,
        short_aspen=short_aspen,
        evt=evt,
        evc=evc,
        evh=evh,
    )


def distance_preference(distance, task="identify"):
    d = np.asarray(distance)
    if task not in CURVES or np.any(~np.isfinite(d)) or np.any(d < 0):
        raise ValueError("Finite nonnegative distances and a supported task required")
    return np.interp(
        d,
        [0, 500, 1000, 1500, 2000, 3000],
        CURVES[task],
        right=0 if task != "uniform" else 1,
    )


def concealment(tree, shrub, deciduous, leaf):
    if leaf not in ("unknown", "on", "partial", "off"):
        raise ValueError("Unknown foliage assumption")
    for a in (tree, shrub, deciduous):
        if np.any(np.isfinite(a) & ((a < 0) | (a > 1))):
            raise ValueError("Fractions must be in [0,1], not raw percent")
    discount = {"unknown": 0, "on": 0, "partial": 0.15, "off": 0.30}[leaf]
    return (1 - 0.90 * tree * (1 - discount * deciduous)) * (1 - 0.65 * shrub)


def allocate(dx, dy, q, cell_area, radius, minutes):
    """Fixed whole polar patches. Invisible/depth-overlap never lowers scan cost."""
    if (
        not 0 < radius <= 3000
        or cell_area <= 0
        or not np.isfinite(q).all()
        or np.any(q < 0)
    ):
        raise ValueError("Invalid scan inputs")
    distances = np.hypot(dx, dy)
    azimuth = np.degrees(np.arctan2(dx, dy)) % 360
    rings = math.ceil(radius / 500)
    ring = np.minimum(np.floor(distances / 500).astype(int), rings - 1)
    ids = ring * 12 + np.minimum((azimuth / 30).astype(int), 11)
    values = np.bincount(
        ids,
        weights=np.where(distances <= radius, q * cell_area, 0),
        minlength=rings * 12,
    )
    patches = []
    for band in range(rings):
        for sector in range(12):
            inner, outer = band * 500, min((band + 1) * 500, radius)
            ident = band * 12 + sector
            patches.append(
                dict(
                    id=ident,
                    azimuth_start=sector * 30,
                    azimuth_end=(sector + 1) * 30,
                    inner_m=inner,
                    outer_m=outer,
                    full_area_km2=math.radians(30) * (outer**2 - inner**2) / 2 / 1e6,
                    reward=float(values[ident]),
                )
            )
    allocation = select(patches, minutes)
    chosen = set(allocation["patch_ids"])
    selected = np.isin(ids, list(chosen)) & (distances <= radius)
    cards = [dict(p, relative_m2=p["reward"]) for p in patches if p["id"] in chosen]
    cards.sort(key=lambda p: (-p["reward"], p["id"]))
    return selected, dict(
        allocation,
        patches=cards,
        cost_note="Fixed full polar footprint; uncalibrated rate, occluded/depth-overlapping terrain does not make scans cheaper",
    )


@dataclass(frozen=True)
class Visit:
    indices: np.ndarray
    values: np.ndarray

    def validate(self, size):
        if (
            self.indices.ndim != 1
            or self.values.shape != self.indices.shape
            or not np.issubdtype(self.indices.dtype, np.integer)
        ):
            raise ValueError("Sparse visit needs aligned index/value vectors")
        if (
            np.any(self.indices < 0)
            or np.any(self.indices >= size)
            or np.any(np.diff(self.indices) <= 0)
        ):
            raise ValueError("Sparse indices must be sorted, unique and inside domain")
        if (
            not np.isfinite(self.values).all()
            or np.any(self.values < 0)
            or np.any(self.values > 1 + 1e-12)
        ):
            raise ValueError(
                "Visit values must be finite nonnegative relative indices <=1"
            )


def best_view(visits, size, area=1):
    if (
        type(size) is not int
        or not 0 <= size <= 3_000_000
        or not math.isfinite(area)
        or area <= 0
    ):
        raise ValueError("Bounded metric domain required")
    best = np.zeros(size, dtype=np.float64)
    for v in visits:
        v.validate(size)
        best[v.indices] = np.maximum(best[v.indices], v.values)
    return float(best.sum(dtype=np.float64) * area), best


def shortlist(rows, loader, size, area, count=5, separation=0, kept=(), swaps=True):
    """Exact sparse marginals, deterministic greedy and one bounded swap pass."""
    if not 0 <= count <= 5 or separation < 0 or len(set(kept)) != len(kept):
        raise ValueError("Invalid bounded shortlist")
    by_id = {r["id"]: r for r in rows}
    if len(by_id) != len(rows) or set(kept) - set(by_id):
        raise ValueError("Duplicate IDs or missing retained point")
    selected = list(kept)
    _, best = best_view((loader(i) for i in selected), size, area)

    def spaced(ident, members):
        p = by_id[ident]
        return all(
            math.hypot(p["x"] - by_id[j]["x"], p["y"] - by_id[j]["y"]) >= separation
            for j in members
        )

    for _ in range(max(0, count - len(selected))):
        winner, gain = None, 0.0
        for ident in sorted(by_id):
            if ident in selected or not spaced(ident, selected):
                continue
            v = loader(ident)
            v.validate(size)
            delta = float(
                np.maximum(v.values - best[v.indices], 0).sum(dtype=np.float64) * area
            )
            if delta > gain + 1e-9:
                winner, gain = ident, delta
        if winner is None:
            break
        selected.append(winner)
        v = loader(winner)
        best[v.indices] = np.maximum(best[v.indices], v.values)
    if swaps:
        for old in list(selected):
            if old in kept:
                continue
            rest = [i for i in selected if i != old]
            total, prior = best_view((loader(i) for i in rest), size, area)
            current = float(best.sum(dtype=np.float64) * area)
            winner = old
            for ident in sorted(by_id):
                if ident in selected or not spaced(ident, rest):
                    continue
                v = loader(ident)
                delta = float(
                    np.maximum(v.values - prior[v.indices], 0).sum(dtype=np.float64)
                    * area
                )
                if total + delta > current + 1e-9:
                    winner, current = ident, total + delta
            if winner != old:
                selected[selected.index(old)] = winner
                _, best = best_view((loader(i) for i in selected), size, area)
    prior = np.zeros(size, dtype=np.float64)
    members = []
    for ident in selected:
        v = loader(ident)
        marginal = float(
            np.maximum(v.values - prior[v.indices], 0).sum(dtype=np.float64) * area
        )
        prior[v.indices] = np.maximum(prior[v.indices], v.values)
        others, _ = best_view((loader(i) for i in selected if i != ident), size, area)
        members.append(
            dict(
                id=ident,
                incremental_relative_m2=marginal,
                exclusive_improvement_m2=float(best.sum(dtype=np.float64) * area)
                - others,
                retained=ident in kept,
            )
        )
    return dict(
        ids=selected,
        members=members,
        relative_m2=float(best.sum(dtype=np.float64) * area),
        status="static_shortlist",
        timed_plan=False,
        guarantee="bounded greedy plus one swap pass; no global optimum guarantee",
    )
