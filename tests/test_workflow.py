"""Isolated three-stage journey on a new synthetic run; no historical analyses."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from glassing.transfer import project
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui.catalog import Run
from huntmaps_gui.server import create_app
from huntmaps_gui.storage import read_json, write
from huntmaps_gui import first_person as fp, first_person_worker as worker
from huntmaps_gui import approach_service as approaches, workflow
from huntmaps_gui.scouting_network import save_network
from huntmaps_gui.maintenance import backup, inventory
from huntmaps_gui.downloads import suggested_mb

ROOT = Path(__file__).resolve().parents[1]


class WorkflowJourney(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="huntmaps-workflow-")
        cls.root = Path(cls.temp.name)
        for name in ("glassing", "configs"):
            shutil.copytree(
                ROOT / name,
                cls.root / name,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
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
                "new-run",
            ],
        ):
            result = subprocess.run(
                command,
                cwd=cls.root,
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
        result = subprocess.run(
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
                "another-run",
            ],
            cwd=cls.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

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
        self.run = "new-run"
        self.r = Run(self.run)
        self.cid = next(iter(self.r.points))
        self.headers = {"X-HuntMaps": "local"}

    def decision(self, action, expected=200, **extra):
        current = self.client.get(f"/api/runs/{self.run}/workflow").json()
        point = workflow.point(self.run, self.cid)
        response = self.client.put(
            f"/api/runs/{self.run}/workflow/{self.cid}",
            headers=self.headers,
            json=dict(
                action=action, revision=current["revision"], point=point, **extra
            ),
        )
        self.assertEqual(response.status_code, expected, response.text)
        return response.json()

    def scenario(self):
        p = self.r.points[self.cid]
        ll = project(self.r.config["epsg"], 4326)
        network = save_network(
            json.dumps(
                dict(
                    type="LineString",
                    coordinates=[
                        ll(p["x"] - 60, p["y"] - 120),
                        ll(p["x"] - 60, p["y"] + 120),
                    ],
                )
            ).encode(),
            ".geojson",
            "trails",
            "Artificial fixture; no access claim",
        )
        from shapely.geometry import box, mapping
        from shapely.ops import transform

        scenario = approaches.create(
            self.run,
            dict(
                ids=[self.cid],
                network_ids=[network["id"]],
                travel_area=mapping(
                    transform(
                        ll, box(p["x"] - 180, p["y"] - 180, p["x"] + 180, p["y"] + 180)
                    )
                ),
                maximum_slope_deg=60,
            ),
            self.client.app.state.jobs,
        )
        approaches.compute(scenario["id"])
        return scenario

    def test_gates_early_view_reload_select_confirm_remove_and_recompute(self):
        self.decision("confirm", expected=400)
        ident = fp.new_plan(self.run, [self.cid], fidelity="terrain")
        with patch(
            "urllib.request.urlopen",
            side_effect=AssertionError("Terrain-only must be offline"),
        ):
            worker.discover(ident)
            worker.prepare(ident, False)
        scene = fp.scene(self.run, self.cid)
        self.assertEqual(scene["fidelity"], "terrain")
        self.assertFalse(scene["fine_observer_available"])
        self.decision("viewed", scene=scene["key"])
        self.decision("confirm", expected=400)
        self.decision("shortlist")
        scenario = self.scenario()
        self.decision("approach", scenario=scenario["id"], alternative=-1, expected=400)
        self.decision("approach", scenario=scenario["id"], alternative=0)
        state = self.decision("confirm")
        self.assertTrue(state["points"][self.cid]["confirmed"])
        self.assertTrue(
            self.decision("viewed", scene=scene["key"])["points"][self.cid]["confirmed"]
        )
        self.assertTrue(workflow.get(self.run)["points"][self.cid]["confirmed"])
        stale = self.client.put(
            f"/api/runs/{self.run}/workflow/{self.cid}",
            headers=self.headers,
            json=dict(
                action="remove", revision=0, point=workflow.point(self.run, self.cid)
            ),
        )
        self.assertEqual(stale.status_code, 400)
        second = self.scenario()
        state = workflow.get(self.run)
        self.assertFalse(state["points"][self.cid]["confirmed"])
        self.assertEqual(state["points"][self.cid]["viewed"], scene["key"])
        self.decision("approach", scenario=second["id"], alternative=0)
        self.decision("confirm")
        self.decision("remove")
        self.decision("confirm", expected=400)
        self.assertTrue(
            (self.state / "approaches" / scenario["id"] / "results.json").exists()
        )
        self.assertTrue(
            (
                self.state / "backups" / backup() / "workflows" / (self.run + ".json")
            ).exists()
        )
        self.assertTrue(
            all(
                item["protected"]
                for item in inventory()["items"]
                if item["kind"] == "scene"
            )
        )

    def test_run_scoped_scenes_revisions_manual_points_and_no_coverage(self):
        keys = []
        for run in (self.run, "another-run"):
            ident = fp.new_plan(run, [self.cid], fidelity="terrain")
            worker.discover(ident)
            worker.prepare(ident, False)
            keys.append(fp.scene(run, self.cid)["key"])
        self.assertNotEqual(*keys)
        original = workflow.point(self.run, self.cid)
        self.decision("shortlist")
        bad = self.client.put(
            f"/api/runs/{self.run}/workflow/{self.cid}",
            headers=self.headers,
            json=dict(
                action="confirm",
                revision=workflow.get(self.run)["revision"],
                point=dict(original, revision="old"),
            ),
        )
        self.assertEqual(bad.status_code, 400)
        manual = dict(
            id="manual-test",
            anchor=self.cid,
            name="Artificial manual",
            status="needs inspection",
            notes="",
            longitude=original["longitude"] + 0.0001,
            latitude=original["latitude"],
        )
        write(
            self.state / "manual-observers" / (self.run + ".json"),
            {"manual-test": manual},
        )
        ident = fp.new_plan(self.run, ["manual-test"], fidelity="terrain")
        worker.discover(ident)
        worker.prepare(ident, False)
        self.assertEqual(
            fp.scene(self.run, "manual-test")["observer"]["longitude"],
            manual["longitude"],
        )
        manual["longitude"] += 0.0001
        write(
            self.state / "manual-observers" / (self.run + ".json"),
            {"manual-test": manual},
        )
        with self.assertRaisesRegex(ValueError, "stale"):
            fp.scene(self.run, "manual-test")
        with self.assertRaisesRegex(ValueError, "Waypoint changed"):
            worker.prepare(ident, False)

    def test_metadata_dedup_explicit_acquisition_and_separate_allowance(self):
        import io

        ids = list(self.r.points)[:2]
        catalog = dict(
            items=[
                dict(
                    title="Artificial acquisition " + name,
                    downloadURL="https://rockyweb.usgs.gov/" + name + "/LAZ/tile.laz",
                    sizeInBytes=20_000_000,
                    boundingBox={},
                    publicationDate="2020",
                )
                for name in ("one", "two")
            ]
        )
        ident = fp.new_plan(self.run, ids)
        with patch(
            "urllib.request.urlopen",
            side_effect=lambda *args, **kwargs: io.BytesIO(
                json.dumps(catalog).encode()
            ),
        ):
            worker.discover(ident)
        plan = fp.plan(ident)
        self.assertEqual(len(plan["sources"]), 2)
        self.assertEqual(plan["estimated_new_bytes"], 40_000_000)
        self.assertTrue(plan["needs_acquisition_selection"])
        self.assertEqual(plan["download_cap_bytes"], 50_000_000)
        self.assertTrue(all(source["candidates"] == ids for source in plan["sources"]))
        with self.assertRaisesRegex(ValueError, "Select one recorded"):
            worker.prepare(ident, False)
        selected = fp.new_plan(self.run, ids, acquisition=plan["acquisitions"][0])
        with patch(
            "urllib.request.urlopen",
            side_effect=lambda *args, **kwargs: io.BytesIO(
                json.dumps(catalog).encode()
            ),
        ):
            worker.discover(selected)
        self.assertFalse(fp.plan(selected)["needs_acquisition_selection"])
        self.assertEqual(len(fp.plan(selected)["sources"]), 1)
        response = self.client.put(
            f"/api/first-person/plans/{selected}/allowance",
            headers=self.headers,
            json=dict(max_download_mb=2500),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["download_cap_bytes"], 2_500_000_000)
        response = self.client.put(
            f"/api/first-person/plans/{selected}/allowance",
            headers=self.headers,
            json=dict(max_download_mb=10),
        )
        self.assertEqual(response.status_code, 200, response.text)
        with patch.object(
            worker,
            "acquire",
            side_effect=AssertionError("No bulk transfer before reviewed allowance"),
        ):
            with self.assertRaisesRegex(ValueError, "reviewed transfer allowance"):
                worker.prepare(selected, True)

    def test_dismiss_undo_restore_stale_and_legacy_records(self):
        before = self.decision("shortlist")
        dismissed = self.decision("dismiss")
        self.assertTrue(dismissed["points"][self.cid]["dismissed"])
        self.assertFalse(dismissed["points"][self.cid]["shortlisted"])
        revision = dismissed["revision"]
        restored = self.decision("undo", undo_revision=revision)
        self.assertTrue(restored["points"][self.cid]["shortlisted"])
        self.assertFalse(restored["points"][self.cid]["dismissed"])
        dismissed = self.decision("dismiss")
        self.decision("remove")
        self.decision("undo", expected=400, undo_revision=dismissed["revision"])
        self.decision("dismiss")
        self.decision("restore")
        self.assertFalse(workflow.get(self.run)["points"][self.cid]["dismissed"])
        self.decision("dismiss")
        self.assertTrue(self.decision("shortlist")["points"][self.cid]["shortlisted"])
        saved = workflow.records(self.run)
        saved["version"] = 1
        saved["points"][self.cid].pop("dismissed", None)
        write(workflow.path(self.run), saved)
        self.assertFalse(workflow.get(self.run)["points"][self.cid]["dismissed"])

    def test_download_consent_rejects_changed_scene_allowance(self):
        ident = fp.new_plan(self.run, [self.cid], fidelity="terrain")
        worker.discover(ident)
        p = fp.plan(ident)
        signature = p["review_signature"]
        self.client.put(
            f"/api/first-person/plans/{ident}/allowance",
            headers=self.headers,
            json=dict(max_download_mb=2500),
        )
        with patch.object(
            self.client.app.state.jobs,
            "start",
            side_effect=AssertionError("Outdated consent must not start work"),
        ):
            response = self.client.post(
                f"/api/first-person/plans/{ident}/start",
                headers=self.headers,
                json=dict(download=True, review_signature=signature),
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("consent", response.text)

    def test_allowance_rounding_caps_and_unknown_versions(self):
        for estimate, expected in [
            (0, 10),
            (1, 10),
            (10_000_000, 20),
            (100_000_000, 120),
            (1_900_000_000, 2280),
            (2_000_000_000, 2400),
        ]:
            self.assertEqual(suggested_mb(estimate), expected)
        self.assertEqual(suggested_mb(500_000_000, 500), 500)
        with self.assertRaises(ValueError):
            suggested_mb(float("nan"))
        write(workflow.path(self.run), dict(version=999, revision=0, points={}))
        with self.assertRaisesRegex(ValueError, "Unsupported workflow"):
            workflow.get(self.run)
