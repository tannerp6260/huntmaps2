"""Scene history, free-space preflight and interrupted writes use disposable state."""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from fastapi.testclient import TestClient
from huntmaps_gui import downloads, first_person as fp, first_person_worker as worker
from huntmaps_gui import scene_storage as scenes
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui.server import create_app
from huntmaps_gui.storage import write, read_json
import test_workflow as workflow_fixture


class SceneStorage(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="huntmaps-scene-storage-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = AppConfig(state_dir=self.root / "state", workspace=self.root)
        context = configured(self.config)
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.disk = downloads.shutil.disk_usage(self.root)
        self.plan = dict(
            id="a" * 32,
            prepared=True,
            candidates=["A"],
            sources=[],
            fidelity="terrain",
            estimated_new_bytes=0,
            review_signature="approved",
            snapshots={},
        )
        self.path = fp.HOME / "plans" / (self.plan["id"] + ".json")
        write(self.path, self.plan)

    def disk_free(self, free):
        return patch.object(
            downloads.shutil, "disk_usage", return_value=self.disk._replace(free=free)
        )

    def history(self):
        # Sparse files exceed the former logical-size quota without allocating 1 GB.
        saved = fp.HOME / "bundles/history/saved.bin"
        partial = fp.HOME / "partial/interrupted/partial.bin"
        for path, size in ((saved, 900_000_000), (partial, 34_000_000)):
            path.parent.mkdir(parents=True)
            with path.open("wb") as handle:
                handle.write(b"preserved")
                handle.truncate(size)
        return {path: path.stat() for path in (saved, partial)}

    def test_large_scene_history_is_information_not_a_quota(self):
        history = self.history()
        with self.disk_free(downloads.RESERVE + scenes.SCENE_BYTES):
            review = scenes.review(self.plan)
            self.assertFalse(review["storage"]["blocked"])
            self.assertEqual(review["storage"]["required_bytes"], scenes.SCENE_BYTES)
            self.assertEqual(
                review["storage"]["scene_assets"]["saved_bytes"], 900_000_000
            )
            self.assertEqual(
                review["storage"]["scene_assets"]["partial_bytes"], 34_000_000
            )
            scenes.check_plan(self.plan, True)
            scenes.check_plan(self.plan, False)
        for path, before in history.items():
            self.assertEqual(path.stat(), before)

    def test_batch_estimate_includes_outputs_downloads_assembly_and_spools(self):
        from huntmaps_gui.lidar_batch import MAX_SPOOL_BYTES

        plan = dict(
            self.plan,
            candidates=["A", "B", "C"],
            estimated_new_bytes=100,
            sources=[dict(bytes=100, remaining_bytes=100, cached=False)],
        )
        required = 3 * scenes.SCENE_BYTES + MAX_SPOOL_BYTES + 100 + 300
        with self.disk_free(downloads.RESERVE + required):
            self.assertEqual(scenes.review(plan)["storage"]["required_bytes"], required)
            scenes.check_plan(plan, True)
        with self.disk_free(downloads.RESERVE + required - 1):
            self.assertTrue(scenes.review(plan)["storage"]["blocked"])
            with self.assertRaisesRegex(ValueError, "preserve 20 GiB"):
                scenes.check_plan(plan, True)
            # Cached-only preparation excludes absent downloads and their spools.
            scenes.check_plan(plan, False)

    def test_inventory_tolerates_a_partial_being_published_during_review(self):
        self.history()
        partial = fp.HOME / "partial/interrupted/partial.bin"
        original = Path.stat
        calls = 0

        def moving(path, *args, **kwargs):
            nonlocal calls
            if path == partial:
                calls += 1
                if calls > 1:
                    raise FileNotFoundError("Partial was published")
            return original(path, *args, **kwargs)

        with patch.object(Path, "stat", moving):
            self.assertEqual(
                scenes.usage(), dict(saved_bytes=900_000_000, partial_bytes=0)
            )

    def test_separate_temporary_filesystem_and_worker_recheck(self):
        temp = Path(tempfile.gettempdir())

        def disk(path):
            free = (
                downloads.RESERVE + scenes.SCENE_BYTES - 1
                if Path(path) == temp
                else 100 * 1024**3
            )
            return self.disk._replace(free=free)

        with patch.object(downloads.shutil, "disk_usage", side_effect=disk):
            with self.assertRaisesRegex(ValueError, "preserve 20 GiB"):
                scenes.check_plan(self.plan, False)
        with self.disk_free(downloads.RESERVE + scenes.SCENE_BYTES - 1):
            with patch.object(worker, "acquire") as acquire:
                with self.assertRaisesRegex(ValueError, "preserve 20 GiB"):
                    worker.prepare(self.plan["id"], False)
                acquire.assert_not_called()
        self.assertNotIn("transfer_ceiling_bytes", read_json(self.path))

    def test_low_space_write_does_not_truncate_existing_assets(self):
        path = self.root / "mesh.bin"
        path.write_bytes(b"old asset")
        values = np.arange(200, dtype="<f4")
        with self.disk_free(downloads.RESERVE + values.nbytes - 1):
            with self.assertRaisesRegex(ValueError, "preserve 20 GiB"):
                scenes.write_array(values, path)
        self.assertEqual(path.read_bytes(), b"old asset")
        with self.disk_free(downloads.RESERVE + values.nbytes):
            scenes.write_array(values, path)
        np.testing.assert_array_equal(np.fromfile(path, dtype="<f4"), values)

    def test_api_review_start_and_allowance_share_the_same_storage_policy(self):
        self.history()
        app = create_app(self.config)
        client = TestClient(app)
        url = "/api/first-person/plans/" + self.plan["id"]
        headers = {"X-HuntMaps": "local"}
        with self.disk_free(downloads.RESERVE + scenes.SCENE_BYTES - 1):
            self.assertTrue(client.get(url).json()["storage"]["blocked"])
            with patch.object(app.state.jobs, "start") as start:
                response = client.post(
                    url + "/start", headers=headers, json={"download": False}
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("20 GiB", response.json()["detail"])
                start.assert_not_called()
        with self.disk_free(downloads.RESERVE + scenes.SCENE_BYTES):
            self.assertFalse(client.get(url).json()["storage"]["blocked"])
            response = client.put(
                url + "/allowance", headers=headers, json={"max_download_mb": 10}
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("scene_assets", response.json()["storage"])
            with patch.object(
                app.state.jobs, "start", return_value={"id": "job"}
            ) as start:
                response = client.post(
                    url + "/start", headers=headers, json={"download": False}
                )
                self.assertEqual(response.status_code, 200)
                start.assert_called_once()


class ScenePublishing(unittest.TestCase):
    setUpClass = classmethod(workflow_fixture.WorkflowJourney.setUpClass.__func__)
    tearDownClass = classmethod(workflow_fixture.WorkflowJourney.tearDownClass.__func__)
    setUp = workflow_fixture.WorkflowJourney.setUp

    def test_full_scene_copy_and_cluster_upgrade_allow_large_preserved_history(self):
        SceneStorage.history(self)
        history = scenes.usage()
        worker.publish(self.r, self.cid, [])
        key = read_json(fp.ready_path(self.run, self.cid))["key"]
        prior = fp.HOME / "bundles" / key
        original = {p.name: p.read_bytes() for p in prior.iterdir() if p.is_file()}
        copy_key = "b" * 32
        copy_target = fp.HOME / "bundles" / copy_key
        worker.publish_copy(
            self.r, self.cid, copy_key, prior, copy_target, time.monotonic()
        )
        self.assertTrue((copy_target / "scene.json").exists())
        cluster_key = "c" * 32
        cluster_target = fp.HOME / "bundles" / cluster_key
        with patch.object(
            worker, "crop_points", return_value=(np.empty((0, 4)), "", {})
        ):
            worker.publish_clusters(
                self.r,
                self.cid,
                cluster_key,
                prior,
                cluster_target,
                time.monotonic(),
                [],
            )
        self.assertTrue((cluster_target / "scene.json").exists())
        self.assertEqual(
            read_json(fp.ready_path(self.run, self.cid))["key"], cluster_key
        )
        self.assertEqual({p.name: p.read_bytes() for p in prior.iterdir()}, original)
        self.assertGreater(scenes.usage()["saved_bytes"], history["saved_bytes"])
        self.assertEqual(scenes.usage()["partial_bytes"], history["partial_bytes"])

    def test_disk_loss_during_preparation_retains_partial_and_prior_ready_scene(self):
        worker.publish(self.r, self.cid, [])
        pointer = fp.ready_path(self.run, self.cid)
        ready = pointer.read_bytes()
        # An upgrade loses real disk headroom after writing its first asset.
        prior = fp.HOME / "bundles" / read_json(pointer)["key"]
        target = fp.HOME / "bundles" / ("d" * 32)
        disk = downloads.shutil.disk_usage(self.state)
        exhausted = False
        write_array = worker.write_array

        def shrink(array, path):
            nonlocal exhausted
            write_array(array, path)
            exhausted = True

        def available(path):
            return disk._replace(free=downloads.RESERVE - 1) if exhausted else disk

        with patch.object(downloads.shutil, "disk_usage", side_effect=available):
            with patch.object(worker, "write_array", side_effect=shrink):
                with self.assertRaisesRegex(ValueError, "preserve 20 GiB"):
                    worker.publish_copy(
                        self.r, self.cid, target.name, prior, target, time.monotonic()
                    )
        self.assertFalse(target.exists())
        self.assertEqual(pointer.read_bytes(), ready)
        self.assertTrue(list((fp.HOME / "partial").glob("*/vegetation-colors.bin")))


if __name__ == "__main__":
    unittest.main()
