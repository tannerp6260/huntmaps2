"""Exact known answers and real saved-run API integration, in disposable state."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from fastapi.testclient import TestClient
from osgeo import gdal
from huntmaps_gui import complementary as c, workflow, scouting_filters
from huntmaps_gui.catalog import Run
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui.server import create_app
from huntmaps_gui.storage import write, read_json

ROOT = Path(__file__).resolve().parents[1]


def point(cid, x=0, eligible=True):
    return dict(
        id=cid,
        x=x,
        y=0,
        eligible=eligible,
        point=dict(id=cid, longitude=x, latitude=0, revision=cid),
    )


class CoverageKnownAnswers(unittest.TestCase):
    def run_greedy(self, cells, rows=None, kept=None, count=2, separation=0, width=24):
        masks = {}
        for cid, indices in cells.items():
            a = np.zeros((3, width), dtype=bool)
            a.ravel()[indices] = True
            masks[cid] = c.pack(a)
        rows = rows or [point(cid) for cid in cells]
        return c.greedy(
            rows,
            kept or [],
            lambda p: masks.get(p["id"]),
            (3, width),
            count,
            separation,
        )

    def test_a10_b9_c8_different_selects_a_c_18_exact_cells(self):
        result, union, delta = self.run_greedy(
            dict(A=list(range(10)), B=list(range(9)), C=list(range(10, 18)))
        )
        self.assertEqual([p["id"] for p in result["suggestions"]], ["A", "C"])
        self.assertEqual(result["combined_cells"], 18)
        self.assertEqual(int(np.unpackbits(union).sum()), 18)
        self.assertEqual(
            [p["additional_cells"] for p in result["suggestions"]], [10, 8]
        )
        self.assertEqual(result["suggestions"][1]["overlap_percent"], 0)
        self.assertEqual(int(c.POPCOUNT[delta["C"]].sum()), 8)

    def test_kept_unknown_manual_identical_and_zero_marginal(self):
        result, _, _ = self.run_greedy(
            dict(A=list(range(10)), B=list(range(9)), C=list(range(10, 18))),
            kept=[point("A"), point("manual")],
            count=3,
        )
        self.assertEqual([p["id"] for p in result["suggestions"]], ["C"])
        self.assertIsNone(result["kept"][1]["total_cells"])
        self.assertEqual(result["combined_cells"], 18)
        result, _, _ = self.run_greedy(dict(A=[0, 1], B=[0, 1], C=[]), count=5)
        self.assertEqual(len(result["suggestions"]), 1)
        result, _, _ = self.run_greedy(dict(A=[0, 1], B=[1, 2]), count=2)
        self.assertEqual(result["suggestions"][1]["additional_cells"], 1)
        self.assertEqual(result["suggestions"][1]["overlap_percent"], 50)
        result, _, _ = self.run_greedy(
            dict(A=[0], B=[1]), kept=[point("A"), point("manual")], count=1
        )
        self.assertEqual(result["suggestions"], [])
        self.assertEqual(len(result["kept"]), 2)

    def test_deterministic_rank_ties_eligibility_spacing_and_byte_edges(self):
        cells = dict(
            A=[7, 8, 15, 16, 24, 25, 48, 49],
            B=[7, 8, 15, 16, 24, 25, 48, 49],
            C=[10, 11],
        )
        rows = [point("B", 100), point("A"), point("C", 200)]
        for _ in range(3):
            result, _, _ = self.run_greedy(cells, rows=rows)
            self.assertEqual([p["id"] for p in result["suggestions"]], ["B", "C"])
        result, _, _ = self.run_greedy(
            cells,
            rows=[point("A", eligible=False), point("B", 100), point("C", 110)],
            count=3,
            separation=20,
        )
        self.assertEqual([p["id"] for p in result["suggestions"]], ["B"])
        result, _, _ = self.run_greedy(dict(A=[24, 25, 26]), width=9)
        self.assertEqual(result["combined_cells"], 3)

    def test_byte_bounded_cache(self):
        c.CACHE.clear()
        c.CACHE_BYTES = 0

        class Saved:
            def mask(self, cid):
                return np.ones((3, 25), bool), {}

        context = object.__new__(c.Context)
        context.paths = {str(i): None for i in range(50)}
        context.mask_identity = "bounded-fixture"
        context.run = Saved()
        context.filtered = type("Filtered", (), dict(matching=np.ones((3, 25), bool)))()
        with patch.object(c, "CACHE_BUDGET", 40):
            for i in range(50):
                self.assertEqual(context.coverage(dict(id=str(i))).total, 75)
                self.assertLessEqual(c.CACHE_BYTES, 40)
        c.CACHE.clear()
        c.CACHE_BYTES = 0

        class Empty:
            def mask(self, cid):
                return np.zeros((3, 25), bool), {}

        context.run = Empty()
        with patch.object(c, "CACHE_ITEMS", 3):
            for i in range(50):
                self.assertEqual(context.coverage(dict(id=str(i))).total, 0)
                self.assertLessEqual(len(c.CACHE), 3)
        c.CACHE.clear()
        c.CACHE_BYTES = 0


class CoverageAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="huntmaps-collection-tests-")
        cls.root = Path(cls.temp.name)
        for name in ("glassing", "configs"):
            shutil.copytree(
                ROOT / name,
                cls.root / name,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        env = dict(
            os.environ,
            PYTHONDONTWRITEBYTECODE="1",
            OPENBLAS_NUM_THREADS="1",
            OMP_NUM_THREADS="1",
        )
        for command in (
            [
                sys.executable,
                "-c",
                "from glassing.transfer_fixture import create; create('fixture.json','fixture')",
            ],
            [
                sys.executable,
                "-m",
                "glassing.owner",
                "run",
                "--area",
                "fixture/observer.geojson",
                "--source-config",
                "fixture.json",
                "--name",
                "coverage-fixture",
            ],
        ):
            response = subprocess.run(
                command,
                cwd=cls.root,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if response.returncode:
                raise RuntimeError(response.stdout + response.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.state = Path(tempfile.mkdtemp(dir=self.root, prefix="state-"))
        self.config = AppConfig(
            source_dir=self.root, workspace=self.root, state_dir=self.state
        )
        self.context = configured(self.config)
        self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)
        self.client = TestClient(create_app(self.config))
        self.addCleanup(self.client.app.state.jobs.shutdown)
        self.run = "coverage-fixture"
        self.r = Run(self.run)
        self.headers = {"X-HuntMaps": "local"}

    def calculate(self, count=5, profile=""):
        response = self.client.post(
            f"/api/runs/{self.run}/complementary",
            headers=self.headers,
            json=dict(count=count, profile=profile),
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def decide(self, cid, action):
        state = workflow.records(self.run)
        return workflow.decide(
            self.run,
            cid,
            dict(
                action=action,
                revision=state["revision"],
                point=workflow.point(self.run, cid),
            ),
            self.client.app.state.jobs,
        )

    def test_actual_masks_unique_contributions_and_explicit_atomic_add(self):
        before = workflow.records(self.run)
        result = self.calculate()
        self.assertEqual(before, workflow.records(self.run))
        self.assertTrue(result["suggestions"])
        union = np.zeros((self.r.dem.RasterYSize, self.r.dem.RasterXSize), bool)
        for p in result["suggestions"]:
            mask = self.r.mask(p["id"])[0]
            self.assertEqual(p["total_cells"], int(mask.sum()))
            self.assertEqual(p["additional_cells"], int((mask & ~union).sum()))
            union |= mask
        self.assertEqual(result["combined_cells"], int(union.sum()))
        counts = np.zeros(union.shape, np.uint16)
        masks = {}
        for member in [*result["kept"], *result["suggestions"]]:
            masks[member["id"]] = self.r.mask(member["id"])[0]
            counts += masks[member["id"]]
        folder = c.folder(result["id"])
        ds = gdal.Open(str(folder / "shared.tif"))
        np.testing.assert_array_equal(
            ds.GetRasterBand(4).ReadAsArray() > 0, counts >= 2
        )
        for cid, mask in masks.items():
            ds = gdal.Open(str(folder / f"unique-{cid}.tif"))
            np.testing.assert_array_equal(
                ds.GetRasterBand(4).ReadAsArray() > 0, mask & (counts == 1)
            )

        image = self.client.get(
            f"/api/runs/{self.run}/collection-tiles/{result['id']}/combined/0/0/0.png"
        )
        self.assertEqual(
            image.status_code, 200, image.text[:200] if image.status_code != 200 else ""
        )
        added = self.client.post(
            f"/api/runs/{self.run}/complementary/{result['id']}/add",
            headers=self.headers,
        )
        self.assertEqual(added.status_code, 200, added.text)
        self.assertTrue(
            all(
                added.json()["points"][p["id"]]["shortlisted"]
                for p in result["suggestions"]
            )
        )
        self.assertFalse(any(p["confirmed"] for p in added.json()["points"].values()))
        self.assertEqual(workflow.records(self.run)["revision"], before["revision"] + 1)
        stale = self.client.post(
            f"/api/runs/{self.run}/complementary/{result['id']}/add",
            headers=self.headers,
        )
        self.assertEqual(stale.status_code, 400)
        filled = self.calculate(3)
        self.assertFalse(filled["suggestions"])
        self.assertEqual(len(filled["kept"]), len(result["suggestions"]))

    def test_manual_kept_unknown_dismiss_restore_filters_and_existing_decisions(self):
        first = self.calculate()["suggestions"][0]["id"]
        self.decide(first, "shortlist")
        old = workflow.records(self.run)["points"][first]
        p = self.r.candidate(first)
        write(
            self.state / "manual-observers" / f"{self.run}.json",
            {
                "manual-fixture": dict(
                    id="manual-fixture",
                    anchor=first,
                    longitude=p["longitude"],
                    latitude=p["latitude"],
                    name="Hunter kept",
                    status="keep",
                    kind="provisional-manual-observer",
                    analysis="No calculated coverage",
                )
            },
        )
        result = self.calculate(3)
        self.assertEqual(len(result["kept"]), 2)
        self.assertEqual(result["unknown_ids"], ["manual-fixture"])
        self.assertEqual(len(result["suggestions"]), 1)
        added = self.client.post(
            f"/api/runs/{self.run}/complementary/{result['id']}/add",
            headers=self.headers,
        )
        self.assertEqual(added.status_code, 200, added.text)
        self.assertEqual(workflow.records(self.run)["points"][first], old)
        self.assertTrue(added.json()["points"]["manual-fixture"]["shortlisted"])
        cid = result["suggestions"][0]["id"]
        self.decide(cid, "dismiss")
        dismissed = self.calculate()
        self.assertNotIn(cid, [p["id"] for p in dismissed["suggestions"]])
        self.assertNotEqual(dismissed["id"], result["id"])
        self.decide(cid, "restore")
        restored = self.calculate()
        self.assertNotEqual(restored["id"], dismissed["id"])
        self.assertTrue(
            next(p for p in c.Context(self.run, "", None).rows if p["id"] == cid)[
                "eligible"
            ]
        )
        profile = scouting_filters.save(self.run, dict(elevation_m=[9000, 10000]))
        empty = self.calculate(profile=profile["id"])
        self.assertEqual(empty["combined_cells"], 0)
        self.assertFalse(empty["suggestions"])
        self.assertEqual(len(empty["kept"]), 2)

    def test_source_corruption_rejected_even_warm_cache(self):
        result = self.calculate()
        path = self.r.visibility_path(result["suggestions"][0]["id"])
        content = path.read_bytes()
        stat = path.stat()
        try:
            path.write_bytes(content[:-1] + bytes([content[-1] ^ 1]))
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            response = self.client.post(
                f"/api/runs/{self.run}/complementary",
                headers=self.headers,
                json=dict(count=5),
            )
            self.assertEqual(response.status_code, 400, response.text)
            self.assertIn("Saved source changed", response.text)
        finally:
            path.write_bytes(content)

    def test_pending_move_does_not_use_proposed_coordinates_and_changed_snapshot_rejects_add(
        self,
    ):
        result = self.calculate()
        cid = result["suggestions"][0]["id"]
        # Pending proposals have no published coordinates/mask and must not be used.
        write(
            self.state / "working-waypoints" / self.run / "state.json",
            dict(
                overrides={},
                pending={
                    cid: dict(
                        job_id="pending-job",
                        status="running",
                        revision="pending",
                        proposal=dict(longitude=0, latitude=0),
                    )
                },
            ),
        )
        pending = self.calculate()
        self.assertNotEqual(result["id"], pending["id"])
        self.assertEqual(result["suggestions"], pending["suggestions"])
        response = self.client.post(
            f"/api/runs/{self.run}/complementary/{result['id']}/add",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_published_working_mask_and_coordinates_replace_original(self):
        cid = self.calculate()["suggestions"][0]["id"]
        original = self.r.candidate(cid)
        pose = dict(
            original,
            latitude=original["latitude"] + 0.00001,
            anchor=cid,
            name="Current moved observer",
        )
        revision, spec = __import__(
            "huntmaps_gui.working_waypoints", fromlist=["signature"]
        ).signature(self.r, pose)
        home = self.state / "working-waypoints" / self.run / "cache" / revision
        home.mkdir(parents=True)
        mask = np.zeros((self.r.dem.RasterYSize, self.r.dem.RasterXSize), np.uint8)
        target = gdal.Open(str(self.r.analysis / "target.tif")).ReadAsArray() == 1
        row, col = np.argwhere(target)[0]
        mask[row, col] = 1
        from glassing.core import write_raster, digest

        write_raster(
            home / "mask.tif",
            mask,
            self.r.dem.GetGeoTransform(),
            self.r.dem.GetProjection(),
        )
        area = (
            abs(self.r.dem.GetGeoTransform()[1] * self.r.dem.GetGeoTransform()[5]) / 1e6
        )
        write(
            home / "result.json",
            dict(
                spec=spec,
                mask_sha256=digest(home / "mask.tif"),
                metrics=dict(raw_km2=area),
            ),
        )
        write(
            self.state / "working-waypoints" / self.run / "state.json",
            dict(
                overrides={
                    cid: dict(pose, revision=revision, metrics=dict(raw_km2=area))
                },
                pending={},
            ),
        )
        self.decide(cid, "shortlist")
        result = self.calculate()
        kept = next(p for p in result["kept"] if p["id"] == cid)
        self.assertEqual(kept["total_cells"], 1)
        self.assertEqual(kept["point"]["latitude"], pose["latitude"])
        self.assertEqual(kept["point"]["revision"], revision)
        # A missing published mask fails. It must never fall back to the original.
        (home / "mask.tif").unlink()
        response = self.client.post(
            f"/api/runs/{self.run}/complementary",
            headers=self.headers,
            json=dict(count=5),
        )
        self.assertEqual(response.status_code, 400)
