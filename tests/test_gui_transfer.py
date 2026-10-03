"""Storage boundaries and job-scoped progress without real downloads."""

import concurrent.futures
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from huntmaps_gui import downloads, progress
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui.jobs import Jobs
from huntmaps_gui.storage import write, read_json


class TransferSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="huntmaps-transfer-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = AppConfig(state_dir=self.root / "state", workspace=self.root)
        self.context = configured(self.config)
        self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)
        self.path = self.root / "state/jobs/transfer.progress"
        self.env = patch.dict(os.environ, HUNTMAPS_PROGRESS_FILE=str(self.path))
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_reserve_boundary_and_larger_than_former_caps(self):
        usage = __import__("shutil").disk_usage(self.root)
        with patch.object(
            downloads.shutil,
            "disk_usage",
            return_value=usage._replace(free=downloads.RESERVE + 1024),
        ):
            self.assertEqual(
                downloads.check_space(self.root, 1024), downloads.RESERVE + 1024
            )
            with self.assertRaisesRegex(ValueError, "20 GiB"):
                downloads.check_space(self.root, 1025)
            review = downloads.review_info([self.root], 3_000_000_000)
            self.assertTrue(review["storage"]["blocked"])
        with patch.object(
            downloads.shutil,
            "disk_usage",
            return_value=usage._replace(free=100 * 1024**3),
        ):
            self.assertFalse(
                downloads.review_info([self.root], 3_000_000_000)["storage"]["blocked"]
            )
        self.assertEqual(downloads.suggested_mb(3_000_000_000), 3600)

    def test_parallel_progress_job_scope_unknown_totals_and_durable_reload(self):
        progress.start_download(3200)

        def receive(_):
            for i in range(20):
                progress.received(10, "https://example.test/a")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(receive, range(8)))
        progress.flush_download()
        self.assertEqual(read_json(self.path)["completed"], 1600)
        progress.emit("processing", "Scenes", 1, 2, force=True)
        self.assertNotIn("remaining_s", read_json(self.path))
        ident = "a" * 32
        write(
            self.root / "state/jobs" / (ident + ".json"),
            dict(
                id=ident,
                status="complete",
                kind="first-person-prepare",
                started=0,
                finished=1,
            ),
        )
        target = self.path.with_name(ident + ".progress")
        target.write_bytes(self.path.read_bytes())
        jobs = Jobs()
        self.addCleanup(jobs.shutdown)
        self.assertEqual(jobs.list(False)[0]["progress"]["completed"], 1)
        self.assertEqual(len(jobs.list(False)), 1)
        target.write_text("damaged optional progress")
        self.assertNotIn("progress", jobs.list(False)[0])
        progress.start_download(None)
        progress.received(50, "https://example.test/a")
        progress.flush_download()
        self.assertEqual(read_json(self.path)["completed"], 50)
        self.assertIsNone(read_json(self.path)["total"])
        progress.start_download(10)
        progress.received(20, "https://example.test/a")
        progress.flush_download()
        self.assertIsNone(read_json(self.path)["total"])

    def test_eta_measured_rate_and_cache_does_not_trigger_probe(self):
        with patch(
            "urllib.request.urlopen", side_effect=AssertionError("No speed test")
        ):
            self.assertEqual(downloads.time_estimate(0)["basis"], "cached")
            assumed = downloads.time_estimate(100_000_000)
            self.assertEqual((assumed["minimum_s"], assumed["maximum_s"]), (10, 100))
            self.assertEqual(downloads.time_estimate(None)["basis"], "unknown")
            (self.config.state_dir / "transfer-rates.json").parent.mkdir(exist_ok=True)
            (self.config.state_dir / "transfer-rates.json").write_text(
                "damaged optional speeds"
            )
            self.assertEqual(
                downloads.time_estimate(1000, ["example.test"])["basis"], "illustrative"
            )
            write(
                self.config.state_dir / "transfer-rates.json",
                {
                    "example.test": dict(
                        updated=progress.time.time(), bytes_per_s=2_000_000
                    )
                },
            )
            self.assertEqual(
                downloads.time_estimate(100_000_000, ["example.test"])["basis"],
                "measured",
            )
            with patch.object(
                progress.time, "time", return_value=progress.time.time() + 8 * 86400
            ):
                self.assertIsNone(progress.recent_rate("example.test"))

    def test_live_speed_eta_and_throttled_updates(self):
        with patch.object(progress.time, "time", return_value=100):
            progress.start_download(100_000)
            progress.received(1000, "https://example.test/a")
        stamp = self.path.stat().st_mtime_ns
        with patch.object(progress.time, "time", return_value=100.5):
            progress.received(1000, "https://example.test/a")
        self.assertEqual(stamp, self.path.stat().st_mtime_ns)
        with patch.object(progress.time, "time", return_value=105):
            progress.received(8000, "https://example.test/a")
        result = read_json(self.path)
        self.assertEqual(result["completed"], 10_000)
        self.assertAlmostEqual(result["bytes_per_s"], 2000)
        self.assertAlmostEqual(result["remaining_s"], 45)
        with patch.object(progress.time, "time", return_value=105):
            self.assertEqual(progress.recent_rate("example.test"), 2000)

    def test_processing_monitor_stops_only_its_job_group(self):
        from huntmaps_gui import guarded_job

        fake = __import__("unittest.mock", fromlist=["Mock"]).Mock()
        fake.poll.return_value = None
        with patch.object(guarded_job.os, "getpid", return_value=123), patch.object(
            guarded_job.os, "getpgrp", return_value=123
        ), patch.object(
            guarded_job.subprocess, "Popen", return_value=fake
        ), patch.object(
            guarded_job,
            "check_space",
            side_effect=[100, 100, 100, ValueError("reserve threatened")],
        ), patch.object(
            guarded_job.os, "killpg"
        ) as kill:
            self.assertEqual(guarded_job.main(), 2)
            kill.assert_called_once_with(123, guarded_job.signal.SIGTERM)

    def test_gui_fetch_preserves_partial_and_records_actual_transfer(self):
        import io
        from glassing.acquire import Fetcher
        from huntmaps_gui.owner_worker import get

        class Response(io.BytesIO):
            headers = {"Content-Length": "2000"}

        response = Response(b"x" * 2000)
        progress.start_download(2000)
        fetcher = Fetcher(self.root / "sources", 3_000_000_000)
        with patch("urllib.request.urlopen", return_value=response):
            path = get(fetcher, "source.bin", "https://example.test/data")
        self.assertEqual(path.stat().st_size, 2000)
        self.assertEqual(read_json(self.path)["completed"], 2000)
        response = Response(b"z" * 2000)
        with patch("urllib.request.urlopen", return_value=response), patch(
            "huntmaps_gui.owner_worker.check_space",
            side_effect=ValueError("20 GiB reserve"),
        ):
            with self.assertRaisesRegex(ValueError, "20 GiB"):
                get(fetcher, "interrupted.bin", "https://example.test/data")
        self.assertTrue((self.root / "sources/interrupted.bin.partial").exists())
        self.assertFalse((self.root / "sources/interrupted.bin").exists())

    def test_baseline_consent_includes_allowance_and_worker_rechecks(self):
        from fastapi.testclient import TestClient
        from huntmaps_gui.server import create_app
        from huntmaps_gui import worker

        ident = "d" * 32
        config = self.root / "settings.json"
        write(config, dict(radius_m=2000, observation_minutes=30, candidate_count=150))
        plan = dict(
            id=ident,
            name="transfer-fixture",
            config=str(config),
            prepared=True,
            sources_ready=True,
            max_download_mb=3000,
            acquisition_hash="unchanged-sources",
            acquisition=dict(estimated_bytes=0, items=[], errors=[]),
        )
        path = self.config.state_dir / "plans" / (ident + ".json")
        write(path, plan)
        app = create_app(self.config)
        self.addCleanup(app.state.jobs.shutdown)
        client = TestClient(app)
        signature = client.get("/api/plans/" + ident).json()["review_signature"]
        with patch.object(
            app.state.jobs, "start", return_value={"id": "synthetic"}
        ) as start:
            response = client.post(
                "/api/plans/" + ident + "/start",
                headers={"X-HuntMaps": "local"},
                json=dict(download=True, review_signature=signature),
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("--review-signature", start.call_args.args[0])
        write(config, {"candidate_count": 600, "search": {"recommendation_count": 12}})
        self.assertNotEqual(downloads.baseline_review_signature(plan), signature)
        write(config, {})
        plan["max_download_mb"] = 3500
        write(path, plan)
        with patch.object(
            app.state.jobs,
            "start",
            side_effect=AssertionError("Stale consent must not launch"),
        ):
            response = client.post(
                "/api/plans/" + ident + "/start",
                headers={"X-HuntMaps": "local"},
                json=dict(download=True, review_signature=signature),
            )
            self.assertEqual(response.status_code, 400)
        with patch(
            "sys.argv",
            ["worker", "run", ident, "--download", "--review-signature", signature],
        ), patch.object(worker, "run") as run:
            with self.assertRaisesRegex(ValueError, "allowance changed"):
                worker.main()
            run.assert_not_called()
