"""Timed experimental objective. Sparse unselected support, exact maxima, bounded allocation.

Policies are engineering assumptions. No probability, foreground transmission or
biological inference is introduced here. Existing static policy is unchanged.
"""

from dataclasses import dataclass
import itertools
import math
import time

import numpy as np

from trail_scout.storage import atomic, checked, digest, file_hash, read, seal
from . import model
from .engine import community_layers
from .package import CommunityPackage, installed_root

VERSION = "practical-timed-1"


def settings(value):
    if not isinstance(value, dict) or set(value) - {
        "version",
        "policy",
        "search_minutes_cap",
    }:
        raise ValueError("Unknown timed practical setting")
    if type(value.get("version", 1)) is not int or value.get("version", 1) != 1:
        raise ValueError("Unsupported timed practical version")
    cap = value.get("search_minutes_cap")
    if cap is not None and (
        type(cap) not in (float, int) or not math.isfinite(cap) or not 0 <= cap <= 720
    ):
        raise ValueError("Timed per-stop cap must be null or finite 0–720 minutes")
    if "policy" in value and not isinstance(value["policy"], dict):
        raise ValueError("Timed policy must be an object")
    policy = model.settings(value.get("policy"))
    # scan_minutes belongs solely to the static comparison, never timed visits.
    if "scan_minutes" in value.get("policy", {}):
        raise ValueError(
            "Use search_minutes_cap for timed plans; scan_minutes is static-only"
        )
    policy.pop("scan_minutes")
    return dict(version=1, policy=policy, search_minutes_cap=cap)


def knapsack(rewards, costs, minutes):
    """Exact independent whole-patch knapsack, vectorized conservative 1/4 min DP."""
    rewards, costs = np.asarray(rewards, float), np.asarray(costs, int)
    if (
        not np.isfinite(rewards).all()
        or np.any(rewards < 0)
        or np.any(costs <= 0)
        or not math.isfinite(minutes)
        or minutes < 0
    ):
        raise ValueError("Invalid scan reward/cost/budget")
    cap = min(int(math.floor(minutes * 4 + 1e-9)), int(costs[rewards > 0].sum()))
    best = np.zeros(cap + 1)
    decisions = np.zeros((len(rewards), cap + 1), bool)
    for i, (value, cost) in enumerate(zip(rewards, costs)):
        if value <= 0 or cost > cap:
            continue
        proposal = best[:-cost] + value
        improve = proposal > best[cost:] + 1e-10
        decisions[i, cost:] = improve
        best[cost:] = np.where(improve, proposal, best[cost:])
    selected = []
    left = cap
    for i in range(len(rewards) - 1, -1, -1):
        if decisions[i, left]:
            selected.append(i)
            left -= int(costs[i])
    return sorted(selected)


@dataclass
class Support:
    indices: np.ndarray
    q: np.ndarray
    known: np.ndarray
    patch: np.ndarray
    group: np.ndarray
    patches: list

    def __post_init__(self):
        n = len(self.indices)
        if (
            any(len(a) != n for a in (self.q, self.known, self.patch, self.group))
            or (n and (np.any(np.diff(self.indices) <= 0) or np.any(self.indices < 0)))
            or not np.isfinite(self.q).all()
            or np.any(self.q < 0)
            or np.any(self.q > 1)
            or np.any(self.patch < 0)
            or np.any(self.patch >= len(self.patches))
            or np.any(self.q[~self.known] > 0)
        ):
            raise ValueError(
                "Invalid sparse timed support; no imputation or negative/duplicate indices"
            )

    def selected(self, chosen):
        return np.where(np.isin(self.patch, chosen), self.q, 0)


def patch_geometry(dx, dy, radius):
    distance = np.hypot(dx, dy)
    rings = math.ceil(radius / 500)
    ids = np.minimum((distance / 500).astype(int), rings - 1) * 12 + np.minimum(
        ((np.degrees(np.arctan2(dx, dy)) % 360) / 30).astype(int), 11
    )
    patches = []
    for ring in range(rings):
        for az in range(12):
            inner, outer = ring * 500, min((ring + 1) * 500, radius)
            area = math.radians(30) * (outer**2 - inner**2) / 2 / 1e6
            patches.append(
                dict(
                    id=len(patches),
                    azimuth_start=az * 30,
                    azimuth_end=(az + 1) * 30,
                    inner_m=inner,
                    outer_m=outer,
                    full_area_km2=area,
                    cost_units=max(1, math.ceil((area / 0.02 + 0.5) * 4 - 1e-9)),
                )
            )
    return ids, patches


def union_values(supports, selected):
    """Compact union only; no candidate × analysis grid cube."""
    if not supports:
        return np.array([], dtype=np.int64), np.array([], float), []
    indices = np.unique(np.concatenate([p.indices for p in supports]))
    mappings = [np.searchsorted(indices, p.indices) for p in supports]
    best = np.zeros(len(indices))
    for p, choice, mapping in zip(supports, selected, mappings):
        np.maximum.at(best, mapping, p.selected(choice))
    return indices, best, mappings


def allocate(supports, budgets, area=100, joint=True, cancel=lambda: None):
    """Multi-start marginal knapsacks + two coordinate sweeps; no global guarantee.

    Each block is solved exactly conditional on other visits. Keep the best seed,
    including independent allocation. Costs are full fixed footprints. A longer
    visit is bounded by all positive patches, never silently clamped to 120 min.
    """
    if len(supports) != len(budgets) or not 1 <= len(supports) <= 2:
        raise ValueError("One or two visit budgets required")
    _, _, mappings = union_values(supports, [[] for _ in supports])
    size = max((int(m.max()) + 1 for m in mappings if len(m)), default=0)
    costs = [np.array([p["cost_units"] for p in s.patches]) for s in supports]

    def choose(i, other):
        p = supports[i]
        marginal = np.maximum(0, p.q - other[mappings[i]])
        reward = np.bincount(p.patch, weights=marginal * area, minlength=len(p.patches))
        return knapsack(reward, costs[i], budgets[i])

    def score(choices):
        best = np.zeros(size)
        for p, choice, mapping in zip(supports, choices, mappings):
            np.maximum.at(best, mapping, p.selected(choice))
        return float(best.sum(dtype=np.float64) * area)

    independent = [choose(i, np.zeros(size)) for i in range(len(supports))]
    winner, value = independent, score(independent)
    if joint and len(supports) == 2:
        for order in itertools.permutations(range(len(supports))):
            choices = [[] for _ in supports]
            for _ in range(3):
                for i in order:
                    cancel()
                    other = np.zeros(size)
                    for j, (p, mapping) in enumerate(zip(supports, mappings)):
                        if j != i:
                            np.maximum.at(other, mapping, p.selected(choices[j]))
                    candidate = choose(i, other)
                    before = score(choices)
                    trial = [*choices]
                    trial[i] = candidate
                    if score(trial) >= before - 1e-8:
                        choices = trial
            v = score(choices)
            if v > value + 1e-8:
                winner, value = choices, v
    return winner, value


def metrics(supports, choices, budgets, observation, area=100):
    indices, best, mappings = union_values(supports, choices)
    known = np.zeros(len(indices), bool)
    searched = np.zeros(len(indices), bool)
    for p, choice, mapping in zip(supports, choices, mappings):
        known[mapping] |= p.known
        searched[mapping] |= np.isin(p.patch, choice)
    total = float(best.sum(dtype=np.float64) * area)
    visits = []
    prior = np.zeros(len(indices))
    for i, (p, choice, mapping) in enumerate(zip(supports, choices, mappings)):
        values = p.selected(choice)
        after = prior.copy()
        np.maximum.at(after, mapping, values)
        others = np.zeros(len(indices))
        for j, (s, m) in enumerate(zip(supports, mappings)):
            if j != i:
                np.maximum.at(others, m, s.selected(choices[j]))
        cards = []
        for ident in choice:
            card = dict(p.patches[ident])
            mask = p.patch == ident
            card.update(
                relative_m2=float(values[mask].sum() * area),
                minutes=card["cost_units"] / 4,
            )
            cards.append(card)
        cards.sort(key=lambda p: (-p["relative_m2"], p["id"]))
        used = sum(p["minutes"] for p in cards)
        bands = [
            dict(
                from_m=lo,
                to_m=lo + 500,
                relative_m2=float(values[(p.patch // 12) == lo // 500].sum() * area),
                physical_m2=int(((p.patch // 12) == lo // 500).sum()) * area,
                supported_m2=int((((p.patch // 12) == lo // 500) & p.known).sum())
                * area,
                selected_terrain_m2=int(
                    (((p.patch // 12) == lo // 500) & np.isin(p.patch, choice)).sum()
                )
                * area,
            )
            for lo in range(0, len(p.patches) // 12 * 500, 500)
        ]
        visits.append(
            dict(
                patches=cards,
                minutes_used=used,
                budget_minutes=budgets[i],
                observation_minutes=observation[i],
                unused_observation_minutes=max(0, observation[i] - used),
                marginal_relative_m2=float((after - prior).sum() * area),
                exclusive_relative_m2=float(np.maximum(0, best - others).sum() * area),
                standalone_selected_relative_m2=float(values.sum() * area),
                bands=bands,
                community_relative_m2={
                    name: float(values[p.group == k].sum() * area)
                    for k, name in enumerate(model.GROUPS)
                },
            )
        )
        prior = after
    standalone = sum(v["standalone_selected_relative_m2"] for v in visits)
    return dict(
        version=VERSION,
        status="scored_conditional" if known.any() else "insufficient_data",
        relative_m2=total if known.any() else None,
        terrain_m2=len(indices) * area,
        supported_m2=int(known.sum()) * area,
        unknown_m2=int((~known).sum()) * area,
        supported_fraction=float(known.mean()) if len(known) else None,
        searched_terrain_m2=int(searched.sum()) * area,
        searched_supported_m2=int((searched & known).sum()) * area,
        searched_unknown_m2=int((searched & ~known).sum()) * area,
        positive_opportunity_support_m2=int((best > 0).sum()) * area,
        overlap_relative_m2=standalone - total,
        visits=visits,
        foreground_status="uninspected; no numerical foreground adjustment",
        bounds=dict(
            lower_relative_m2=0,
            upper_relative_m2=total + int((~known).sum()) * area,
            interpretation="Assumption envelope, not confidence interval; lower permits complete foreground obstruction",
        ),
    )


class Objective:
    def __init__(
        self,
        paths,
        pack,
        terrain,
        old,
        target,
        rows,
        masks,
        config,
        cancel=lambda: None,
    ):
        begin = time.perf_counter()
        self.config = settings(config)
        self.package = CommunityPackage(installed_root(paths))
        if self.package.spec["base_manifest_sha256"] != file_hash(
            pack.folder / "pack.json"
        ):
            raise ValueError("Community companion differs from terrain pack")
        self.area = terrain.res**2
        self.support = {}
        self.new = None
        self.hits = 0
        memory = 0
        for row in rows:
            cancel()
            ident = row["id"]
            identity = dict(
                version=VERSION,
                package=self.package.spec["id"],
                sources=pack.revision,
                grid=[terrain.gt, terrain.a.shape],
                coordinate=[row["x"], row["y"]],
                mask=row["mask_key"],
                target=digest(np.packbits(target).tobytes().hex()),
                policy=self.config["policy"],
            )
            key = digest(identity)
            folder = paths.state / "cache/timed-support" / key
            path = folder / "support.npz"
            if path.exists():
                with np.load(checked(path), allow_pickle=False) as z:
                    arrays = {
                        k: z[k] for k in ("indices", "q", "known", "patch", "group")
                    }
                metadata = read(checked(folder / "patches.json"))
                self.hits += 1
            else:
                if self.new is None:
                    self.new = community_layers(
                        self.package, terrain.ds, self.config["policy"]
                    )
                new = self.new
                indices = np.flatnonzero(masks[ident] & target).astype(np.int32)
                rr, cc = np.divmod(indices, terrain.a.shape[1])
                dx = terrain.gt[0] + (cc + 0.5) * terrain.gt[1] - row["x"]
                dy = terrain.gt[3] + (rr + 0.5) * terrain.gt[5] - row["y"]
                get = lambda a: np.asarray(a).ravel()[indices]
                known = get(new["known"]) & (get(old["known"]) | (get(new["h"]) == 0))
                g = model.concealment(
                    get(old["tree"]),
                    get(old["shrub"]),
                    get(new["deciduous"]),
                    self.config["policy"]["leaf"],
                )
                q = np.where(
                    known,
                    np.where(
                        get(new["h"]) == 0,
                        0,
                        get(new["h"])
                        * g
                        * model.distance_preference(
                            np.hypot(dx, dy), self.config["policy"]["task"]
                        ),
                    ),
                    0,
                )
                patch, cards = patch_geometry(dx, dy, row["radius_m"])
                arrays = dict(
                    indices=indices,
                    q=q,
                    known=known,
                    patch=patch.astype(np.uint8),
                    group=get(new["group"]),
                )
                metadata = dict(identity=identity, patches=cards)
                folder.mkdir(parents=True, exist_ok=True)
                with path.open("wb") as f:
                    np.savez_compressed(f, **arrays)
                seal(path)
                atomic(folder / "patches.json", metadata)
                seal(folder / "patches.json")
            memory += sum(a.nbytes for a in arrays.values())
            if memory > 256 * 1024**2:
                raise ValueError(
                    "Timed support exceeds 256 MiB bound; reduce corridor/radius/candidate budget"
                )
            self.support[ident] = Support(**arrays, patches=metadata["patches"])
        self.seconds = time.perf_counter() - begin
        self.bytes = memory

    def score(self, ids, variant, cancel=lambda: None, joint=True, cap_override=False):
        if not variant["feasible"]:
            return None
        obs = [e["minutes"] for e in variant["events"] if e["kind"] == "observe"]
        cap = (
            self.config["search_minutes_cap"] if cap_override is False else cap_override
        )
        budgets = [min(t, cap) if cap is not None else t for t in obs]
        supports = [self.support[i] for i in ids]
        choices, _ = allocate(supports, budgets, self.area, joint, cancel)
        return metrics(supports, choices, budgets, obs, self.area)
