"""Audit regressions; disposable state and controlled failures only."""

import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui import catalog, maintenance
from huntmaps_gui.jobs import Jobs
from huntmaps_gui.storage import write


class AuditRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="huntmaps-regression-")
        self.root = Path(self.temp.name)
        self.config = AppConfig(
            source_dir=self.root, workspace=self.root, state_dir=self.root / "state"
        )
        self.context = configured(self.config)
        self.context.__enter__()

    def tearDown(self):
        self.context.__exit__(None, None, None)
        self.temp.cleanup()

    def test_launch_write_failure_reaps_child_and_closes_log(self):
        jobs = Jobs()
        original = __import__("subprocess").Popen
        children = []

        def spawn(*args, **kwargs):
            # Real harmless process group, independent of application inputs.
            proc = original(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                start_new_session=True,
                stdout=kwargs["stdout"],
                stderr=kwargs["stderr"],
            )
            children.append((proc, kwargs["stdout"]))
            return proc

        try:
            with patch("huntmaps_gui.jobs.subprocess.Popen", side_effect=spawn), patch(
                "huntmaps_gui.jobs.write", side_effect=OSError("full disk")
            ):
                with self.assertRaises(OSError):
                    jobs.start(["unused"], "fixture")
            self.assertIsNotNone(
                children[0][0].poll(), "Unmanaged process survives failed submission"
            )
            self.assertTrue(children[0][1].closed)
            self.assertFalse(any(t.is_alive() for t in jobs.wait_threads))
        finally:
            for proc, log in children:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=5)
                log.close()
            jobs.shutdown()

    def test_invalid_job_types_are_preserved_and_reported(self):
        for field, value in [
            ("started", "bad timestamp"),
            ("status", []),
            ("id", "../escape"),
            ("finished", float("inf")),
            ("pid", "wrong"),
        ]:
            with self.subTest(field=field):
                path = self.root / "state/jobs" / ("d" * 32 + ".json")
                record = dict(
                    id="d" * 32,
                    status="running",
                    started=1,
                    kind="approach",
                    pid=123,
                    ticks="1",
                    boot_id="fixture",
                )
                record[field] = value
                # JSON writer rejects infinity, emulate external damaged bytes.
                import json

                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(record))
                before = path.read_bytes()
                jobs = Jobs()
                self.assertEqual(jobs.list(False)[0]["status"], "damaged")
                self.assertTrue(maintenance.status()["problems"])
                jobs.shutdown()
                self.assertEqual(path.read_bytes(), before)

    def test_catalog_quarantines_bad_json_and_schema(self):
        for name, content in [
            (
                "good",
                '{"input_kind":"synthetic_fixture","work":"results/good/analysis"}',
            ),
            ("truncated", "{"),
            ("wrong-schema", "[]"),
        ]:
            folder = self.root / "results" / name
            (folder / "analysis").mkdir(parents=True)
            (folder / "scouting.json").write_text(content)
            (folder / "manifest.json").write_text("{}")
            (folder / "analysis/scores.json").write_text("[]")
        self.assertEqual([r["id"] for r in catalog.runs()], ["good"])
        self.assertEqual(len(catalog.run_problems()), 2)
        self.assertEqual(
            (self.root / "results/truncated/scouting.json").read_text(), "{"
        )

    def test_annotation_stale_revision_cannot_replace_newer_notes(self):
        from fastapi.testclient import TestClient
        from huntmaps_gui.server import create_app
        from types import SimpleNamespace

        with patch(
            "huntmaps_gui.api_routes.Run",
            return_value=SimpleNamespace(points={"A": {}}),
        ), TestClient(create_app(self.config)) as client:
            headers = {"X-HuntMaps": "local"}
            endpoint = "/api/runs/fixture/annotations/A"
            first = client.put(
                endpoint,
                headers=headers,
                json={"status": "keep", "notes": "first", "revision": 0},
            )
            self.assertEqual(first.status_code, 200, first.text)
            newer = client.put(
                endpoint,
                headers=headers,
                json={
                    "status": "keep",
                    "notes": "newest",
                    "revision": first.json()["revision"],
                },
            )
            self.assertEqual(newer.status_code, 200, newer.text)
            stale = client.put(
                endpoint,
                headers=headers,
                json={
                    "status": "keep",
                    "notes": "older",
                    "revision": first.json()["revision"],
                },
            )
            self.assertEqual(stale.status_code, 409)
            self.assertEqual(
                client.get("/api/runs/fixture/annotations").json()["A"]["notes"],
                "newest",
            )

    def test_warm_display_validates_authoritative_target_bytes(self):
        import hashlib
        import numpy as np
        from osgeo import gdal, osr
        from types import SimpleNamespace
        from huntmaps_gui.tiles import sources

        folder = self.root / "analysis"
        folder.mkdir()
        dem = gdal.GetDriverByName("MEM").Create("", 2, 2, 1, gdal.GDT_Byte)
        dem.SetGeoTransform((0, 10, 0, 20, 0, -10))
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(32613)
        dem.SetProjection(srs.ExportToWkt())
        for name in ("dem", "target", "visible"):
            gdal.GetDriverByName("GTiff").CreateCopy(str(folder / (name + ".tif")), dem)
        hashes = {
            str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.glob("*.tif")
        }
        run = SimpleNamespace(
            dem=dem,
            dem_path=folder / "dem.tif",
            analysis=folder,
            experimental=False,
            hashes=hashes,
        )
        run.validate = lambda p: catalog.Run.validate(run, p)
        run.visibility_path = lambda _: folder / "visible.tif"
        run.mask = lambda _: (np.ones((2, 2), dtype=bool), {})
        sources(run, "visible", "A", 0)
        target = folder / "target.tif"
        st = target.stat()
        content = bytearray(target.read_bytes())
        content[-1] ^= 1
        target.write_bytes(content)
        os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, "Saved source changed"):
            sources(run, "visible", "A", 0)

    def test_restore_is_snapshot_and_retains_pre_restore_backup(self):
        key = maintenance.create_backup()["backup"]
        later = self.root / "state/workflows/fixture.json"
        write(later, {"revision": 1, "points": {"A": {"shortlisted": True}}})
        result = maintenance.restore(maintenance.Restore(backup=key))
        self.assertFalse(
            later.exists(), "Restore silently merged a post-backup workflow"
        )
        self.assertEqual(result["removed"], 1)
        self.assertTrue(
            (
                self.root
                / "state/backups"
                / result["backup"]
                / "workflows/fixture.json"
            ).exists()
        )

    def test_browsing_burst_keeps_status_responsive(self):
        import asyncio
        import threading
        import httpx
        from huntmaps_gui.server import create_app

        gate = threading.Event()
        entered = []

        def stalled(*args, **kwargs):
            entered.append(1)
            gate.wait(3)
            raise OSError("controlled provider stall")

        async def check():
            app = create_app(self.config)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                with patch.dict(os.environ, {"HUNTMAPS_DISABLE_BROWSING": "0"}), patch(
                    "huntmaps_gui.browsing.urllib.request.urlopen", side_effect=stalled
                ):
                    tiles = [
                        asyncio.create_task(
                            client.get(f"/api/browsing/transportation/10/{i}/100.png")
                        )
                        for i in range(40)
                    ]
                    try:
                        for _ in range(100):
                            if len(entered) == 2:
                                break
                            await asyncio.sleep(0.01)
                        await asyncio.sleep(0.1)
                        response = await asyncio.wait_for(
                            client.get("/api/jobs"), timeout=0.5
                        )
                        self.assertEqual(response.status_code, 200)
                    finally:
                        gate.set()
                        await asyncio.gather(*tiles)
            app.state.jobs.shutdown()

        asyncio.run(check())

    def test_live_worker_still_blocks_submission_after_record_damage(self):
        from unittest.mock import Mock

        jobs = Jobs()
        jobs.process = Mock()
        jobs.process.poll.return_value = None
        try:
            with patch("huntmaps_gui.jobs.subprocess.Popen") as spawn, patch(
                "huntmaps_gui.jobs.os.killpg"
            ):
                with self.assertRaisesRegex(ValueError, "Another job"):
                    jobs.start(["unused"], "fixture")
                spawn.assert_not_called()
        finally:
            jobs.process = None
            jobs.shutdown()

    def test_cancel_damaged_job_reports_recovery_instead_of_type_error(self):
        jobs = Jobs()
        path = self.root / "state/jobs" / ("d" * 32 + ".json")
        write(path, dict(id="d" * 32, started="bad", kind="fixture", status=[]))
        with self.assertRaisesRegex(ValueError, "Damaged job record"):
            jobs.cancel("d" * 32)

    def test_waiter_preserves_damage_and_exposes_diagnostic(self):
        import io
        from unittest.mock import Mock

        jobs = Jobs()
        path = self.root / "state/jobs" / ("d" * 32 + ".json")
        write(path, dict(id="d" * 32, started="bad", kind="fixture", status=[]))
        before = path.read_bytes()
        proc = Mock()
        proc.wait.return_value = 0
        log = io.BytesIO()
        jobs._wait("d" * 32, proc, log)
        self.assertTrue(log.closed)
        self.assertTrue(jobs.storage_errors)
        self.assertEqual(path.read_bytes(), before)

    def test_shutdown_reaps_tracked_worker_when_cancellation_cannot_persist(self):
        import subprocess

        jobs = Jobs()
        children = []
        original = subprocess.Popen

        def spawn(*args, **kwargs):
            child = original(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                start_new_session=True,
                stdout=kwargs["stdout"],
                stderr=kwargs["stderr"],
            )
            children.append(child)
            return child

        try:
            with patch("huntmaps_gui.jobs.subprocess.Popen", side_effect=spawn):
                jobs.start(["unused"], "fixture")
            with patch("huntmaps_gui.jobs.write", side_effect=OSError("full disk")):
                jobs.shutdown()
            self.assertIsNotNone(children[0].poll())
            self.assertTrue(jobs.storage_errors)
        finally:
            for child in children:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=5)
            for thread in jobs.wait_threads:
                thread.join(timeout=3)

    def test_damaged_jobs_do_not_break_cache_or_storage_diagnostics(self):
        from huntmaps_gui import display_cache

        path = self.root / "state/jobs" / ("d" * 32 + ".json")
        write(path, dict(id="d" * 32, kind="fixture", started=1, status=[]))
        cache = self.root / "state/cache/unreferenced.bin"
        cache.parent.mkdir()
        cache.write_bytes(b"keep")
        self.assertTrue(maintenance.status()["problems"])
        self.assertEqual(maintenance.inventory()["reclaimable_bytes"], 0)
        self.assertEqual(display_cache.evict(), 0)
        self.assertTrue(cache.exists())

    def test_healthy_optional_tile_burst_queues_without_rejecting_viewport(self):
        import asyncio, io, threading, time
        import httpx
        from PIL import Image
        from huntmaps_gui.server import create_app

        png = io.BytesIO()
        Image.new("RGBA", (256, 256)).save(png, format="PNG")
        data = png.getvalue()
        active = 0
        maximum = 0
        mutex = threading.Lock()

        def provider(*args, **kwargs):
            nonlocal active, maximum
            with mutex:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.02)
            with mutex:
                active -= 1
            return io.BytesIO(data)

        async def check():
            app = create_app(self.config)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                with patch.dict(os.environ, {"HUNTMAPS_DISABLE_BROWSING": "0"}), patch(
                    "huntmaps_gui.browsing.urllib.request.urlopen", side_effect=provider
                ):
                    responses = await asyncio.gather(
                        *(
                            client.get(f"/api/browsing/transportation/10/{i}/100.png")
                            for i in range(16)
                        )
                    )
                    self.assertEqual([r.status_code for r in responses], [200] * 16)
                    self.assertLessEqual(maximum, 2)
            app.state.jobs.shutdown()

        asyncio.run(check())

    def test_cached_optional_tiles_bypass_stalled_provider_queue(self):
        import asyncio, threading, io
        import httpx
        from PIL import Image
        from huntmaps_gui.server import create_app

        gate = threading.Event()
        entered = []

        def stalled(*args, **kwargs):
            entered.append(1)
            gate.wait(3)
            raise OSError("controlled stall")

        cache = self.root / "state/cache/transportation-v1/10-50-100.png"
        cache.parent.mkdir(parents=True)
        image = io.BytesIO()
        Image.new("RGBA", (256, 256)).save(image, format="PNG")
        cache.write_bytes(image.getvalue())

        async def check():
            app = create_app(self.config)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                with patch.dict(os.environ, {"HUNTMAPS_DISABLE_BROWSING": "0"}), patch(
                    "huntmaps_gui.browsing.urllib.request.urlopen", side_effect=stalled
                ):
                    requests = [
                        asyncio.create_task(
                            client.get(f"/api/browsing/transportation/10/{i}/100.png")
                        )
                        for i in range(2)
                    ]
                    try:
                        for _ in range(100):
                            if len(entered) == 2:
                                break
                            await asyncio.sleep(0.01)
                        response = await asyncio.wait_for(
                            client.get("/api/browsing/transportation/10/50/100.png"),
                            timeout=0.5,
                        )
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.content, image.getvalue())
                    finally:
                        gate.set()
                        await asyncio.gather(*requests)
            app.state.jobs.shutdown()

        asyncio.run(check())
