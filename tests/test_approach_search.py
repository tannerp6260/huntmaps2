import unittest
import numpy as np
from shapely.geometry import box, LineString, GeometryCollection
from huntmaps_gui.approach_search import (
    Grid,
    solve,
    departures,
    network_paths,
    summarize,
)

W = dict(slope=1, tree=1, shrub=1, gain=1)


def grid(dem=None, tree=None, shrub=None, barriers=None, maximum=30):
    dem = np.zeros((12, 12)) if dem is None else dem
    return Grid(
        dem,
        np.zeros_like(dem) if tree is None else tree,
        np.zeros_like(dem) if shrub is None else shrub,
        (0, 240),
        box(0, 0, 240, 240),
        barriers if barriers is not None else GeometryCollection(),
        maximum,
    )


class ApproachSearchTests(unittest.TestCase):
    def test_exact_endpoints_metrics_and_determinism(self):
        g = grid()
        line = LineString([(10, 230), (10, 10)])
        target = (207.1, 31.7)
        result = solve(g, [line], target, W)
        self.assertEqual(result, solve(g, [line], target, W))
        self.assertEqual(len(result["alternatives"]), 1)
        a = result["alternatives"][0]
        self.assertEqual(a["offtrail"][-1], target)
        independently = sum(
            np.linalg.norm(np.array(b) - a)
            for a, b in zip(a["offtrail"], a["offtrail"][1:])
        )
        self.assertAlmostEqual(independently, a["offtrail_distance_m"])
        self.assertAlmostEqual(sum(a["cost_contributions"].values()), a["cost"])
        self.assertEqual(a["ascent_m"], 0)

    def test_brush_tradeoff_and_farther_departure(self):
        trees = np.zeros((12, 12))
        trees[4:8, 1:8] = 1
        g = grid(tree=trees)
        lines = [LineString([(10, 230), (10, 10)])]
        shortest = solve(g, lines, (210, 130), dict(slope=0, tree=0, shrub=0, gain=0))[
            "alternatives"
        ][0]
        brush = solve(g, lines, (210, 130), dict(slope=0, tree=5, shrub=0, gain=0))[
            "alternatives"
        ][0]
        self.assertGreater(
            brush["offtrail_distance_m"], shortest["offtrail_distance_m"]
        )
        self.assertNotEqual(brush["departure"], shortest["departure"])
        self.assertLess(
            brush["cost_contributions"]["tree"], 5 * shortest["offtrail_distance_m"]
        )

    def test_trail_start_changes_departure(self):
        g = grid()
        lines = [LineString([(10, 230), (10, 10)])]
        target = (210, 130)
        a = solve(g, lines, target, W)["alternatives"][0]
        b = solve(g, lines, target, W, start=(10, 230))["alternatives"][0]
        self.assertNotEqual(a["departure"], b["departure"])
        self.assertEqual(b["mapped"][0], (10, 230))
        self.assertGreater(
            b["mapped_distance_m"] + b["offtrail_distance_m"], a["offtrail_distance_m"]
        )

    def test_barrier_and_no_corner_cutting(self):
        g = grid(barriers=box(115, 0, 125, 240))
        result = solve(g, [LineString([(10, 230), (10, 10)])], (210, 130), W)
        self.assertFalse(result["alternatives"])
        self.assertIn("No path found", result["message"])
        g = grid()
        g.valid[5, 6] = False
        g.valid[6, 5] = False
        self.assertNotIn((6, 6), list(g.neighbors((5, 5))))

    def test_unknown_penalty_and_missing_dem(self):
        tree = np.full((12, 12), np.nan)
        g = grid(tree=tree)
        edge = g.segment((30, 210), (50, 210), W)
        self.assertEqual(edge["contributions"][2], 20)
        self.assertTrue(edge["unknown"])
        self.assertEqual(
            summarize(g, [], [(30, 210), (50, 210)], W)["unknown_cover_fraction"], 1
        )
        g.dem[3, 3] = np.nan
        g.valid[3, 3] = False
        self.assertIsNone(g.segment((50, 170), (90, 170), W))

    def test_climbing_direction_and_hard_slope(self):
        dem = np.tile(np.arange(12) * 3, (12, 1)).astype(float)
        g = grid(dem)
        up = g.segment((30, 210), (50, 210), W)
        down = g.segment((50, 210), (30, 210), W)
        self.assertEqual(up["ascent_m"], 3)
        self.assertEqual(down["descent_m"], 3)
        self.assertEqual(up["cost"] - down["cost"], 30)
        self.assertIsNone(grid(dem, maximum=5).segment((30, 210), (50, 210), W))

    def test_disconnected_crossings_no_bridge_and_pinned(self):
        g = grid()
        lines = [LineString([(10, 230), (10, 10)]), LineString([(30, 130), (210, 130)])]
        p = (210, 130)
        self.assertNotIn(p, network_paths(g, lines, [p], (10, 230), W))
        crossing = [
            LineString([(10, 130), (230, 130)]),
            LineString([(130, 230), (130, 10)]),
        ]
        self.assertNotIn(
            (130, 10), network_paths(g, crossing, [(130, 10)], (10, 130), W)
        )
        self.assertIn((10, 131.234), departures(lines, (210, 130), (10, 131.234)))
        with self.assertRaises(ValueError):
            departures(lines, (210, 130), (17, 131))

    def test_endpoint_exclusion_and_export_segments(self):
        g = grid(barriers=box(201, 30, 215, 45))
        self.assertFalse(
            solve(g, [LineString([(10, 230), (10, 10)])], (207, 37), W)["alternatives"]
        )
        g = grid(barriers=box(90, 100, 130, 160))
        r = solve(g, [LineString([(10, 230), (10, 10)])], (207, 130), W)
        for a in r["alternatives"]:
            for u, v in zip(a["offtrail"], a["offtrail"][1:]):
                self.assertTrue(g.domain.covers(LineString([u, v])))

    def test_independent_slope_and_climbing_tradeoffs(self):
        z = np.zeros((12, 12))
        z[4:8, 4:8] = 30
        g = grid(z, maximum=60)
        lines = [LineString([(10, 130), (10, 130.1)])]
        zero = dict(slope=0, tree=0, shrub=0, gain=0)
        short = solve(g, lines, (210, 130), zero)["alternatives"][0]
        steep = solve(g, lines, (210, 130), dict(zero, slope=5))["alternatives"][0]
        climb = solve(g, lines, (210, 130), dict(zero, gain=5))["alternatives"][0]
        self.assertGreater(steep["offtrail_distance_m"], short["offtrail_distance_m"])
        self.assertLess(steep["maximum_slope_deg"], short["maximum_slope_deg"])
        self.assertGreater(climb["offtrail_distance_m"], short["offtrail_distance_m"])
        self.assertLess(climb["ascent_m"], short["ascent_m"])
        a = short
        heights = [g.dem[g.cell(p)] for p in a["offtrail"]]
        self.assertAlmostEqual(
            sum(max(0, b - a) for a, b in zip(heights, heights[1:])), a["ascent_m"]
        )
        self.assertAlmostEqual(
            sum(max(0, a - b) for a, b in zip(heights, heights[1:])), a["descent_m"]
        )
        self.assertAlmostEqual(a["cost"], a["offtrail_distance_m"])

    def test_reject_oversized_departure_inventory(self):
        lines = [LineString([(0, y * 0.1), (2000, y * 0.1)]) for y in range(200)]
        with self.assertRaisesRegex(ValueError, "narrow"):
            departures(lines, (1000, 10))

    def test_independent_distance_gain_cover_and_cost_contributions(self):
        import math

        rows, cols = np.indices((12, 12))
        dem = cols * 3 + rows * 1.5
        tree = np.full((12, 12), 0.4)
        shrub = np.full((12, 12), 0.2)
        shrub[2, 3] = np.nan
        g = grid(dem.astype(float), tree, shrub, maximum=60)
        mapped = [(10, 210), (30, 210)]
        offtrail = [(30, 210), (50, 190), (70, 190)]
        actual = summarize(g, mapped, offtrail, W)
        diagonal = 20 * math.sqrt(2)
        terrain = math.degrees(math.atan(math.hypot(3 / 20, 1.5 / 20)))
        self.assertAlmostEqual(actual["mapped_distance_m"], 20)
        self.assertAlmostEqual(actual["offtrail_distance_m"], diagonal + 20)
        self.assertAlmostEqual(actual["ascent_m"], 10.5)
        self.assertEqual(actual["descent_m"], 0)
        expected = dict(
            distance=40 + diagonal,
            slope=(40 + diagonal) * (terrain / 15) ** 2,
            tree=(20 + diagonal) * 0.4,
            shrub=diagonal * 0.2 + 20 * 0.6,
            climbing=105,
        )
        for key, value in expected.items():
            self.assertAlmostEqual(actual["cost_contributions"][key], value)
        self.assertAlmostEqual(actual["cost"], sum(expected.values()))
        self.assertAlmostEqual(actual["unknown_cover_fraction"], 20 / (40 + diagonal))
