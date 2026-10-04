"""Known-answer terrain criteria and standing-point eligibility checks."""

import unittest
import numpy as np
from huntmaps_gui import target_filters
from huntmaps_gui.search import rank, spread_recommendations, nearby_cover


class TargetFilters(unittest.TestCase):
    def test_combined_ranges_unknown_cover_and_north_facing(self):
        dem = np.repeat(np.arange(5, dtype=float)[:, None] * 10 + 2000, 5, axis=1)
        tree = np.full((5, 5), 0.2)
        shrub = np.full((5, 5), 0.3)
        tree[2, 2] = np.nan
        criteria = dict(
            elevation_m=[2020, 2030],
            slope_deg=[44, 46],
            aspects=["N"],
            tree_percent=[10, 25],
            shrub_percent=[20, 40],
        )
        original = dem.copy()
        matching, unknown = target_filters.masks(
            dem, (0, 10, 0, 0, 0, -10), criteria, tree, shrub
        )
        expected = np.zeros((5, 5), bool)
        expected[2:4] = True
        expected[2, 2] = False
        np.testing.assert_array_equal(matching, expected)
        self.assertEqual(int(unknown.sum()), 1)
        np.testing.assert_array_equal(dem, original)
        criteria["aspects"] = ["S"]
        self.assertFalse(
            target_filters.masks(dem, (0, 10, 0, 0, 0, -10), criteria, tree, shrub)[
                0
            ].any()
        )

    def test_flat_direction_and_disabled_cover_unknown(self):
        dem = np.ones((5, 5)) * 2000
        tree = np.full_like(dem, np.nan)
        matching, unknown = target_filters.masks(
            dem, (0, 10, 0, 0, 0, -10), {}, tree, tree
        )
        self.assertTrue(matching.all())
        self.assertFalse(unknown.any())
        matching, unknown = target_filters.masks(
            dem, (0, 10, 0, 0, 0, -10), {"aspects": ["N"]}, tree, tree
        )
        self.assertFalse(matching.any())
        self.assertTrue(unknown.all())
        matching, unknown = target_filters.masks(
            dem, (0, 10, 0, 0, 0, -10), {"tree_percent": [0, 100]}, tree, tree
        )
        self.assertFalse(matching.any())
        self.assertTrue(unknown.all())

    def test_clearing_mask_matches_neighborhood_evidence(self):
        tree = np.zeros((25, 25))
        shrub = np.zeros_like(tree)
        tree[:, 15:] = 0.8
        tree[4:9, 4:9] = np.nan
        eligible = target_filters.standing_mask(tree, 10, 30, 10)
        for row, col in [(0, 0), (12, 12), (12, 20), (6, 6), (12, 4)]:
            evidence = nearby_cover(
                tree, shrub, (0, 10, 0, 0, 0, -10), {"row": row, "col": col}, 30, 10
            )
            self.assertEqual(
                bool(eligible[row, col]),
                evidence["foreground_category"] == "low mapped tree cover",
            )

    def test_ranking_uses_matching_area_and_keeps_nonmatches(self):
        rows = [
            dict(
                id=ident,
                matching_km2=matching,
                raw_km2=raw,
                group="automated",
                x=x,
                y=0,
                standing_eligible=eligible,
            )
            for ident, matching, raw, x, eligible in [
                ("dense", 4, 5, 0, True),
                ("open", 1, 8, 300, True),
                ("zero", 0, 9, 600, True),
                ("ineligible", 6, 6, 900, False),
                ("tie", 4, 6, 1200, True),
            ]
        ]
        self.assertEqual(
            [p["id"] for p in rank(rows)],
            ["ineligible", "tie", "dense", "open", "zero"],
        )
        self.assertEqual(
            [p["id"] for p in spread_recommendations(rows, 5, 150)],
            ["tie", "dense", "open"],
        )
        self.assertEqual(len(rows), 5)
        self.assertEqual(
            spread_recommendations([dict(p, matching_km2=0) for p in rows], 5, 0), []
        )

    def test_invalid_ranges_and_versions(self):
        for criteria in [
            {"version": 2},
            {"elevation_m": [5, 4]},
            {"slope_deg": [-1, 10]},
            {"tree_percent": [0, 101]},
            {"aspects": ["up"]},
            {"elevation_m": [float("nan"), 10]},
        ]:
            with self.assertRaises(ValueError):
                target_filters.validate(criteria)
