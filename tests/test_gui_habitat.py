"""Independent numerical and isolation checks for GUI-only habitat scoring."""

import unittest
import numpy as np
from huntmaps_gui import habitat
from huntmaps_gui import complementary as comp


class HabitatNumbers(unittest.TestCase):
    def test_scalar_product_and_unknown(self):
        # Independent scalar oracle: never product of means.
        h = np.array([[1.0, 0.5, 0.8, 0.9]])
        g = np.array([[0.2, 0.8, 0.9, 0.9]])
        known = np.array([[True, True, False, True]])
        layers = dict(
            h=h,
            g=g,
            known=known,
            components=np.stack([h * 0.1, h * 0.45, h * 0.25, h * 0.2]),
        )
        visible = np.array([[True, True, True, False]])
        m = habitat.metrics(
            layers, visible, np.ones_like(visible), 100, habitat.validate()
        )
        self.assertAlmostEqual(m["effective_m2"], 100 * (1 * 0.2 + 0.5 * 0.8))
        self.assertEqual(m["matching_m2"], 300)
        self.assertEqual(m["scorable_m2"], 200)
        self.assertEqual(m["habitat_unknown_m2"], 100)
        self.assertAlmostEqual(
            sum(m["component_effective_m2"].values()), m["effective_m2"]
        )

    def test_known_zero_and_insufficient(self):
        layers = dict(
            h=np.zeros((1, 2)),
            g=np.ones((1, 2)),
            known=np.ones((1, 2), bool),
            components=np.zeros((4, 1, 2)),
        )
        m = habitat.metrics(
            layers,
            np.ones((1, 2), bool),
            np.ones((1, 2), bool),
            100,
            habitat.validate(),
        )
        self.assertEqual(m["status"], "scored")
        self.assertEqual(m["effective_m2"], 0)
        layers["known"][:] = False
        m = habitat.metrics(
            layers,
            np.ones((1, 2), bool),
            np.ones((1, 2), bool),
            100,
            habitat.validate(),
        )
        self.assertEqual(m["status"], "insufficient_data")
        self.assertIsNone(m["effective_m2"])

    def test_weighted_exact_and_tail(self):
        # A=100, B=75, C=200 in adjusted m²; two positions C,A =>300.
        masks = {
            "A": np.array([[1, 1, 1, 1, 0, 0, 0, 0, 0]], bool),
            "B": np.array([[1, 1, 1, 0, 0, 0, 0, 0, 0]], bool),
            "C": np.array([[0, 0, 0, 0, 0, 0, 0, 1, 1]], bool),
            "D": np.array([[0, 0, 0, 0, 0, 0, 0, 1, 1]], bool),
        }
        weights = np.array([[25, 25, 25, 25, 0, 0, 0, 100, 100]], float)
        priority = np.array([[1, 0, 0, 0, 0, 0, 0, 1, 1]], bool) * 100
        rows = [
            dict(id=k, x=i * 100, y=0, eligible=True, point={})
            for i, k in enumerate(masks)
        ]
        result, union, _ = comp.greedy(
            rows,
            [],
            lambda p: comp.pack(masks[p["id"]]),
            (1, 9),
            2,
            0,
            weights=weights,
            priority=priority,
        )
        self.assertEqual([p["id"] for p in result["suggestions"]], ["C", "A"])
        self.assertEqual(
            [p["additional_effective_m2"] for p in result["suggestions"]], [200, 100]
        )
        self.assertEqual(result["combined_effective_m2"], 300)
        self.assertEqual(result["combined_priority_m2"], 300)
        self.assertEqual(comp.pack(masks["D"]).weighted(union, weights), 0)

    def test_boundary_holes_and_patch_support(self):
        t = np.zeros((41, 41))
        s = np.full_like(t, 0.2)
        t[20, 20] = 0.9
        f = habitat.features(t, s, 30, habitat.validate())
        self.assertEqual(f["mixed"][20, 20], 0)
        self.assertEqual(f["cover"][20, 20], 0)
        self.assertFalse(f["known"][0, 0])
        self.assertTrue(f["known"][20, 20])
        t[20, 20] = np.nan
        self.assertFalse(
            habitat.features(t, s, 30, habitat.validate())["known"][20, 20]
        )

    def test_preset_behavior_and_threshold_independence(self):
        settings = habitat.validate()
        t = np.full((41, 41), 0.8)
        s = np.full_like(t, 0.02)
        dense = habitat.evaluate(habitat.features(t, s, 30, settings), settings)
        self.assertGreater(dense["h"][20, 20], 0.1)
        self.assertLess(dense["g"][20, 20], 0.3)
        # Independent scalar default: uniform cover saturates cover context,
        # has no opening mixture, and keeps browse separate from the G penalty.
        expected_h = 0.10 + 0.45 * (0.02 / (0.02 + 0.15)) + 0.20
        expected_g = (1 - 0.90 * 0.8) * (1 - 0.65 * 0.02)
        self.assertAlmostEqual(dense["h"][20, 20], expected_h)
        self.assertAlmostEqual(dense["g"][20, 20], expected_g)
        one = np.zeros_like(t, dtype=bool)
        one[20, 20] = True
        measured = habitat.metrics(dense, one, np.ones_like(one), 100, settings)
        self.assertAlmostEqual(measured["effective_m2"], 100 * expected_h * expected_g)
        t[:, ::4] = 0.1
        s[:, ::4] = 0.35
        mixed = habitat.evaluate(habitat.features(t, s, 30, settings), settings)
        self.assertGreater(mixed["h"][20, 20], dense["h"][20, 20])
        barren = habitat.evaluate(
            habitat.features(t * 0, s * 0, 30, settings), settings
        )
        self.assertAlmostEqual(barren["h"][20, 20], 0.1)
        shrubs = habitat.evaluate(
            habitat.features(t * 0, s * 0 + 1, 30, settings), settings
        )
        self.assertLess(shrubs["g"][20, 20], 0.4)
        v = np.ones_like(t, bool)
        a = habitat.metrics(mixed, v, v, 900, settings)
        b = habitat.metrics(
            mixed,
            v,
            v,
            900,
            dict(settings, habitat_threshold=0.9, glassability_threshold=0.9),
        )
        self.assertEqual(a["effective_m2"], b["effective_m2"])
        self.assertGreater(a["priority_m2"], b["priority_m2"])

    def test_strict_validation(self):
        for value in [
            dict(foo=1),
            dict(version=2),
            dict(weights=[0, 0, 0, 0]),
            dict(tree_penalty=float("nan")),
            dict(local_radius_m=1),
            dict(profile="species"),
        ]:
            with self.assertRaises(ValueError):
                habitat.validate(value)


if __name__ == "__main__":
    unittest.main()


class HabitatIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_gui_complementary as fixtures

        cls.fixture = fixtures.CoverageAPI
        cls.fixture.setUpClass()
        cls.root = cls.fixture.root

    @classmethod
    def tearDownClass(cls):
        cls.fixture.tearDownClass()

    def setUp(self):
        self.fixture.setUp(self)

    def test_saved_api_no_generation_current_metrics_and_priority_tiles(self):
        from huntmaps_gui import habitat_service as h
        from unittest.mock import patch

        with patch(
            "urllib.request.urlopen", side_effect=AssertionError("No download")
        ), patch(
            "glassing.core.viewshed",
            side_effect=AssertionError("No visibility generation"),
        ):
            chosen = h.choose(self.run, dict(settings={}, revision=0))
            response = self.client.get(
                f'/api/runs/{self.run}/habitat/{chosen["profile"]}'
            )
            self.assertEqual(response.status_code, 200, response.text)
            value = response.json()
            self.assertEqual(len(value["candidates"]), len(self.r.points))
            scored = [p for p in value["candidates"] if p["status"] == "scored"]
            self.assertTrue(scored)
            for p in scored:
                self.assertIn("target_filter_unknown_m2", p)
                self.assertLessEqual(
                    p["target_filter_unknown_m2"], p["current_visible_m2"]
                )
                self.assertAlmostEqual(
                    p["scorable_m2"] + p["habitat_unknown_m2"], p["matching_m2"]
                )
                self.assertAlmostEqual(
                    sum(p["component_effective_m2"].values()), p["effective_m2"]
                )
                self.assertLessEqual(p["priority_m2"], p["high_habitat_m2"])
            r = h.HabitatRun(
                __import__(
                    "huntmaps_gui.working_waypoints", fromlist=["DisplayRun"]
                ).DisplayRun(self.run, None),
                h.load(chosen["profile"], self.run),
            )
            path = h.overlay(r, scored[0]["id"])
            from osgeo import gdal

            rgba = gdal.Open(str(path)).ReadAsArray()
            visible = r.run.mask(scored[0]["id"])[0]
            self.assertFalse((rgba[3][~visible] > 0).any())
            warm = h.score(self.run, chosen["profile"])
            self.assertEqual(value, warm)
            from dataclasses import replace
            from huntmaps_gui.config import configured

            with configured(replace(self.config, display_budget_bytes=0)):
                h.score(self.run, chosen["profile"])
                self.assertFalse(list((self.state / "cache").rglob("arrays.npz")))
                self.assertTrue(
                    (
                        self.state / "habitat-profiles" / f'{chosen["profile"]}.json'
                    ).exists()
                )
            result = comp.calculate(self.run, 3, habitat_profile=chosen["profile"])
            union = np.zeros(r.layers["known"].shape, bool)
            for p in result["suggestions"]:
                m = r.run.mask(p["id"])[0] & r.filtered.matching
                expected = float(
                    np.sum(
                        (r.layers["h"] * r.layers["g"])[m & ~union & r.layers["known"]],
                        dtype=np.float64,
                    )
                    * r.area
                )
                self.assertAlmostEqual(p["additional_effective_m2"], expected, places=7)
                union |= m
            expected = float(
                np.sum(
                    (r.layers["h"] * r.layers["g"])[union & r.layers["known"]],
                    dtype=np.float64,
                )
                * r.area
            )
            self.assertAlmostEqual(result["combined_effective_m2"], expected, places=7)
            h.choose(self.run, dict(settings=None, revision=1))
            with self.assertRaisesRegex(ValueError, "changed"):
                comp.load_result(self.run, result["id"])

    def test_profile_backup_restore_and_state_isolation(self):
        from huntmaps_gui import habitat_service as h, maintenance
        from huntmaps_gui.config import configured, AppConfig
        from pathlib import Path
        import tempfile

        a = h.choose(self.run, dict(settings={}, revision=0))
        key = maintenance.backup()
        b = h.choose(
            self.run,
            dict(
                settings=dict(habitat.DEFAULTS, preset="custom", tree_penalty=0.8),
                revision=1,
            ),
        )
        self.assertNotEqual(a["profile"], b["profile"])
        restored = maintenance.restore(maintenance.Restore(backup=key))
        self.assertEqual(h.selection(self.run)["profile"], a["profile"])
        self.assertFalse(
            (self.state / "habitat-profiles" / f'{b["profile"]}.json').exists()
        )
        self.assertTrue(
            (
                self.state
                / "backups"
                / restored["backup"]
                / "habitat-profiles"
                / f'{b["profile"]}.json'
            ).exists()
        )
        with tempfile.TemporaryDirectory() as empty, configured(
            AppConfig(state_dir=Path(empty))
        ):
            self.assertEqual(h.selection(self.run)["profile"], "")

    def test_strict_preparation_and_source_corruption(self):
        from huntmaps_gui import habitat_service as h
        from huntmaps_gui.requests import Preparation
        import os

        args = dict(name="new", import_id="a" * 32, polygon="1")
        self.assertEqual(Preparation(**args, habitat={}).habitat, habitat.validate())
        with self.assertRaises(ValueError):
            Preparation(**args, habitat=dict(version=12))
        with self.assertRaises(ValueError):
            Preparation(**args, habitat_extra=True)
        with self.assertRaises(ValueError):
            h.choose(self.run, dict(settings={}, revision=True))
        with self.assertRaises(ValueError):
            h.choose(self.run, dict(settings={}, revision=0, target_profile=123))
        from huntmaps_gui.storage import write
        from unittest.mock import patch
        import json

        ident = "a" * 32
        write(
            self.state / "imports" / ident / "import.json",
            dict(
                path=str(self.root / "fixture/observer.geojson"),
                choices=[dict(number="1")],
            ),
        )
        payload = dict(
            name="habitat-preparation",
            import_id=ident,
            polygon="1",
            candidate_count=24,
            recommendation_count=5,
            habitat=dict(
                habitat.DEFAULTS, preset="custom", weights=[0.1, 0.5, 0.25, 0.2]
            ),
        )
        with patch.object(
            self.client.app.state.jobs,
            "start",
            return_value=dict(id="controlled-plan-job"),
        ) as start:
            response = self.client.post(
                "/api/plans", headers=self.headers, json=payload
            )
            self.assertEqual(response.status_code, 200, response.text)
            plan = start.call_args.args[0][-1]
            record = json.loads((self.state / "plans" / f"{plan}.json").read_text())
            prepared = json.loads(
                __import__("pathlib").Path(record["config"]).read_text()
            )
            self.assertAlmostEqual(sum(prepared["search"]["habitat"]["weights"]), 1)
            self.assertAlmostEqual(
                prepared["search"]["habitat"]["weights"][1], 0.5 / 1.05
            )
        chosen = h.choose(self.run, dict(settings={}, revision=0))
        h.score(self.run, chosen["profile"])
        path = self.r.path(self.r.config["data"]["tree"]["path"])
        original = path.read_bytes()
        st = path.stat()
        try:
            content = bytearray(original)
            content[-1] ^= 1
            path.write_bytes(content)
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
            with self.assertRaisesRegex(ValueError, "changed"):
                h.score(self.run, chosen["profile"])
        finally:
            path.write_bytes(original)
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))

    def test_retained_missing_mask_is_unknown_without_generation(self):
        from huntmaps_gui import habitat_service as h, workflow
        from unittest.mock import patch

        chosen = h.choose(self.run, dict(settings={}, revision=0))
        scored = h.score(self.run, chosen["profile"])
        cid = scored["recommendation_ids"][0]
        workflow.decide(
            self.run,
            cid,
            dict(
                action="shortlist",
                revision=workflow.records(self.run)["revision"],
                point=workflow.point(self.run, cid),
            ),
            None,
        )
        path = self.r.visibility_path(cid)
        content = path.read_bytes()
        try:
            path.unlink()
            with patch(
                "glassing.core.viewshed",
                side_effect=AssertionError("No automatic calculation"),
            ):
                result = h.score(self.run, chosen["profile"])
                missing = next(p for p in result["candidates"] if p["id"] == cid)
                self.assertEqual(missing["status"], "mask_unavailable")
                self.assertIsNone(missing["effective_m2"])
                result = comp.calculate(self.run, 3, habitat_profile=chosen["profile"])
                self.assertIn(cid, result["unknown_ids"])
                retained = next(p for p in result["kept"] if p["id"] == cid)
                self.assertIsNone(retained["total_effective_m2"])
        finally:
            path.write_bytes(content)

    def test_tile_burst_and_derived_corruption_are_not_warm_cache_bypasses(self):
        from huntmaps_gui import habitat_service as h
        from huntmaps_gui.working_waypoints import DisplayRun
        from concurrent.futures import ThreadPoolExecutor
        import os, math

        chosen = h.choose(self.run, dict(settings={}, revision=0))
        h.score(self.run, chosen["profile"])
        hr = h.HabitatRun(
            DisplayRun(self.run, None), h.load(chosen["profile"], self.run)
        )
        cid = next(iter(self.r.points))
        p = self.r.candidate(cid)
        z = 13
        x = int((p["longitude"] + 180) / 360 * 2**z)
        y = int(
            (1 - math.asinh(math.tan(math.radians(p["latitude"]))) / math.pi) / 2 * 2**z
        )
        url = f'/api/runs/{self.run}/habitat-tiles/{chosen["profile"]}/original/{cid}/{z}/{x}/{y}.png'
        with ThreadPoolExecutor(max_workers=12) as executor:
            responses = list(executor.map(lambda _: self.client.get(url), range(24)))
        self.assertTrue(
            all(r.status_code == 200 for r in responses),
            [(r.status_code, r.text[:100]) for r in responses if r.status_code != 200],
        )
        self.assertTrue(all(r.content == responses[0].content for r in responses))
        path = h.overlay(hr, cid)
        content = path.read_bytes()
        st = path.stat()
        try:
            altered = bytearray(content)
            altered[-1] ^= 1
            path.write_bytes(altered)
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
            with self.assertRaisesRegex(ValueError, "changed"):
                h.overlay(hr, cid)
        finally:
            path.write_bytes(content)

    def test_concurrent_preferences_reject_result_and_stale_add(self):
        from huntmaps_gui import habitat_service as h
        from unittest.mock import patch

        off = comp.calculate(self.run, 3)
        chosen = h.choose(self.run, dict(settings={}, revision=0))
        with self.assertRaisesRegex(ValueError, "changed"):
            comp.load_result(self.run, off["id"])
        old = h.HabitatRun.results

        def change(run):
            result = old(run)
            h.choose(self.run, dict(settings=None, revision=1))
            return result

        with patch.object(h.HabitatRun, "results", change):
            with self.assertRaisesRegex(ValueError, "changed"):
                h.score(self.run, chosen["profile"])
        with self.assertRaisesRegex(ValueError, "another window"):
            h.choose(self.run, dict(settings={}, revision=0))
        profile = h.choose(self.run, dict(settings={}, revision=2))["profile"]
        result = comp.calculate(self.run, 3, habitat_profile=profile)
        h.choose(
            self.run,
            dict(
                settings=dict(habitat.DEFAULTS, preset="custom", habitat_threshold=0.5),
                revision=3,
            ),
        )
        with self.assertRaisesRegex(ValueError, "changed"):
            comp.add(self.run, result["id"], None)


class HabitatGeometry(unittest.TestCase):
    def test_area_transfer_and_nonmetric_rotated_rejection(self):
        from osgeo import osr
        from huntmaps_gui import habitat_service as s

        sr = osr.SpatialReference()
        sr.ImportFromEPSG(32613)
        wkt = sr.ExportToWkt()
        coarse = np.array([[0.25, 1], [0.5, 0]], float)
        source_gt = (300000, 30, 0, 4280000, 0, -30)
        fine = s.array_dataset(np.zeros((6, 6)), (300000, 10, 0, 4280000, 0, -10), wkt)
        transferred = s.warp(coarse, source_gt, wkt, fine)
        self.assertAlmostEqual(
            float(coarse.sum() * 900), float(transferred.sum() * 100)
        )
        self.assertEqual(set(np.unique(transferred)), set(coarse.ravel()))
        shifted = s.array_dataset(
            np.zeros((6, 6)), (300005, 10, 0, 4279995, 0, -10), wkt
        )
        actual = s.warp(coarse, source_gt, wkt, shifted)
        # Independent cell-centre oracle for a half-fine-cell grid shift.
        import math

        reference = np.zeros((6, 6))
        for row in range(6):
            for col in range(6):
                x = 300005 + (col + 0.5) * 10
                y = 4279995 - (row + 0.5) * 10
                source_row, source_col = math.floor((4280000 - y) / 30), math.floor(
                    (x - 300000) / 30
                )
                if 0 <= source_row < 2 and 0 <= source_col < 2:
                    reference[row, col] = coarse[source_row, source_col]
        np.testing.assert_array_equal(actual, reference)
        self.assertAlmostEqual(float(actual.sum() * 100), 1000.0)
        # Exact continuous rectangle overlap is 1281.25 m² equivalents. Each
        # 30 m patch has at most 5 m width/height sample error here: weighted
        # bound (2*30*5+5²)*(.25+1+.5)=568.75, not invented fine habitat detail.
        self.assertLessEqual(abs(float(actual.sum() * 100) - 1281.25), 568.75)
        destination = s.array_dataset(
            np.zeros((1, 1)), (300000, 60, 0, 4280000, 0, -60), wkt
        )
        self.assertAlmostEqual(
            float(s.warp(coarse, source_gt, wkt, destination, "average")[0, 0] * 3600),
            float(coarse.sum() * 900),
        )
        rotated = s.array_dataset(
            np.zeros((2, 2)), (300000, 10, 1, 4280000, 0, -10), wkt
        )
        with self.assertRaisesRegex(ValueError, "metric"):
            habitat.grid(rotated)
        sr.ImportFromEPSG(4326)
        geographic = s.array_dataset(
            np.zeros((2, 2)), (-107, 0.001, 0, 38, 0, -0.001), sr.ExportToWkt()
        )
        with self.assertRaisesRegex(ValueError, "metric"):
            habitat.grid(geographic)
        # Coarsening precomputed products differs from product of means.
        hh = np.array([[1.0, 0], [1.0, 0]])
        gg = np.array([[0.0, 1], [0.0, 1]])
        self.assertEqual(
            s.warp(hh * gg, source_gt, wkt, destination, "average")[0, 0], 0
        )
        self.assertGreater(
            s.warp(hh, source_gt, wkt, destination, "average")[0, 0]
            * s.warp(gg, source_gt, wkt, destination, "average")[0, 0],
            0,
        )

    def test_nonintegral_visibility_and_current_target_domain(self):
        from osgeo import osr
        from glassing.review_maps import visible_mask
        from huntmaps_gui.habitat_service import array_dataset

        sr = osr.SpatialReference()
        sr.ImportFromEPSG(32613)
        dem = array_dataset(np.ones((5, 5)), (0, 10, 0, 50, 0, -10), sr.ExportToWkt())
        mask = array_dataset(
            np.ones((2, 2)), (0.5, 10, 0, 50, 0, -10), sr.ExportToWkt()
        )
        with self.assertRaisesRegex(ValueError, "Nonintegral"):
            visible_mask(
                mask,
                dem,
                np.ones((5, 5), bool),
                dict(id="A", x=5, y=45, raw_km2=0.0004),
                100,
            )
        mask.SetGeoTransform((0, 10, 0, 50, 0, -10))
        target = np.ones((5, 5), bool)
        target[0, 0] = False
        visible, _ = visible_mask(
            mask, dem, target, dict(id="A", x=5, y=45, raw_km2=0.0003), 100
        )
        self.assertEqual(int(visible.sum()), 3)
        self.assertFalse(visible[0, 0])

    def test_permutations_monotone_union_and_retained_unknown(self):
        import itertools

        weights = np.array([[25.0, 25.0, 100.0, 100.0, 0.0, 0.0, 0.0, 0.0, 50.0]])
        masks = {
            "A": np.array([[1, 1, 0, 0, 0, 0, 0, 0, 1]], bool),
            "B": np.array([[0, 0, 1, 1, 0, 0, 0, 0, 0]], bool),
            "C": np.array([[1, 1, 0, 0, 0, 0, 0, 0, 1]], bool),
        }
        row = lambda cid: dict(id=cid, x=ord(cid) * 100, y=0, eligible=True, point={})
        for permutation in itertools.permutations(masks):
            rows = sorted(
                [
                    dict(row(k), effective_m2=float(weights[masks[k]].sum()))
                    for k in permutation
                ],
                key=habitat.order,
            )
            result, _, _ = comp.greedy(
                rows,
                [],
                lambda p: comp.pack(masks[p["id"]]),
                (1, 9),
                5,
                0,
                weights,
                np.ones_like(weights) * 100,
            )
            self.assertEqual([p["id"] for p in result["suggestions"]], ["B", "A"])
            self.assertEqual(result["combined_effective_m2"], 300)
        retained = [dict(row("Z"), eligible=False)]
        result, _, _ = comp.greedy(
            rows,
            retained,
            lambda p: comp.pack(masks[p["id"]]) if p["id"] in masks else None,
            (1, 9),
            1,
            0,
            weights,
            np.ones_like(weights) * 100,
        )
        self.assertEqual(len(result["kept"]), 1)
        self.assertIsNone(result["kept"][0]["total_effective_m2"])
        self.assertFalse(result["suggestions"])


class HabitatRoundoff(unittest.TestCase):
    def test_explicit_nan_nodata_source_stays_unknown_and_has_canonical_identity(self):
        from huntmaps_gui import habitat_service as h
        from huntmaps_gui.config import AppConfig, configured
        from osgeo import osr, gdal
        from glassing.core import digest
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as folder, configured(
            AppConfig(state_dir=Path(folder) / "state")
        ):
            sr = osr.SpatialReference()
            sr.ImportFromEPSG(32613)
            gt = (300000, 30, 0, 4280000, 0, -30)
            data = np.full((41, 41), 20.0)
            data[20, 20] = np.nan
            config = dict(input_kind="synthetic_fixture", data={})
            for name in ("tree", "shrub"):
                path = Path(folder) / (name + ".tif")
                ds = h.array_dataset(data, gt, sr.ExportToWkt(), float("nan"))
                out = gdal.GetDriverByName("GTiff").CreateCopy(str(path), ds)
                out = None
                config["data"][name] = dict(path=str(path), sha256=digest(path))
            sources = h.source_inventory(config, Path)
            self.assertEqual(sources["tree"]["nodata"], "nan")
            prepared = h.prepare(
                sources,
                habitat.validate(),
                h.array_dataset(np.zeros_like(data), gt, sr.ExportToWkt()),
            )
            self.assertFalse(prepared["layers"]["known"][20, 20])
            self.assertTrue(prepared["layers"]["known"][20, 19])

    def test_cache_build_respects_maintenance_before_feature_lock(self):
        from huntmaps_gui import habitat_service as h, storage
        from huntmaps_gui.config import AppConfig, configured, STATE
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as folder, configured(
            AppConfig(state_dir=Path(folder))
        ):

            def build():
                self.assertIn((STATE / "maintenance").resolve(), storage._held.paths)
                return dict(value=np.ones((2, 2)))

            value = h.cached_arrays("context", "engineering-lock-fixture", build, {})
            self.assertEqual(value["value"].sum(), 4)

    def test_distant_patch_has_exact_zero_context(self):
        tree = np.zeros((101, 101))
        shrub = np.zeros_like(tree)
        tree[20:24, 20:24] = 0.9
        settings = habitat.validate(
            dict(habitat.DEFAULTS, preset="custom", weights=[0, 0, 0, 1])
        )
        layers = habitat.evaluate(habitat.features(tree, shrub, 30, settings), settings)
        self.assertTrue(layers["known"][70, 70])
        self.assertEqual(layers["h"][70, 70], 0)


class HabitatNewRun(unittest.TestCase):
    def test_real_worker_uses_objective_and_records_sidecar(self):
        import tempfile, shutil, subprocess, os, json, sys
        from pathlib import Path
        from huntmaps_gui.search import rank

        root_source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="habitat-new-run-") as folder:
            root = Path(folder)
            for name in ("glassing", "configs"):
                shutil.copytree(
                    root_source / name,
                    root / name,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )
            env = dict(
                os.environ,
                PYTHONDONTWRITEBYTECODE="1",
                PYTHONPATH=str(root_source),
                HUNTMAPS_WORKSPACE=str(root),
                HUNTMAPS_STATE_DIR=str(root / "state"),
                OPENBLAS_NUM_THREADS="1",
                OMP_NUM_THREADS="1",
            )

            def command(args):
                r = subprocess.run(
                    [sys.executable, *args],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

            command(
                [
                    "-c",
                    "from glassing.transfer_fixture import create;create('fixture.json','fixture')",
                ]
            )
            path = root / "fixture.json"
            v = json.loads(path.read_text())
            v.update(
                normal_scouting=True,
                search=dict(
                    version=1,
                    ranking_version=2,
                    recommendation_count=5,
                    recommendation_separation_m=0,
                    nearby_radius_m=30,
                    tree_threshold_percent=10,
                    habitat=habitat.validate(),
                ),
            )
            path.write_text(json.dumps(v))
            command(
                [
                    "-m",
                    "huntmaps_gui.owner_worker",
                    "run",
                    "--area",
                    "fixture/observer.geojson",
                    "--source-config",
                    "fixture.json",
                    "--name",
                    "habitat-new",
                ]
            )
            home = root / "results/habitat-new/analysis"
            scores = json.loads((home / "scores.json").read_text())
            recommendations = json.loads((home / "recommendations.json").read_text())
            eligible = [
                p
                for p in scores
                if p["group"] != "manual"
                and (p["habitat"]["effective_m2"] or 0) > 0
                and p.get("standing_eligible", True)
            ]
            self.assertEqual(
                recommendations["ids"], [p["id"] for p in rank(eligible)[:5]]
            )
            terrain_eligible = [
                p
                for p in scores
                if p["group"] != "manual"
                and p.get("standing_eligible", True)
                and p["matching_km2"] > 0
            ]
            terrain_expected = sorted(
                terrain_eligible,
                key=lambda p: (-p["matching_km2"], -p["raw_km2"], p["id"]),
            )[:5]
            self.assertEqual(
                recommendations["established_ids"],
                [p["id"] for p in terrain_expected],
            )
            self.assertTrue((home / "habitat-provenance.json").exists())
            self.assertIn(
                "habitat-provenance.json",
                json.loads((home / "products.json").read_text()),
            )
            implementation = json.loads((home / "implementation.json").read_text())
            self.assertTrue(any(p.endswith("/habitat.py") for p in implementation))
            self.assertTrue(
                any(p.endswith("/habitat_service.py") for p in implementation)
            )
            broad = [
                p
                for p in scores
                if p["group"] == "automated" and (p["habitat"]["effective_m2"] or 0) > 0
            ]
            centres = json.loads((home / "refinement.json").read_text())["centres"]
            self.assertTrue(set(centres) <= set(p["id"] for p in rank(broad)[:10]))
            # The legacy numerical score and coordinates are still separately recorded.
            self.assertTrue(
                all("raw_km2" in p and "selective_score" in p for p in scores)
            )
