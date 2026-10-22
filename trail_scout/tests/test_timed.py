"""Independent exhaustive engineering oracles, not deer observations."""

import itertools
import math
import unittest
import numpy as np
from practical_glassing.timed import Support, allocate, knapsack, metrics, settings
from practical_glassing.selection import select_options
from practical_glassing.inspection import coarse_risk, sector


def support(indices, values, patches, costs=None, known=None):
    n = max(patches, default=-1) + 1
    return Support(
        np.array(indices),
        np.array(values, float),
        np.array(known if known is not None else [True] * len(indices)),
        np.array(patches),
        np.ones(len(indices), np.uint8),
        [
            dict(
                id=i,
                cost_units=(costs or [4] * n)[i],
                inner_m=0,
                outer_m=500,
                azimuth_start=i * 30,
                azimuth_end=(i + 1) * 30,
            )
            for i in range(n)
        ],
    )


def oracle(supports, budgets):
    """Enumerate patch subsets, use a plain cell dictionary for unique utility."""
    choices = []
    for s, minutes in zip(supports, budgets):
        choices.append(
            [
                list(c)
                for n in range(len(s.patches) + 1)
                for c in itertools.combinations(range(len(s.patches)), n)
                if sum(s.patches[i]["cost_units"] for i in c)
                <= math.floor(minutes * 4 + 1e-9)
            ]
        )
    best = 0
    for selection in itertools.product(*choices):
        cells = {}
        for s, c in zip(supports, selection):
            for i, v, p in zip(s.indices, s.q, s.patch):
                if p in c:
                    cells[int(i)] = max(cells.get(int(i), 0), float(v))
        best = max(best, sum(cells.values()))
    return best


class TimedNumerical(unittest.TestCase):
    def test_knapsack_independent_exhaustive(self):
        rng = np.random.default_rng(548)
        for _ in range(60):
            values = rng.integers(0, 20, 6)
            costs = rng.integers(1, 8, 6)
            budget = float(rng.integers(0, 24)) / 4
            chosen = knapsack(values, costs, budget)
            expected = max(
                sum(values[i] for i in c)
                for n in range(7)
                for c in itertools.combinations(range(6), n)
                if sum(costs[i] for i in c) <= budget * 4
            )
            self.assertEqual(sum(values[i] for i in chosen), expected)
            self.assertLessEqual(sum(costs[i] for i in chosen), budget * 4)

    def test_duplicate_and_better_view_marginal_exclusive(self):
        a = support([0, 1], [0.4, 0.8], [0, 0])
        b = support([0, 1], [0.6, 0.5], [0, 0])
        c, v = allocate([a, b], [1, 1], 1)
        self.assertAlmostEqual(v, 1.4)
        m = metrics([a, b], c, [1, 1], [5, 7], 1)
        self.assertAlmostEqual(sum(v["marginal_relative_m2"] for v in m["visits"]), 1.4)
        self.assertAlmostEqual(m["visits"][1]["exclusive_relative_m2"], 0.2)
        self.assertAlmostEqual(m["overlap_relative_m2"], 0.9)
        _, duplicate = allocate([a, a], [1, 1], 1)
        self.assertAlmostEqual(duplicate, 1.2)

    def test_joint_avoids_duplicate_budget_trap_against_oracle(self):
        a = support([0, 1], [1, 0.7], [0, 1])
        b = support([0, 2], [1, 0.9], [0, 1])
        independent, iv = allocate([a, b], [1, 1], 1, joint=False)
        chosen, v = allocate([a, b], [1, 1], 1)
        self.assertEqual(iv, 1)
        self.assertEqual(v, oracle([a, b], [1, 1]))
        self.assertAlmostEqual(v, 1.9)
        self.assertEqual(
            sum(p["cost_units"] for p in a.patches if p["id"] in chosen[0]), 4
        )

    def test_time_exposes_new_patches_no_120_clamp(self):
        a = support([0, 1], [1, 0.5], [0, 1], costs=[400, 400])
        _, one = allocate([a], [120], 1)
        _, both = allocate([a], [210], 1)
        self.assertEqual(one, 1)
        self.assertEqual(both, 1.5)
        self.assertEqual(oracle([a], [210]), both)

    def test_unknown_and_known_zero(self):
        a = support([0], [0], [0], known=[False])
        m = metrics([a], [[]], [5], [5], 100)
        self.assertIsNone(m["relative_m2"])
        self.assertEqual(m["unknown_m2"], 100)
        a.known[:] = True
        m = metrics([a], [[]], [5], [5], 100)
        self.assertEqual(m["relative_m2"], 0)
        self.assertEqual(m["supported_m2"], 100)

    def test_budget_bounds_and_strict_schema(self):
        for v in (
            {"version": 2},
            {"wat": 1},
            {"search_minutes_cap": float("nan")},
            {"policy": {"scan_minutes": 30}},
        ):
            with self.assertRaises(ValueError):
                settings(v)
        self.assertIsNone(settings({})["search_minutes_cap"])
        with self.assertRaises(ValueError):
            knapsack([float("nan")], [1], 5)

    def test_more_time_never_reduces_best_block_value(self):
        a = support([0, 1, 2], [0.2, 0.7, 0.9], [0, 1, 2])
        values = [allocate([a], [t], 1)[1] for t in [0, 0.9, 1, 2, 3, 1000]]
        self.assertEqual(values, sorted(values))

    def test_coarse_cannot_certify_clear_or_blocked(self):
        self.assertEqual(coarse_risk([0], [0], [True])["status"], "coarse risk")
        self.assertEqual(coarse_risk([1], [1], [True])["status"], "coarse risk")
        self.assertEqual(
            coarse_risk([0], [0], [False])["status"], "unknown/uninspected"
        )

    def test_actual_sector_geometry_projected_in_metres(self):
        p = dict(x=307000, y=4270000, id="x")
        f = sector(p, dict(azimuth_start=0, azimuth_end=30, inner_m=0, outer_m=500))
        self.assertEqual(f["geometry"]["type"], "Polygon")
        self.assertTrue(
            all(
                -108 < xy[0] < -106 and 38 < xy[1] < 40
                for xy in f["geometry"]["coordinates"][0]
            )
        )

    def test_am_pm_separate_and_easier_single(self):
        def option(id, am, pm, hours, stops=1):
            return dict(
                id=id,
                viewpoints=[{}] * stops,
                movement=dict(hours_high=hours, ascent_m=0, offtrail_m=0),
                schedules={
                    m: dict(feasible=True, practical=dict(relative_m2=v))
                    for m, v in [("am", am), ("pm", pm)]
                },
            )

        a = option("am", 100, 10, 0.2)
        b = option("pm", 10, 100, 0.2)
        c = option("costly", 105, 105, 1, 2)
        frontier, recommended = select_options([a, b, c])
        self.assertEqual(recommended, dict(am="am", pm="pm"))
        self.assertEqual({o["id"] for o in frontier}, {"am", "pm", "costly"})


if __name__ == "__main__":
    unittest.main()


class TimedSearchOracles(unittest.TestCase):
    def test_complement_outside_old_eight_is_evaluated(self):
        from practical_glassing.selection import member_options

        rows = [dict(id=str(i), feasible=True) for i in range(10)]
        old, _ = member_options(rows, [], False)
        proposed, size = member_options(rows, [], True)
        self.assertEqual(size, 10)
        self.assertEqual(len(proposed), 100)
        self.assertFalse(any(len(m) == 2 and rows[9] in m for m in old))
        # Nine old leaders see the same cell; modest tenth sees distinct habitat.
        supports = {str(i): support([0], [1], [0]) for i in range(9)}
        supports["9"] = support([1], [0.8], [0])
        ranked = sorted(
            (
                (
                    allocate([supports[r["id"]] for r in m], [1] * len(m), 1)[1],
                    [r["id"] for r in m],
                )
                for m in proposed
            ),
            reverse=True,
        )
        self.assertAlmostEqual(ranked[0][0], 1.8)
        self.assertIn("9", ranked[0][1])

    def test_joint_small_random_oracle_bounds_and_independent_lower_bound(self):
        rng = np.random.default_rng(20261031)
        gaps = []
        for _ in range(40):
            a = support([0, 1, 2], [*rng.random(3)], [0, 1, 2])
            b = support([0, 1, 3], [*rng.random(3)], [0, 1, 2])
            _, v = allocate([a, b], [1, 1], 1)
            _, ind = allocate([a, b], [1, 1], 1, joint=False)
            exact = oracle([a, b], [1, 1])
            gaps.append(exact - v)
            self.assertGreaterEqual(v + 1e-10, ind)
            self.assertLessEqual(v, exact + 1e-10)
        self.assertLess(
            max(gaps), 1e-10
        )  # This small single-patch-per-visit oracle is exact.

    def test_order_dependent_schedule_and_costly_pair_can_lose(self):
        from trail_scout import schedule, profiles

        p = profiles.validate()
        start = dict(latitude=38.7, longitude=-107.2)

        def leg(minutes):
            return dict(hours_low=minutes / 60, hours_high=minutes / 60)

        config = dict(am_end_offset=160, min_glassing_minutes=60)
        one = schedule.variant("2026-10-31", start, [leg(5), leg(5)], p, config, "am")
        ab = schedule.variant(
            "2026-10-31", start, [leg(5), leg(30), leg(5)], p, config, "am"
        )
        ba = schedule.variant(
            "2026-10-31", start, [leg(40), leg(30), leg(5)], p, config, "am"
        )
        self.assertTrue(one["feasible"])
        self.assertFalse(ab["feasible"])
        self.assertFalse(ba["feasible"])
        self.assertGreater(ab["observation_minutes"], ba["observation_minutes"])
        a = support([0, 1], [1, 0.8], [0, 1], costs=[300, 300])
        single = allocate([a], [one["observation_minutes"]], 1)[1]
        pair = allocate([a, a], [max(0, ab["observation_minutes"] / 2)] * 2, 1)[1]
        self.assertGreater(single, pair)


class CachePublication(unittest.TestCase):
    def test_interruption_retained_publication_atomic_and_completed_never_overwritten(
        self,
    ):
        from pathlib import Path
        import tempfile
        from practical_glassing import cache
        from trail_scout.storage import IntegrityError, atomic

        with tempfile.TemporaryDirectory(prefix="timed-publication-") as root:
            folder = Path(root) / ("a" * 64)
            cache.begin(folder)
            (folder / "support.npz").write_bytes(b"interrupted incomplete fixture")
            self.assertFalse(cache.ready(folder))
            cache.begin(folder)
            interrupted = list(Path(root).glob("*.interrupted-*"))
            self.assertEqual(len(interrupted), 1)
            self.assertEqual(
                (interrupted[0] / "support.npz").read_bytes(),
                b"interrupted incomplete fixture",
            )
            cache.publish(folder)
            self.assertTrue(cache.ready(folder))
            with self.assertRaises(IntegrityError):
                cache.begin(folder)
            atomic(folder / "ready.json", dict(version=1, key="wrong generation"))
            with self.assertRaises(IntegrityError):
                cache.ready(folder)


class WholePlanOracle(unittest.TestCase):
    def test_enumerated_feasible_plans_against_independent_patch_plan_oracle(self):
        from trail_scout import profiles, schedule
        from practical_glassing.selection import member_options

        # Engineering graph: explicit directed travel only, one unsupported edge.
        # Distances and climbing constraints remain independent of the utility.
        nodes = ["A", "B", "C"]
        rows = [dict(id=i, feasible=True) for i in nodes]
        data = {
            "A": support([0, 1], [1, 0.8], [0, 1], costs=[160, 160]),
            "B": support([0, 2], [0.9, 0.9], [0, 1], costs=[160, 160]),
            "C": support([3, 4], [0.5, 0.5], [0, 1], costs=[160, 160]),
        }
        travel = {
            (a, b): (4 + (ord(b[0]) - 65) % 3, 200, 10)
            for a in ["E"] + nodes
            for b in ["E"] + nodes
            if a != b
        }
        travel["B", "C"] = None
        travel["C", "A"] = (30, 1200, 160)
        p = profiles.validate({"max_miles": 1, "max_gain_ft": 300})
        start = dict(latitude=38.7, longitude=-107.2)
        options = []
        exact = []

        def evaluate(ids, approx):
            edges = [travel[a, b] for a, b in zip(["E"] + ids, ids + ["E"])]
            if any(e is None for e in edges):
                return None
            if (
                sum(e[1] for e in edges) > 1609.344 * 0.75
                or sum(e[2] for e in edges) > 300 * 0.3048 * 0.75
            ):
                return None
            legs = [dict(hours_low=e[0] / 60, hours_high=e[0] / 60) for e in edges]
            variant = schedule.variant(
                "2026-10-31",
                start,
                legs,
                p,
                dict(am_end_offset=125, min_glassing_minutes=15),
                "am",
            )
            if not variant["feasible"]:
                return None
            budgets = [
                e["minutes"] for e in variant["events"] if e["kind"] == "observe"
            ]
            reward = (
                allocate([data[i] for i in ids], budgets, 1)[1]
                if approx
                else oracle([data[i] for i in ids], budgets)
            )
            return reward, sum(e[0] for e in edges) / 60, sum(e[2] for e in edges)

        proposed, _ = member_options(rows, [], True)
        for members in proposed:
            ids = [r["id"] for r in members]
            result = evaluate(ids, True)
            if result:
                value, hours, gain = result
                options.append(
                    dict(
                        id="-".join(ids),
                        viewpoints=members,
                        movement=dict(hours_high=hours, ascent_m=gain, offtrail_m=0),
                        schedules={
                            m: dict(feasible=True, practical=dict(relative_m2=value))
                            for m in ("am", "pm")
                        },
                    )
                )
        # Separate enumeration and dictionary cell-union oracle, without the
        # production member generator, knapsack, max reducer or frontier.
        for count in (1, 2):
            for ids in itertools.permutations(nodes, count):
                value = evaluate(list(ids), False)
                if value:
                    exact.append(value[0])
        self.assertAlmostEqual(
            max(o["schedules"]["am"]["practical"]["relative_m2"] for o in options),
            max(exact),
        )
        _, recommended = select_options(options)
        chosen = next(o for o in options if o["id"] == recommended["am"])
        self.assertGreaterEqual(
            chosen["schedules"]["am"]["practical"]["relative_m2"], 0.9 * max(exact)
        )
        self.assertNotIn("B-C", {o["id"] for o in options})
        self.assertNotIn("C-A", {o["id"] for o in options})
