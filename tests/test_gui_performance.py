"""Exact oracles and integrity/recovery guards for normal-workflow optimizations."""

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from osgeo import gdal
from glassing import core, transfer
from glassing.acquire import srs, dump, digest
from huntmaps_gui.config import AppConfig, configured, current
from huntmaps_gui.sampling import TerrainSampler
from huntmaps_gui.evaluation import Evaluation


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="huntmaps-opt-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.context = configured(
            AppConfig(current().source_dir, self.root / "state", self.root)
        )
        self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)

    def test_manifest_cache_exact_independent_and_rejects_changed_paths(self):
        from huntmaps_gui import catalog

        folder = self.root / "sources"
        folder.mkdir()
        source = folder / "input.bin"
        source.write_bytes(b"original source")
        manifest = self.root / "manifest.json"
        values = {str(source): "0" * 64}
        manifest.write_text(json.dumps(values))
        expected = {
            str(catalog.safe_path(k, current().source_dir)): v
            for k, v in values.items()
        }
        first = catalog.manifest_hashes(manifest, current().source_dir)
        self.assertEqual(first, expected)
        first.clear()
        self.assertEqual(
            catalog.manifest_hashes(manifest, current().source_dir), expected
        )
        old = manifest.stat()
        values[str(source)] = "1" * 64
        manifest.write_text(json.dumps(values))
        os.utime(manifest, ns=(old.st_atime_ns, old.st_mtime_ns))
        self.assertEqual(
            catalog.manifest_hashes(manifest, current().source_dir), values
        )
        source.unlink()
        source.symlink_to("/etc/hostname")
        with self.assertRaisesRegex(ValueError, "Source must be inside this project"):
            catalog.manifest_hashes(manifest, current().source_dir)

    def test_verified_file_cache_rejects_restored_mtime_and_atomic_replacement(self):
        from huntmaps_gui.first_person import verify_file

        path = self.root / "asset.bin"
        path.write_bytes(b"immutable")
        expected, old = digest(path), path.stat()
        verify_file(path, expected)
        # ext4 can give two writes within one clock tick the same ctime. This
        # regression isolates the new ctime key, independently of that granularity.
        time.sleep(0.01)
        path.write_bytes(b"corrupted")
        os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, "Saved source changed"):
            verify_file(path, expected)
        path.write_bytes(b"immutable")
        verify_file(path, expected)
        replacement = self.root / "replacement.bin"
        replacement.write_bytes(b"corrupted")
        os.utime(replacement, ns=(old.st_atime_ns, old.st_mtime_ns))
        replacement.replace(path)
        with self.assertRaisesRegex(ValueError, "Saved source changed"):
            verify_file(path, expected)

    def grid_config(self, count=48, spacing=30):
        root = self.root / "sampling"
        root.mkdir(exist_ok=True)
        n = 72
        yy, xx = np.mgrid[:n, :n]
        dem = (2100 + 30 * np.sin(xx / 10) + 15 * np.cos(yy / 8)).astype("float32")
        allowed = (xx > 5) & (xx < 65) & (yy > 5) & (yy < 65)
        allowed[25:45, 25:45] = False
        gt = (-360, 10, 0, 360, 0, -10)
        for name, a in [
            ("dem", dem),
            ("observer", allowed.astype("uint8")),
            ("target", allowed.astype("uint8")),
        ]:
            core.write_raster(root / (name + ".tif"), a, gt, srs(32613).ExportToWkt())
        c = dict(
            work=str(root),
            vertical_units="m",
            max_cells=3000000,
            seed=5403,
            candidate_count=count,
            spacing_m=spacing,
            manual_points=[],
        )
        self.seal(c)
        return c

    def seal(self, c):
        root = Path(c["work"])
        dump(
            root / "prepared.json",
            dict(
                config=c,
                implementation_sha256=digest(core.__file__),
                **{
                    k + "_sha256": digest(root / (k + ".tif"))
                    for k in ["dem", "target", "observer"]
                },
            ),
        )

    def test_sampling_exact_order_provenance_strict_spacing_and_exhaustion(self):
        c = self.grid_config()
        # Both accepted manual neighbors match the third cell. Earliest accepted
        # wins even across hash buckets; do not merge into the closest/newest.
        gt = (-360, 10, 0, 360, 0, -10)
        c["manual_points"] = [
            dict(zip(("x", "y"), core.xy(gt, 10, col)), name=name)
            for col, name in [(10, "first"), (14, "second"), (12, "bridge")]
        ]
        for seed in [0, 17, 5403]:
            c["seed"] = seed
            for spacing in [10 * (1 - 1e-9), 20, 30, 70, 300]:
                with self.subTest(seed=seed, spacing=spacing):
                    c["spacing_m"] = spacing
                    self.seal(c)
                    try:
                        core.generate(c)
                    except ValueError as error:
                        with self.assertRaisesRegex(ValueError, "Only ") as actual:
                            TerrainSampler(c).generate(c)
                        self.assertEqual(str(actual.exception), str(error))
                    else:
                        expected = (Path(c["work"]) / "candidates.json").read_bytes()
                        sampler = TerrainSampler(c)
                        sampler.generate(c)
                        self.assertEqual(
                            (Path(c["work"]) / "candidates.json").read_bytes(), expected
                        )
                        if spacing == 30:
                            points = json.loads(expected)
                            self.assertIn("manual:bridge", points[0]["provenance"])
                            self.assertNotIn("manual:bridge", points[1]["provenance"])
        # A spacing retry reuses the same derived arrays and still matches the oracle.
        c["spacing_m"] = 30
        self.seal(c)
        sampler = TerrainSampler(c)
        c["spacing_m"] = 20
        self.seal(c)
        core.generate(c)
        expected = transfer.read(Path(c["work"]) / "candidates.json")
        with patch(
            "huntmaps_gui.sampling.gaussian_filter",
            side_effect=AssertionError("Repeated smoothing"),
        ):
            sampler.generate(c)
        self.assertEqual(transfer.read(Path(c["work"]) / "candidates.json"), expected)

    def test_sampling_rejects_same_size_same_mtime_changes(self):
        c = self.grid_config()
        sampler = TerrainSampler(c)
        path = Path(c["work"]) / "dem.tif"
        old = path.stat()
        content = bytearray(path.read_bytes())
        content[-1] ^= 1
        path.write_bytes(content)
        os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, "Sampling terrain changed"):
            sampler.generate(c)

    def test_evaluation_exact_scores_patches_masks_and_input_change_rejection(self):
        from glassing.transfer_fixture import create

        create(str(self.root / "fixture.json"), str(self.root / "fixture"))
        c = transfer.read(self.root / "fixture.json")
        c.update(normal_scouting=True, work=str(self.root / "analysis"))
        transfer.prepare(c)
        transfer.candidates(c)
        pool = transfer.read(Path(c["work"]) / "pool.json")
        expected_rows, expected_patches = transfer.evaluate(c, pool)
        folder = Path(c["work"]) / "additional_visibility"
        masks = {p.name: p.read_bytes() for p in folder.glob("*.tif")}
        evaluator = Evaluation(c)
        rows, patches = [], {}
        with patch.object(
            core, "validate", side_effect=AssertionError("Per-observer full DEM read")
        ):
            for offset in range(0, len(pool), 7):
                rs, ps = evaluator.evaluate(pool[offset : offset + 7])
                rows.extend(rs)
                patches.update(ps)
        self.assertEqual(rows, expected_rows)
        self.assertEqual(patches, expected_patches)
        self.assertEqual({p.name: p.read_bytes() for p in folder.glob("*.tif")}, masks)
        self.assertEqual(
            [(p["x"], p["y"]) for p in rows if p["group"] == "manual"],
            [(p["x"], p["y"]) for p in pool if p["group"] == "manual"],
        )
        evaluator.verify(full=True)
        path = Path(c["work"]) / "tree.tif"
        old = path.stat()
        path.write_bytes(path.read_bytes()[:-1] + b"x")
        os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, "Evaluation input changed"):
            evaluator.evaluate(pool[:1])

    def test_cached_requests_skip_inventory_and_growth_budget_still_applies(self):
        from huntmaps_gui import display_cache as cache, tiles
        from huntmaps_gui.catalog import Run

        run = Run("soap-creek-decision-review-v2")
        p = run.candidate("A0075")
        z = 15
        x = int((p["longitude"] + 180) / 360 * 2**z)
        y = int(
            (1 - math.asinh(math.tan(math.radians(p["latitude"]))) / math.pi) / 2 * 2**z
        )
        first = tiles.tile(run, "visible", "A0075", z, x, y)
        with patch.object(
            cache, "evict", side_effect=AssertionError("Warm cache scan")
        ):
            for _ in range(5):
                self.assertEqual(first, tiles.tile(run, "visible", "A0075", z, x, y))
        # A different process has no access to this process's dirty set. Its
        # write marker still requires exactly one inventory on the next hit.
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from huntmaps_gui.display_cache import changed; changed()",
            ],
            env=dict(
                os.environ,
                HUNTMAPS_SOURCE_DIR=str(current().source_dir),
                HUNTMAPS_WORKSPACE=str(self.root),
                HUNTMAPS_STATE_DIR=str(self.root / "state"),
            ),
            check=True,
            timeout=10,
        )
        with patch.object(cache, "evict", wraps=cache.evict) as scanned:
            tiles.tile(run, "visible", "A0075", z, x, y)
            tiles.tile(run, "visible", "A0075", z, x, y)
        self.assertEqual(scanned.call_count, 1)
        # A writer that exits after leaving a partial must still notify other
        # processes. Sparse bytes exercise the actual budget without a bulk write.
        partial = self.root / "state/cache/failed-write.bin"
        failed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; from pathlib import Path; "
                "from huntmaps_gui.display_cache import changed; changed(); "
                "f=Path(sys.argv[1]).open('wb'); f.truncate(int(sys.argv[2])); "
                "f.close(); sys.exit(7)",
                str(partial),
                str(current().display_budget_bytes + 1024**2),
            ],
            env=dict(
                os.environ,
                HUNTMAPS_SOURCE_DIR=str(current().source_dir),
                HUNTMAPS_WORKSPACE=str(self.root),
                HUNTMAPS_STATE_DIR=str(self.root / "state"),
            ),
            timeout=10,
        )
        self.assertEqual(failed.returncode, 7)
        self.assertTrue(partial.exists())
        self.assertEqual(first, tiles.tile(run, "visible", "A0075", z, x, y))
        self.assertFalse(partial.exists())
        source = self.root / "state/cache/growth.png"
        source.write_bytes(b"x" * 500)
        with configured(
            AppConfig(current().source_dir, self.root / "state", self.root, 0)
        ):
            with cache.pin([source]):
                cache.changed()
                cache.maybe_evict()
                self.assertTrue(source.exists())
            cache.maybe_evict()
            self.assertFalse(source.exists())

    def test_native_distances_successors_and_complete_paths_are_exact(self):
        from huntmaps_gui.approach_search import Grid, solve
        from huntmaps_gui.approach_native import library
        from shapely.geometry import box, GeometryCollection, LineString

        self.assertIsNotNone(
            library(), "Current Ubuntu compiler must exercise the native path"
        )
        for seed in range(8):
            rng = np.random.default_rng(seed)
            dem = rng.normal(size=(22, 25)).cumsum(axis=0) * 0.8
            tree, shrub = rng.random(dem.shape), rng.random(dem.shape)
            tree[5:8, 12:15] = np.nan
            shrub[8, 8] = np.nan
            exclusions = box(180, 0, 205, 290) if seed % 2 else GeometryCollection()
            grid = Grid(dem, tree, shrub, (0, 440), box(0, 0, 500, 440), exclusions, 60)
            for weights in [
                dict(slope=0, tree=0, shrub=0, gain=0),
                dict(slope=1, tree=2.1, shrub=0.7, gain=4.3),
            ]:
                target = (421.7, 381.2)
                expected = grid.search_reference(target, weights)
                actual = grid.search(target, weights)
                self.assertEqual(dict(actual[0]), expected[0])
                self.assertEqual(dict(actual[1]), expected[1])
                lines = [LineString([(10, 10), (10, 430)])]
                result = solve(grid, lines, target, weights, pinned=(10, 230))
                with patch.object(grid, "search", side_effect=grid.search_reference):
                    self.assertEqual(
                        result, solve(grid, lines, target, weights, pinned=(10, 230))
                    )
        # Equal-cost ties on flat ground are checked independently of rough terrain.
        grid = Grid(
            np.zeros((25, 25)),
            np.zeros((25, 25)),
            np.zeros((25, 25)),
            (0, 500),
            box(0, 0, 500, 500),
            GeometryCollection(),
        )
        expected = grid.search_reference(
            (391.25, 392.75), dict(slope=0, tree=0, shrub=0, gain=0)
        )
        actual = grid.search((391.25, 392.75), dict(slope=0, tree=0, shrub=0, gain=0))
        self.assertEqual(dict(actual[0]), expected[0])
        self.assertEqual(dict(actual[1]), expected[1])
        with patch("huntmaps_gui.approach_native.shutil.which", return_value=None):
            fallback = grid.search(
                (391.25, 392.75), dict(slope=0, tree=0, shrub=0, gain=0)
            )
        self.assertEqual(fallback, expected)

    def test_native_alarm_fallback_concurrent_build_and_corruption(self):
        from huntmaps_gui import approach_native as native
        from huntmaps_gui.approach_search import Grid
        from shapely.geometry import box, GeometryCollection

        with ThreadPoolExecutor(max_workers=3) as executor:
            libraries = [
                task.result()
                for task in [
                    executor.submit(copy_context().run, native.library)
                    for _ in range(3)
                ]
            ]
        self.assertTrue(all(v is not None for v in libraries))
        a = np.zeros((400, 400))
        grid = Grid(a, a, a, (0, 8000), box(0, 0, 8000, 8000), GeometryCollection())
        weights = dict(slope=1, tree=1, shrub=1, gain=1)
        old = signal.getsignal(signal.SIGALRM)
        signal.signal(
            signal.SIGALRM,
            lambda *_: (_ for _ in ()).throw(ValueError("interrupted native search")),
        )
        try:
            signal.setitimer(signal.ITIMER_REAL, 0.02)
            with self.assertRaisesRegex(ValueError, "interrupted native search"):
                grid.search((4000, 4000), weights)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
        # Native failure cannot poison another independent evaluation.
        result = grid.search((4000, 4000), weights)
        self.assertEqual(len(result[0]), a.size)
        small = np.zeros((5, 5), dtype="float32")
        grid = Grid(
            small, small, small, (0, 100), box(0, 0, 100, 100), GeometryCollection()
        )
        with patch.object(
            native,
            "library",
            side_effect=AssertionError("Float32 must keep its original rounding"),
        ):
            self.assertEqual(
                grid.search((50, 50), weights), grid.search_reference((50, 50), weights)
            )
        binary = next((self.root / "state/native").glob("*/dijkstra.so"))
        with binary.open("ab") as handle:
            handle.write(b"corrupt")
        with self.assertRaisesRegex(ValueError, "Native approach cache changed"):
            native.library()

    def test_lidar_batch_exact_order_units_histograms_radius_and_capacity(self):
        import laspy
        from pyproj import CRS
        from huntmaps_gui import first_person_worker as worker, lidar_batch

        ids = ["one", "two", "three"]
        run = SimpleNamespace(
            config=dict(epsg=32613),
            points={
                cid: dict(x=300000 + i * 40, y=4300000) for i, cid in enumerate(ids)
            },
        )
        sources = []
        for index, count in enumerate([110005, 50]):
            header = laspy.LasHeader(point_format=6, version="1.4")
            header.add_crs(CRS.from_user_input("EPSG:32613+5703"))
            header.offsets = np.array([300000, 4300000, 2500])
            header.scales = np.array([0.001, 0.001, 0.001])
            las = laspy.LasData(header)
            rng = np.random.default_rng(index)
            las.x = 300000 + rng.uniform(-320, 320, count)
            las.y = 4300000 + rng.uniform(-320, 320, count)
            las.z = 2500 + rng.random(count) * 20
            las.classification = rng.choice([1, 2, 5, 7, 18], count).astype(np.uint8)
            las.withheld = np.arange(count) % 41 == 0
            path = self.root / f"points-{index}.las"
            las.write(path)
            sources.append(
                (dict(candidates=ids if index == 0 else ids[:2]), path, digest(path))
            )
        expected = {
            (cid, radius): worker.crop_points(run, cid, sources, radius)
            for cid in ids
            for radius in [122, 308]
        }
        original = laspy.open
        with patch.object(laspy, "open", wraps=original) as opened:
            with lidar_batch.crop_batch(run, ids, sources) as crops:
                self.assertIsNotNone(crops)
                for cid in ids:
                    for radius in [122, 308]:
                        points, vref, hist = crops.get(cid, radius)
                        epoints, evref, ehist = expected[cid, radius]
                        np.testing.assert_array_equal(points, epoints)
                        self.assertEqual((vref, hist), (evref, ehist))
            self.assertEqual(
                opened.call_count, 2, "One decode per source for all observers"
            )
        with patch.object(lidar_batch, "MAX_SPOOL_BYTES", 1):
            with lidar_batch.crop_batch(run, ids, sources) as crops:
                self.assertIsNone(crops)
        # Cancellation during decoding must close every anonymous spool; it
        # must propagate, rather than start the sequential fallback afterward.
        spools = []
        temporary_file = tempfile.TemporaryFile

        def tracked_spool():
            spool = temporary_file()
            spools.append(spool)
            return spool

        with patch.object(lidar_batch.tempfile, "TemporaryFile", tracked_spool):
            with patch.object(laspy, "open", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    with lidar_batch.crop_batch(run, ids, sources):
                        self.fail("Cancellation should leave the context")
        self.assertEqual(len(spools), len(ids))
        self.assertTrue(all(spool.closed for spool in spools))
        with self.assertRaisesRegex(ValueError, "Lidar source changed"):
            with lidar_batch.crop_batch(run, ids, sources) as crops:
                sources[0][1].write_bytes(sources[0][1].read_bytes() + b"corrupt")
                with self.assertRaisesRegex(ValueError, "Lidar source changed"):
                    crops.get("one")

    def test_existing_scene_reused_with_original_identity_without_decoding(self):
        from huntmaps_gui import first_person_worker as worker, first_person as fp
        from huntmaps_gui.catalog import Run
        from huntmaps_gui.storage import write

        run = Run("soap-creek-decision-review-v2")
        signature, key = worker.scene_signature(run, "A0075", [], False)
        folder = fp.HOME / "bundles" / key
        folder.mkdir(parents=True)
        asset = folder / "mesh.bin"
        asset.write_bytes(b"immutable engineering fixture")
        meta = dict(
            version=fp.VERSION,
            scene_signature=signature,
            hashes={"mesh.bin": digest(asset)},
        )
        write(folder / "scene.json", meta)
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        with patch.object(
            worker, "crop_points", side_effect=AssertionError("Cached scene decode")
        ):
            worker.publish(run, "A0075", [], optimized=True)
        self.assertEqual(transfer.read(fp.ready_path(run.id, "A0075"))["key"], key)
        self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)
        asset.write_bytes(b"corrupt fixture")
        with self.assertRaisesRegex(ValueError, "Saved source changed"):
            worker.publish(run, "A0075", [], optimized=True)


if __name__ == "__main__":
    unittest.main()
