"""Indexed normal-workflow sampling, preserving the frozen generator's order.

Terrain formulas, RNG calls, strict spacing comparison and provenance updates
mirror glassing.core.generate. The historical implementation remains the oracle.
"""

import json
import math
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter, uniform_filter
from glassing import core


def stamp(path):
    s = Path(path).stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


class TerrainSampler:
    def __init__(self, c):
        self.root = Path(c["work"])
        self.inputs = {
            self.root / (k + ".tif"): stamp(self.root / (k + ".tif"))
            for k in ["dem", "target", "observer"]
        }
        ds, a, self.gt, masks = core.load_grid(c)
        self.shape = a.shape
        self.allowed = allowed = masks["observer"]
        self.config = {k: v for k, v in c.items() if k != "spacing_m"}
        self.hashes = {
            k: json.loads((self.root / "prepared.json").read_text())[k + "_sha256"]
            for k in ["dem", "target", "observer"]
        }
        res = self.gt[1]
        smooth = gaussian_filter(a.astype("float64"), sigma=3)
        gy, gx = np.gradient(smooth, res)
        self.slope = slope = np.degrees(np.arctan(np.hypot(gx, gy)))
        tpi = smooth - uniform_filter(smooth, size=max(3, int(500 / res)))
        bend = np.hypot(*np.gradient(slope, res))
        self.categories = {
            "bench_proxy": allowed & (slope < 12) & (tpi > -10),
            "shoulder_proxy": allowed & (tpi > 5) & (slope >= 8) & (slope < 30),
            "ridge_break_proxy": allowed
            & (tpi > 8)
            & (bend > np.percentile(bend[allowed], 60)),
            "background": allowed,
        }
        self.verify(c)

    def verify(self, c):
        meta = json.loads((self.root / "prepared.json").read_text())
        if meta["config"] != c or meta["implementation_sha256"] != core.digest(
            core.__file__
        ):
            raise ValueError(
                "Configuration changed: rerun prepare and downstream stages"
            )
        if (
            {k: v for k, v in c.items() if k != "spacing_m"} != self.config
            or any(stamp(p) != value for p, value in self.inputs.items())
            or any(meta[k + "_sha256"] != h for k, h in self.hashes.items())
        ):
            raise ValueError("Sampling terrain changed: rerun prepare")

    def generate(self, c):
        self.verify(c)
        gt, allowed, categories, slope = (
            self.gt,
            self.allowed,
            self.categories,
            self.slope,
        )
        res = gt[1]
        rng = np.random.default_rng(c["seed"])
        points, buckets = [], {}
        limit, spacing = c["candidate_count"], c["spacing_m"]
        if not math.isfinite(spacing) or spacing <= 0:
            raise ValueError("Positive finite candidate spacing required")
        squared = spacing**2

        def add(r, col, provenance):
            x, y = core.xy(gt, r, col)
            bx, by = math.floor(x / spacing), math.floor(y / spacing)
            first = len(points)
            for ix in range(bx - 1, bx + 2):
                for iy in range(by - 1, by + 2):
                    for i in buckets.get((ix, iy), ()):
                        p = points[i]
                        if (
                            i < first
                            and (p["x"] - x) ** 2 + (p["y"] - y) ** 2 < squared
                        ):
                            first = i
            if first < len(points):
                nearest = points[first]
                nearest["provenance"] = sorted(
                    set(nearest["provenance"] + [provenance])
                )
                return False
            if len(points) >= limit:
                return False
            buckets.setdefault((bx, by), []).append(len(points))
            points.append(
                dict(
                    id=f"C{len(points)+1:04}",
                    row=int(r),
                    col=int(col),
                    x=x,
                    y=y,
                    provenance=[provenance],
                    access=core.UNKNOWN,
                    slope_deg=float(slope[r, col]),
                )
            )
            return True

        for point in c.get("manual_points", []):
            r = int(math.floor((point["y"] - gt[3]) / gt[5]))
            col = int(math.floor((point["x"] - gt[0]) / res))
            if not (
                0 <= r < self.shape[0] and 0 <= col < self.shape[1] and allowed[r, col]
            ):
                raise ValueError(
                    "Manual point outside observer domain or wrong coordinates"
                )
            add(r, col, "manual:" + point.get("name", "unnamed"))
        rows, cols = np.where(allowed)
        side = max(2, int(math.sqrt(limit * 0.4)))
        for rr in np.array_split(np.arange(rows.min(), rows.max() + 1), side):
            for cc in np.array_split(np.arange(cols.min(), cols.max() + 1), side):
                sub = np.argwhere(allowed[np.ix_(rr, cc)])
                if len(sub):
                    pick = sub[rng.integers(len(sub))]
                    add(rr[pick[0]], cc[pick[1]], "background_stratified")
        pools = {k: rng.permutation(np.argwhere(v)) for k, v in categories.items()}
        cursors = {k: 0 for k in pools}
        while len(points) < limit:
            progressed = False
            for name, pool in pools.items():
                for _ in range(100):
                    i = cursors[name]
                    if i >= len(pool):
                        break
                    cursors[name] += 1
                    progressed = True
                    r, col = pool[i]
                    if add(r, col, name):
                        break
            if not progressed:
                break
        if len(points) < limit:
            raise ValueError(
                f"Only {len(points)} separated candidates; reduce count/spacing explicitly"
            )
        for p in points:
            p["provenance"] = sorted(
                set(
                    p["provenance"]
                    + [
                        k
                        for k, m in categories.items()
                        if k != "background" and m[p["row"], p["col"]]
                    ]
                )
            )
        self.verify(c)
        core.dump(self.root / "candidates.json", points)
        core.dump(
            self.root / "candidates_meta.json",
            dict(
                prepared_sha256=core.digest(self.root / "prepared.json"),
                candidates_sha256=core.digest(self.root / "candidates.json"),
            ),
        )
