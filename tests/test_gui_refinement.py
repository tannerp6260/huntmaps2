"""Transition and management regressions on disposable completed runs."""

import copy
import hashlib
import io
import json
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from glassing.transfer import project
from huntmaps_gui import (
    approach_service as approaches,
    workflow,
    first_person as fp,
    first_person_worker as scene_worker,
    working_waypoints as working,
    manual_observers as manual,
    scouting_network as network,
    run_management,
    speed_probe,
)
from huntmaps_gui.search import spread_recommendations
from huntmaps_gui.storage import read_json, write
import test_workflow as base


class RefinementJourney(unittest.TestCase):
    setUpClass = classmethod(base.WorkflowJourney.setUpClass.__func__)
    tearDownClass = classmethod(base.WorkflowJourney.tearDownClass.__func__)
    setUp = base.WorkflowJourney.setUp
    decision = base.WorkflowJourney.decision
    scenario = base.WorkflowJourney.scenario

    def test_per_point_freshness_preserves_unaffected_selection_and_export(self):
        ids = list(self.r.points)[:2]
        for cid in ids:
            state = workflow.get(self.run)
            workflow.decide(
                self.run,
                cid,
                dict(
                    action="shortlist",
                    revision=state["revision"],
                    point=workflow.point(self.run, cid),
                ),
            )
        first = self.scenario()
        body = {
            k: first[k]
            for k in (
                "network_ids",
                "travel_area",
                "exclusions",
                "weights",
                "maximum_slope_deg",
                "kinds",
            )
        }
        body["ids"] = ids
        from shapely.geometry import box, mapping
        from shapely.ops import transform

        p = [self.r.points[cid] for cid in ids]
        body["travel_area"] = mapping(
            transform(
                project(self.r.config["epsg"], 4326),
                box(
                    min(q["x"] for q in p) - 180,
                    min(q["y"] for q in p) - 180,
                    max(q["x"] for q in p) + 180,
                    max(q["y"] for q in p) + 180,
                ),
            )
        )
        s = approaches.create(self.run, body, self.client.app.state.jobs)
        approaches.compute(s["id"])
        result = approaches.status(s["id"])
        self.assertTrue(result["results"]["results"][0]["alternatives"])
        chosen = dict(scenario=s["id"], alternative=0, seal=result["results"]["sha256"])
        self.assertIsNotNone(workflow.selection(self.run, ids[0], chosen))
        state = workflow.get(self.run)
        workflow.decide(
            self.run,
            ids[1],
            dict(
                action="dismiss",
                revision=state["revision"],
                point=workflow.point(self.run, ids[1]),
            ),
        )
        current = approaches.status(s["id"])
        self.assertFalse(current["stale"])
        self.assertIn(ids[1], current["point_stale"])
        self.assertIsNotNone(workflow.selection(self.run, ids[0], chosen))
        self.assertIsNone(workflow.selection(self.run, ids[1], chosen))
        self.assertIn(
            ids[0].encode(),
            approaches.export(s["id"], 0, 0, "gpx", self.client.app.state.jobs),
        )

    def test_absolute_pose_and_manual_exact_scene_no_original_point_lookup(self):
        p = self.r.points[self.cid]
        lon, lat = self.r.ll(p["x"] + 6, p["y"])
        pose = dict(
            anchor=self.cid,
            longitude=lon,
            latitude=lat,
            east_m=3,
            north_m=0,
            scene_key="exact",
            ground_m=0,
            displacement_m=3,
        )
        revision, spec = working.signature(self.r, pose)
        self.assertAlmostEqual(spec["x"], p["x"] + 6, places=6)
        old = dict(pose, longitude=self.r.ll(p["x"] + 3, p["y"])[0])
        self.assertNotEqual(revision, working.signature(self.r, old)[0])
        key = "manual-regression"
        write(
            manual.path(self.run),
            {
                key: dict(
                    id=key,
                    anchor=self.cid,
                    name="Manual",
                    notes="",
                    status="needs inspection",
                    longitude=lon,
                    latitude=lat,
                )
            },
        )
        pose["anchor"] = key
        revision, spec = working.signature(self.r, pose)
        with patch.object(
            fp, "scene", return_value=dict(key="exact", scene_signature={})
        ), patch.object(fp, "observer", return_value=pose), patch.object(
            working, "cached", return_value=dict(spec=spec, metrics={})
        ):
            value = working.start(
                self.run,
                key,
                dict(scene_key="exact", observer_east_m=3, observer_north_m=0),
                self.client.app.state.jobs,
            )
        self.assertEqual(value["status"], "complete")
        self.assertAlmostEqual(
            value["waypoint"]["terrain"]["x"],
            project(4326, self.r.config["epsg"])(lon, lat)[0],
        )
        far = dict(pose, longitude=self.r.ll(p["x"] + 12, p["y"])[0])
        with patch.object(fp, "observer", return_value=far):
            with self.assertRaisesRegex(ValueError, "original anchor"):
                working.start(
                    self.run,
                    key,
                    dict(observer_east_m=3, observer_north_m=0),
                    self.client.app.state.jobs,
                )

    def test_scene_assets_require_current_identity_and_legacy_urls_are_uncached(self):
        ident = fp.new_plan(self.run, [self.cid], fidelity="terrain")
        scene_worker.discover(ident)
        scene_worker.prepare(ident, False)
        meta = fp.scene(self.run, self.cid)
        name = next(n for n in meta["hashes"] if n.endswith(".bin"))
        url = f"/api/runs/{self.run}/first-person/{self.cid}/assets/{name}"
        response = self.client.get(url + "?scene_key=" + meta["key"])
        self.assertEqual(
            hashlib.sha256(response.content).hexdigest(), meta["hashes"][name]
        )
        self.assertIn("immutable", response.headers["cache-control"])
        self.assertEqual(
            self.client.get(url + "?scene_key=" + "f" * 32).status_code, 400
        )
        self.assertEqual(self.client.get(url).headers["cache-control"], "no-store")

    def test_restoring_coordinates_does_not_resurrect_confirmation(self):
        self.decision("shortlist")
        s = self.scenario()
        ident = fp.new_plan(self.run, [self.cid], fidelity="terrain")
        scene_worker.discover(ident)
        scene_worker.prepare(ident, False)
        self.decision("viewed", scene=fp.scene(self.run, self.cid)["key"])
        self.decision("approach", scenario=s["id"], alternative=0)
        self.assertTrue(self.decision("confirm")["points"][self.cid]["confirmed"])
        working.restore(self.run, self.cid, self.client.app.state.jobs)
        self.assertFalse(workflow.get(self.run)["points"][self.cid]["confirmed"])

    def test_archive_and_reviewed_deletion_stale_token_active_jobs_symlink(self):
        run_management.archive(self.run, True)
        listed = self.client.get("/api/runs").json()
        self.assertNotIn(self.run, [r["id"] for r in listed])
        self.assertEqual(self.client.get("/api/runs/" + self.run).status_code, 200)
        run_management.archive(self.run, False)
        # Fixture owner runs are normal generated scout runs.
        preview = run_management.preview(self.run)
        unrelated = self.root / "fixture/observer.geojson"
        original = unrelated.read_bytes()
        marker = self.r.base / "regression-output.txt"
        marker.write_text("generated")
        with self.assertRaisesRegex(ValueError, "changed"):
            run_management.delete(self.run, preview["token"])
        marker.unlink()
        link = self.r.base / "regression-symlink"
        link.symlink_to(unrelated)
        try:
            with self.assertRaisesRegex(ValueError, "Symlink"):
                run_management.preview(self.run)
        finally:
            link.unlink()
        preview = run_management.preview(self.run)
        write(self.state / "jobs" / ("a" * 32 + ".json"), dict(status="running"))
        with self.assertRaisesRegex(ValueError, "active job"):
            run_management.delete(self.run, preview["token"])
        (self.state / "jobs" / ("a" * 32 + ".json")).unlink()
        # Work on a disposable copy because other cases share the class workspace.
        with patch.object(run_management.shutil, "rmtree") as remove:
            run_management.delete(self.run, preview["token"])
            self.assertIn(self.r.base, [c.args[0] for c in remove.call_args_list])
        self.assertEqual(unrelated.read_bytes(), original)

    def test_protected_historical_and_shared_run_deletion_refused(self):
        with patch.object(
            run_management,
            "read_json",
            side_effect=lambda p, d=None: (
                dict(sha256={"results/new-run/scouting.json": "x"})
                if str(p).endswith("CLEANUP_PRESERVED.json")
                else read_json(p, d)
            ),
        ):
            with self.assertRaisesRegex(ValueError, "protected"):
                run_management.preview(self.run)
        from types import SimpleNamespace

        real_run = self.r
        with patch(
            "huntmaps_gui.catalog.runs",
            return_value=[dict(id=self.run), dict(id="retained")],
        ), patch(
            "huntmaps_gui.catalog.Run",
            side_effect=lambda ident: (
                real_run
                if ident == self.run
                else SimpleNamespace(hashes={str(real_run.dem_path): "x"})
            ),
        ):
            with self.assertRaisesRegex(ValueError, "references"):
                run_management.preview(self.run)

    def test_network_retry_reuses_verified_response_and_keeps_cumulative_allowance(
        self,
    ):
        payload = json.dumps(dict(type="FeatureCollection", features=[])).encode()
        payload += b" " * (8_000_000 - len(payload))
        p = network.network_plan([-111.6, 37.95, -111.59, 37.96], 20)
        calls = []
        fail = [True]

        def provider(url, **kwargs):
            calls.append(url)
            if "Trails" in url and fail[0]:
                raise OSError("interrupt trails")
            return io.BytesIO(payload)

        # Services use separate road/trail URLs. Fail the second actual request.
        def controlled(url, **kwargs):
            calls.append(url)
            if len(calls) == 2:
                raise OSError("interrupt trails")
            return io.BytesIO(payload)

        with patch("urllib.request.urlopen", side_effect=controlled):
            with self.assertRaises(OSError):
                network.acquire(p["id"], 20_000_000)
            result = network.acquire(p["id"], 20_000_000)
        self.assertEqual(len(calls), 3, "Roads must not be transferred again")
        ledger = read_json(self.state / "network-plans" / f"{p['id']}-transfer.json")
        self.assertEqual(ledger["received_bytes"], 16_000_000)
        self.assertLessEqual(ledger["received_bytes"], ledger["ceiling_bytes"])
        self.assertEqual(len(result), 2)

    def test_texture_resolves_relative_path_in_run_workspace(self):
        image = self.root / "workspace-image.png"
        image.write_bytes(b"path test")
        fake = copy.copy(self.r)
        fake.images = [dict(path="workspace-image.png")]
        observed = []
        fake.validate = lambda p: observed.append(str(p))
        with patch.object(
            scene_worker,
            "imagery_mosaic",
            return_value=np.zeros((4, 4, 4), dtype=np.uint8),
        ):
            scene_worker.texture(fake, self.cid, self.state, pixels=4)
        self.assertEqual(observed, [str(image)])

    def test_diversity_keeps_scores_and_all_points(self):
        rows = [
            dict(
                id=str(i),
                group="automated",
                x=x,
                y=0,
                raw_km2=10 - i,
                foreground_category="low mapped tree cover",
            )
            for i, x in enumerate([0, 20, 50, 200, 400])
        ]
        before = copy.deepcopy(rows)
        self.assertEqual(
            [r["id"] for r in spread_recommendations(rows, 3, 150)], ["0", "3", "4"]
        )
        self.assertEqual(
            [r["id"] for r in spread_recommendations(rows, 3, 0)], ["0", "1", "2"]
        )
        self.assertEqual(rows, before)

    def test_speed_default_probe_bound_cancel_and_actual_rate_precedence(self):
        self.assertEqual(speed_probe.estimate_rate(), (2_500_000, "20 Mbps default"))
        write(
            self.state / "speed-probe.json",
            dict(updated=time.time(), bytes_per_s=1_000_000),
        )
        self.assertEqual(speed_probe.estimate_rate()[0], 1_000_000)
        write(
            self.state / "transfer-rates.json",
            {"example.test": dict(updated=time.time(), bytes_per_s=4_000_000)},
        )
        from huntmaps_gui.downloads import time_estimate

        self.assertAlmostEqual(
            time_estimate(6_000_000, ["example.test"])["minimum_s"], 1
        )

        class Idle:
            lock = __import__("threading").RLock()

            def list(self, **kwargs):
                return []

        total = [0]

        class Response(io.BytesIO):
            def read(self, n):
                block = super().read(n)
                total[0] += len(block)
                return block

        with patch.dict(os.environ, HUNTMAPS_DISABLE_SPEED_PROBE="0"), patch(
            "urllib.request.urlopen", return_value=Response(b"x" * 3_000_000)
        ):
            speed_probe.start(Idle())
            end = time.monotonic() + 5
            while time.monotonic() < end:
                if read_json(self.state / "speed-probe.json", {}).get("attempted"):
                    break
                time.sleep(0.01)
        self.assertEqual(total[0], speed_probe.MAX_BYTES)
        self.assertEqual(
            read_json(self.state / "speed-probe.json")["status"], "complete"
        )
