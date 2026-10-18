"""Dense ground and cached recovery regressions; no owner-state writes."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from huntmaps_gui import first_person as fp, first_person_worker as worker
from huntmaps_gui import scene_storage, scene_sources
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui.storage import write


class DenseGround(unittest.TestCase):
    def test_dense_ground_above_old_cap_preserves_surface_and_seams(self):
        y, x = np.mgrid[-308:308.01:0.5, -308:308.01:0.5]
        keep = np.hypot(x, y) <= 308
        x, y = x[keep], y[keep]
        self.assertGreater(len(x), 800000)
        points = np.column_stack([x, y, 10 + x * 0.13 + y * 0.07, np.full(len(x), 2)])
        heights, support = worker.fine_grid(points)
        rows, cols = np.indices(heights.shape)
        inside = np.hypot(cols - 300, 300 - rows) <= 299
        np.testing.assert_allclose(
            heights[inside],
            (10 + (cols - 300) * 0.13 + (300 - rows) * 0.07)[inside],
            atol=1e-5,
        )
        self.assertTrue(np.all(support[inside] <= 0.36))
        self.assertTrue(np.isnan(heights[0, 0]))


class CachedRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="huntmaps-scene-recovery-")
        self.addCleanup(self.temp.cleanup)
        context = configured(AppConfig(state_dir=Path(self.temp.name)))
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def test_completed_sources_refresh_estimates_without_changing_approval(self):
        lidar = dict(
            key="lidar.laz",
            url="https://example.invalid/lidar",
            cached=False,
            bytes=8,
            remaining_bytes=8,
        )
        image = dict(
            key="image",
            url="https://example.invalid/image",
            cached=False,
            bytes=20,
            remaining_bytes=20,
            epsg=32613,
            bounds=[0, 0, 1, 1],
            pixels=1,
        )
        for source, folder, name in [
            (lidar, "sources", "lidar.laz"),
            (image, "imagery", "image.tif"),
        ]:
            path = fp.HOME / folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"verified")
            record = dict(
                source, path=str(path), sha256=hashlib.sha256(b"verified").hexdigest()
            )
            if folder == "sources":
                write(path.parent / "manifest.json", {source["key"]: record})
            else:
                write(path.with_suffix(".json"), record)
        plan = dict(
            sources=[lidar],
            imagery_sources=[image],
            candidates=["A"],
            estimated_new_bytes=28,
            review_signature="unchanged",
            transfer_ceiling_bytes=100,
        )
        original = __import__("copy").deepcopy(plan)
        with patch(
            "urllib.request.urlopen", side_effect=AssertionError("Unexpected download")
        ):
            self.assertIsNotNone(scene_sources.acquire_imagery(image, False))
        effective = scene_storage.effective_plan(plan)
        self.assertEqual(effective["estimated_new_bytes"], 0)
        self.assertTrue(
            all(
                s["cached"] for s in effective["sources"] + effective["imagery_sources"]
            )
        )
        self.assertEqual(plan, original)
        with patch(
            "urllib.request.urlopen", side_effect=AssertionError("Unexpected download")
        ):
            self.assertIsNotNone(scene_sources.acquire_imagery(image, False))
            self.assertEqual(worker.acquire(lidar, False)[0].read_bytes(), b"verified")
        (fp.HOME / "imagery/image.tif").write_bytes(b"corrupt!")
        with self.assertRaises(ValueError):
            scene_storage.effective_plan(plan)

    def test_api_cache_view_preserves_approval_and_cumulative_ledger(self):
        from fastapi.testclient import TestClient
        from huntmaps_gui.config import current
        from huntmaps_gui.server import create_app

        path = fp.HOME / "sources/source.laz"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"verified")
        source = dict(
            key=path.name,
            url="https://example.invalid/source",
            bytes=8,
            remaining_bytes=8,
            cached=False,
        )
        write(
            path.parent / "manifest.json",
            {path.name: dict(source, sha256=hashlib.sha256(b"verified").hexdigest())},
        )
        ledger = path.parent / "ledger.json"
        write(ledger, dict(received_bytes=123456))
        plan = dict(
            id="a" * 32,
            prepared=True,
            sources=[source],
            candidates=["A"],
            estimated_new_bytes=8,
            review_signature="approved",
            download_cap_bytes=10000000,
        )
        target = fp.HOME / "plans" / (plan["id"] + ".json")
        write(target, plan)
        before = target.read_bytes(), ledger.read_bytes()
        with TestClient(create_app(current())) as client:
            response = client.get("/api/first-person/plans/" + plan["id"])
            self.assertEqual(response.status_code, 200, response.text)
            value = response.json()
            self.assertEqual(value["estimated_new_bytes"], 8)
            self.assertEqual(value["remaining_new_bytes"], 0)
            self.assertEqual(value["cached_source_keys"], ["source.laz"])
            self.assertEqual(value["review_signature"], "approved")
            self.assertEqual(value["download_time"]["maximum_s"], 0)
        self.assertEqual((target.read_bytes(), ledger.read_bytes()), before)
        with self.assertRaisesRegex(ValueError, "identity differs"):
            scene_sources.cached_source(
                dict(source, url="https://example.invalid/changed"), "sources"
            )


if __name__ == "__main__":
    unittest.main()
