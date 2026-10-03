"""Actual GUI worker -> unchanged CLI baseline, entirely inside a disposable workspace."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from huntmaps_gui.config import AppConfig, configured, PROJECT
from huntmaps_gui.jobs import Jobs, ACTIVE
from huntmaps_gui.storage import read_json, write


class GuiBaselineWorker(unittest.TestCase):
    def test_prepare_baseline_and_verify_in_disposable_workspace(self):
        with tempfile.TemporaryDirectory(prefix="huntmaps-worker-") as folder:
            root = Path(folder)
            workspace = root / "workspace"
            workspace.mkdir()
            state = root / "state"
            for name in ("glassing", "configs", "docs"):
                (workspace / name).symlink_to(PROJECT / name, target_is_directory=True)
            shutil.copy2(PROJECT / "scout", workspace / "scout")
            shutil.copy2(
                PROJECT / "environment.scout.yml", workspace / "environment.scout.yml"
            )
            config = AppConfig(state_dir=state, workspace=workspace)
            env = dict(
                os.environ,
                **config.environment(),
                PYTHONPATH=str(PROJECT),
                PYTHONDONTWRITEBYTECODE="1"
            )
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from glassing.transfer_fixture import create; create('fixture.json','fixture')",
                ],
                cwd=workspace,
                env=env,
                check=True,
                capture_output=True,
                timeout=30,
            )
            key = uuid.uuid4().hex
            write(
                state / "plans" / (key + ".json"),
                dict(
                    id=key,
                    name="gui-fixture",
                    area=str(workspace / "fixture/observer.geojson"),
                    polygon="1",
                    config=str(workspace / "fixture.json"),
                    max_download_mb=600,
                    prepared=False,
                ),
            )
            with configured(config):
                jobs = Jobs()
                try:

                    def run(action, kind):
                        job = jobs.start(
                            [
                                sys.executable,
                                "-u",
                                "-m",
                                "huntmaps_gui.worker",
                                action,
                                key,
                            ],
                            kind,
                            name="gui-fixture",
                            plan=key,
                        )
                        deadline = time.monotonic() + 60
                        while time.monotonic() < deadline:
                            record = next(
                                value
                                for value in jobs.list()
                                if value["id"] == job["id"]
                            )
                            if record["status"] not in ACTIVE:
                                self.assertEqual(
                                    record["status"], "complete", record.get("logs")
                                )
                                return record
                            time.sleep(0.05)
                        self.fail("Fixture worker exceeded its bound")

                    run("prepare", "prepare")
                    self.assertTrue(
                        read_json(state / "plans" / (key + ".json"))["prepared"]
                    )
                    self.assertTrue(
                        read_json(state / "plans" / (key + ".json"))["sources_ready"]
                    )
                    record = run("run", "baseline")
                    self.assertIn(
                        "Baseline report and GIS exports complete", record["logs"]
                    )
                    refreshed = read_json(state / "plans" / (key + ".json"))
                    self.assertTrue(refreshed["sources_ready"])
                    self.assertGreater(
                        refreshed["acquisition"]["already_cached_bytes"], 0
                    )
                    self.assertTrue(
                        (workspace / "results/gui-fixture/manifest.json").is_file()
                    )
                    verification = subprocess.run(
                        ["./scout", "verify", "--name", "gui-fixture"],
                        cwd=workspace,
                        env=dict(env, SCOUT_PYTHON=sys.executable),
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    self.assertEqual(
                        verification.returncode,
                        0,
                        verification.stdout + verification.stderr,
                    )
                finally:
                    jobs.shutdown()
