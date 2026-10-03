"""Persistence and maintenance safety, using only disposable state."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui import storage, maintenance
from huntmaps_gui.jobs import Jobs


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = AppConfig(state_dir=self.root)
        self.context = configured(self.config)
        self.context.__enter__()

    def tearDown(self):
        self.context.__exit__(None, None, None)
        self.temp.cleanup()

    def test_legacy_migration_preserves_exact_records_and_backup(self):
        path = self.root / "manual-observers/run.json"
        path.parent.mkdir()
        records = {
            "manual-original": {
                "id": "manual-original",
                "longitude": -107.123456789,
                "latitude": 38.9,
                "notes": "Inspect tree",
                "name": "My stance",
                "status": "keep",
            }
        }
        original = json.dumps(records).encode()
        path.write_bytes(original)
        storage.write(path, records)
        self.assertEqual(storage.read_json(path), records)
        self.assertEqual(next(path.parent.glob("*.bak")).read_bytes(), original)
        self.assertEqual(json.loads(path.read_text())["_store_version"], 1)

    def test_interrupted_replace_retains_previous_bytes_and_removes_temp(self):
        path = self.root / "annotations/run.json"
        storage.write(path, {"A": {"notes": "old"}})
        old = path.read_bytes()
        with patch("os.replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                storage.write(path, {"A": {"notes": "new"}})
        self.assertEqual(path.read_bytes(), old)
        self.assertFalse(list(path.parent.glob("*.tmp")))

    def test_concurrent_transactions_keep_all_edits(self):
        path = self.root / "annotations/run.json"

        def edit(index):
            with configured(self.config), storage.transaction(path, {}) as records:
                records[str(index)] = {"notes": str(index)}

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(edit, range(40)))
        self.assertEqual(len(storage.read_json(path)), 40)

    def test_damage_and_future_versions_never_become_empty_state(self):
        path = self.root / "annotations/run.json"
        path.parent.mkdir()
        for value in ("{broken", "[]", '{"_store_version":99,"records":{}}'):
            path.write_text(value)
            with self.assertRaises(ValueError):
                storage.read_json(path, {})
            self.assertEqual(path.read_text(), value)
        self.assertTrue(maintenance.status()["problems"])

    def test_explicit_backup_reset_restore_keeps_identity_and_revision(self):
        path = self.root / "working-waypoints/run/state.json"
        value = {
            "overrides": {
                "A": {
                    "id": "A",
                    "revision": "r",
                    "notes": "question",
                    "longitude": -107.1,
                    "latitude": 38.9,
                }
            },
            "pending": {},
        }
        storage.write(path, value)
        key = maintenance.create_backup()["backup"]
        with self.assertRaises(ValueError):
            maintenance.reset(maintenance.Reset(confirmation=""))
        maintenance.reset(maintenance.Reset(confirmation="RESET GUI RECORDS"))
        self.assertEqual(storage.read_json(path)["overrides"], {})
        maintenance.restore(maintenance.Restore(backup=key))
        self.assertEqual(storage.read_json(path), value)

    def test_cleanup_protects_recursive_scenes_masks_imports_and_active_jobs(self):
        first = "a" * 32
        second = "b" * 32
        unused = "c" * 32
        for key, meta in [
            (first, {"asset_bundles": {"mesh.bin": second}}),
            (second, {}),
            (unused, {}),
        ]:
            storage.write(self.root / "first-person/bundles" / key / "scene.json", meta)
        storage.write(self.root / "first-person/ready/A.json", {"key": first})
        storage.write(
            self.root / "working-waypoints/run/state.json",
            {
                "overrides": {
                    "A": {
                        "id": "A",
                        "revision": "current",
                        "longitude": -107.1,
                        "latitude": 38.9,
                    }
                },
                "pending": {},
            },
        )
        for key in ("current", "old"):
            path = self.root / "working-waypoints/run/cache" / key / "mask.tif"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"fixture")
        boundary = self.root / "imports/original.geojson"
        boundary.parent.mkdir()
        boundary.write_text("original")
        storage.write(self.root / "jobs/job.json", {"status": "running"})
        self.assertEqual(maintenance.inventory()["reclaimable_bytes"], 0)
        with self.assertRaises(ValueError):
            maintenance.cleanup(maintenance.Cleanup(token="any"))
        storage.write(self.root / "jobs/job.json", {"status": "failed"})
        before = maintenance.preview()
        storage.write(self.root / "first-person/ready/B.json", {"key": unused})
        with self.assertRaises(ValueError):
            maintenance.cleanup(maintenance.Cleanup(token=before["token"]))
        result = maintenance.cleanup(
            maintenance.Cleanup(token=maintenance.preview()["token"])
        )
        self.assertGreater(result["reclaimed_bytes"], 0)
        self.assertTrue(
            (self.root / "first-person/bundles" / second / "scene.json").exists()
        )
        self.assertTrue(
            (self.root / "working-waypoints/run/cache/current/mask.tif").exists()
        )
        self.assertFalse((self.root / "working-waypoints/run/cache/old").exists())
        self.assertEqual(boundary.read_text(), "original")

    def test_app_configs_do_not_share_annotations(self):
        from fastapi.testclient import TestClient
        from huntmaps_gui.server import create_app

        with TestClient(create_app(self.config)) as first, TestClient(
            create_app(AppConfig(state_dir=self.root / "other"))
        ) as second:
            url = "/api/runs/soap-creek-v1/annotations/A0075"
            self.assertEqual(
                first.put(
                    url,
                    json={"status": "keep", "notes": "isolated"},
                    headers={"X-HuntMaps": "local"},
                ).status_code,
                200,
            )
            self.assertEqual(second.get(url.rsplit("/", 1)[0]).json(), {})
            self.assertEqual(
                first.get(url.rsplit("/", 1)[0]).json()["A0075"]["notes"], "isolated"
            )

    def test_display_budget_evicts_oldest_and_keeps_authoritative_files(self):
        import os
        from huntmaps_gui.display_cache import evict, touch

        cache = self.root / "cache"
        cache.mkdir()
        old = cache / "old.png"
        new = cache / "new.png"
        old.write_bytes(b"a" * 8)
        new.write_bytes(b"b" * 8)
        os.utime(old, (1, 1))
        os.utime(new, (2, 2))
        authoritative = self.root / "import.geojson"
        authoritative.write_bytes(b"original")
        before = authoritative.stat().st_mtime_ns
        touch(authoritative)
        with configured(AppConfig(state_dir=self.root, display_budget_bytes=8)):
            self.assertEqual(evict(), 8)
        self.assertFalse(old.exists())
        self.assertTrue(new.exists())
        self.assertEqual(authoritative.stat().st_mtime_ns, before)

    def test_viewed_coverage_retained_until_dismissed_or_budget_pressure(self):
        import os
        from huntmaps_gui.display_cache import remember, evict

        cache = self.root / "cache"
        kept = cache / "kept/tile.png"
        dismissed = cache / "dismissed/tile.png"
        other = cache / "other/tile.png"
        for path in (kept, dismissed, other):
            path.parent.mkdir(parents=True)
            path.write_bytes(b"x" * 1000)
        remember(kept.parent, "fixture", "A1", True)
        remember(dismissed.parent, "fixture", "A2", True)
        os.utime(kept, (1, 1))
        storage.write(
            self.root / "workflows/fixture.json",
            {"points": {"A2": {"dismissed": True}}},
        )
        with configured(AppConfig(state_dir=self.root, display_budget_bytes=1500)):
            evict()
        self.assertTrue(
            kept.exists(), "Viewed non-dismissed coverage outranks newer generic cache"
        )
        self.assertFalse(dismissed.exists())
        self.assertFalse(other.exists())
        storage.write(
            self.root / "workflows/fixture.json",
            {"points": {"A1": {"dismissed": True}}},
        )
        other.write_bytes(b"x" * 1000)
        with configured(AppConfig(state_dir=self.root, display_budget_bytes=1500)):
            evict()
        self.assertFalse(kept.exists())
        self.assertTrue(other.exists())

    def test_job_summaries_are_paginated_and_logs_bounded(self):
        import sys, time
        from fastapi.testclient import TestClient
        from huntmaps_gui.server import create_app

        with TestClient(create_app(self.config)) as client:
            jobs = client.app.state.jobs
            job = jobs.start([sys.executable, "-c", "print('x'*70000)"], "fixture")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and jobs.list()[0]["status"] == "running":
                time.sleep(0.02)
            summaries = client.get("/api/jobs?limit=1").json()
            self.assertEqual(len(summaries), 1)
            self.assertNotIn("logs", summaries[0])
            self.assertNotIn("command", summaries[0])
            self.assertEqual(
                len(
                    client.get("/api/jobs/" + job["id"] + "/logs?limit=100").json()[
                        "logs"
                    ]
                ),
                100,
            )
            self.assertEqual(
                client.get("/api/jobs/" + job["id"] + "/logs?limit=64001").status_code,
                400,
            )
            self.assertEqual(client.get("/api/jobs?offset=1").json(), [])

    def test_waypoint_get_is_read_only_and_startup_publishes_once(self):
        from huntmaps_gui import working_waypoints as waypoints
        from huntmaps_gui.catalog import Run
        from huntmaps_gui.jobs import write

        run = "soap-creek-decision-review-v2"
        folder = self.root / "working-waypoints" / run
        folder.mkdir(parents=True)
        value = {"overrides": {}, "pending": {}}
        write(folder / "state.json", value)
        before = (folder / "state.json").read_bytes()
        jobs = Jobs()
        self.assertEqual(waypoints.snapshot(run, jobs), value)
        self.assertEqual((folder / "state.json").read_bytes(), before)
        jobs.shutdown()
