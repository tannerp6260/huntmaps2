"""Concurrent tile generation coalesces duplicates and protects active source files."""

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import numpy as np
from huntmaps_gui import tiles, display_cache
from huntmaps_gui.config import AppConfig, configured


class TileConcurrency(unittest.TestCase):
    def test_background_preparation_respects_jobs_and_free_space(self):
        from types import SimpleNamespace
        from huntmaps_gui.storage import write

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with configured(AppConfig(state_dir=root)):
                with patch.object(
                    tiles.shutil,
                    "disk_usage",
                    return_value=SimpleNamespace(free=19 * 1024**3),
                ):
                    with self.assertRaisesRegex(ValueError, "20 GiB"):
                        tiles.tile(None, "visible", "A0001", 3, 1, 1, background=True)
                write(root / "jobs/job.json", dict(status="running"))
                with self.assertRaisesRegex(ValueError, "analysis is active"):
                    tiles.tile(None, "visible", "A0001", 3, 1, 1, background=True)

    def test_real_tile_return_avoids_reprojection(self):
        import math
        from huntmaps_gui.catalog import Run
        from huntmaps_gui.config import current

        base = current()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with configured(AppConfig(base.source_dir, root, base.workspace)):
                run = Run("soap-creek-decision-review-v2")
                p = run.candidate("A0075")
                z = 15
                x = int((p["longitude"] + 180) / 360 * 2**z)
                y = int(
                    (1 - math.asinh(math.tan(math.radians(p["latitude"]))) / math.pi)
                    / 2
                    * 2**z
                )
                with patch.object(tiles.gdal, "Warp", wraps=tiles.gdal.Warp) as warp:
                    started = time.perf_counter()
                    cold = tiles.tile(run, "visible", "A0075", z, x, y)
                    cold_ms = (time.perf_counter() - started) * 1000
                    started = time.perf_counter()
                    warm = tiles.tile(run, "visible", "A0075", z, x, y)
                    warm_ms = (time.perf_counter() - started) * 1000
                    self.assertEqual(cold, warm)
                    self.assertEqual(warp.call_count, 1)
                    print(
                        f"Real coverage tile: cold={cold_ms:.1f} ms warm={warm_ms:.1f} ms"
                    )

    def test_terrain_and_raster_share_maintenance_then_gdal_lock_order(self):
        from huntmaps_gui.storage import locked

        with tempfile.TemporaryDirectory(prefix="huntmaps-lock-order-") as folder:
            root = Path(folder)
            config = AppConfig(state_dir=root, workspace=root)
            source = root / "cache/source.tif"
            source.parent.mkdir()
            source.write_bytes(b"fixture")
            started = threading.Event()

            class Raster:
                def ReadAsArray(self):
                    return np.zeros((4, 256, 256), dtype="uint8")

            def request():
                started.set()
                return tiles.tile(None, "visible", "A0001", 3, 1, 1)

            with configured(config), patch.object(
                tiles, "sources", return_value=([source], "fixture")
            ), patch.object(tiles.gdal, "Warp", return_value=Raster()):
                with ThreadPoolExecutor(max_workers=1) as executor:
                    with locked(root / "maintenance"):
                        task = executor.submit(copy_context().run, request)
                        self.assertTrue(started.wait(1))
                        time.sleep(0.1)
                        acquired = tiles.LOCK.acquire(timeout=0.5)
                        if acquired:
                            tiles.LOCK.release()
                        self.assertTrue(
                            acquired,
                            "Raster must not hold GDAL lock while waiting for maintenance; terrain acquires maintenance first",
                        )
                    task.result(timeout=3)

    def test_duplicate_requests_coalesce_and_source_is_pinned(self):
        with tempfile.TemporaryDirectory(prefix="huntmaps-tiles-") as folder:
            root = Path(folder)
            config = AppConfig(
                state_dir=root, workspace=root, display_budget_bytes=1024**2
            )
            source = root / "cache/source.tif"
            source.parent.mkdir()
            source.write_bytes(b"fixture")
            counts = dict(calls=0, active=0, peak=0)
            lock = threading.Lock()

            class Raster:
                def ReadAsArray(self):
                    return np.zeros((4, 256, 256), dtype="uint8")

            def warp(*args, **kwargs):
                with lock:
                    counts["calls"] += 1
                    counts["active"] += 1
                    counts["peak"] = max(counts["peak"], counts["active"])
                self.assertIn(source, display_cache._pins)
                time.sleep(0.1)
                with lock:
                    counts["active"] -= 1
                return Raster()

            with configured(config), patch.object(
                tiles, "sources", return_value=([source], "fixture")
            ), patch.object(tiles.gdal, "Warp", side_effect=warp):
                with ThreadPoolExecutor(max_workers=4) as executor:
                    tasks = [
                        executor.submit(
                            copy_context().run,
                            tiles.tile,
                            None,
                            "visible",
                            "A0001",
                            3,
                            x,
                            1,
                        )
                        for x in [1, 1, 2, 3]
                    ]
                    results = [task.result() for task in tasks]
                self.assertEqual(results[0], results[1])
                self.assertEqual(counts["calls"], 3)
                self.assertLessEqual(counts["peak"], 2)
                self.assertFalse(display_cache._pins)
                with display_cache.pin([source]):
                    with configured(
                        AppConfig(
                            state_dir=root, workspace=root, display_budget_bytes=0
                        )
                    ):
                        display_cache.evict()
                        self.assertTrue(source.exists())
                with configured(
                    AppConfig(state_dir=root, workspace=root, display_budget_bytes=0)
                ):
                    display_cache.evict()
                    self.assertFalse(source.exists())


if __name__ == "__main__":
    unittest.main()
