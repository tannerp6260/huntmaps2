"""Actual GMU54 sources and actual API/worker; independent totals and recovery.

Requires the authoritative local prepared pack. No synthetic source is substituted.
All writes use a new disposable TrailScout state retained for inspection.
"""

import copy
from datetime import date
import json
import math
from pathlib import Path
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET

import numpy as np
from fastapi.testclient import TestClient
from pyproj import Transformer
from shapely.geometry import LineString, Point

from trail_scout.app import create_app, Service
from trail_scout.storage import Paths, atomic, read, file_hash
from trail_scout.sources import access, geographic
from trail_scout.network import Network
from trail_scout.analysis import habitat_layers
from trail_scout import planner, profiles


class RealWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = Path(tempfile.mkdtemp(prefix="trailscout-real-tests-"))
        cls.paths = Paths(state=cls.folder / "state")
        cls.client = TestClient(create_app(cls.paths))
        cls.service = cls.client.app.state.service
        cls.entries = cls.client.get("/api/starts").json()
        cls.inputs = dict(
            date="2026-10-31", start_id=cls.entries[0]["id"], candidate_budget=16
        )
        cls.result = cls.calculate(cls.inputs)
        assert cls.result[
            "options"
        ], "Real prepared Soap Creek should provide an evaluated feasible option"
        cls.option = next(
            o
            for o in cls.result["options"]
            if o["id"] == cls.result["recommended"]["am"]
        )
        cls.saved = cls.save(cls.result, cls.option)
        print("REAL DATA EVIDENCE:", cls.folder, flush=True)
        atomic(cls.folder / "real-result.json", cls.result)

    @classmethod
    def calculate(cls, inputs):
        response = cls.client.post("/api/jobs", json=inputs)
        if response.status_code != 200:
            raise AssertionError(response.text)
        job = response.json()
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            value = cls.client.get("/api/jobs/" + job["id"]).json()
            if value["status"] == "completed":
                return cls.client.get("/api/analyses/" + value["analysis_id"]).json()
            if value["status"] in ("failed", "cancelled", "interrupted"):
                raise AssertionError(value)
            time.sleep(0.05)
        raise AssertionError("Real job timed out")

    @classmethod
    def save(cls, r, o, **extra):
        response = cls.client.post(
            "/api/plans",
            json=dict(
                analysis_id=r["analysis_id"],
                option_id=o["id"],
                settings=r["settings"],
                mode="am",
                name="REAL GMU54 verification",
                **extra
            ),
        )
        if response.status_code != 200:
            raise AssertionError(response.text)
        return response.json()

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.service.close()

    def test_second_instance_cannot_rewrite_live_state(self):
        before = {
            p.name: p.read_bytes() for p in (self.paths.state / "jobs").glob("*.json")
        }
        with self.assertRaises(ValueError):
            Service(self.paths)
        self.assertEqual(
            {
                p.name: p.read_bytes()
                for p in (self.paths.state / "jobs").glob("*.json")
            },
            before,
        )

    def test_independent_real_geometry_and_weighted_union(self):
        option = self.option
        t = Transformer.from_crs(4326, 32613, always_xy=True)
        distance = 0
        ascent = 0
        for leg in option["legs"]:
            coords = [t.transform(*p) for p in leg["geometry"]["coordinates"]]
            distance += sum(math.dist(a, b) for a, b in zip(coords, coords[1:]))
            z = [p["elevation_m"] for p in leg["profile"]]
            ascent += sum(max(0, b - a) for a, b in zip(z, z[1:]))
        self.assertAlmostEqual(distance, option["movement"]["distance_m"], places=5)
        self.assertAlmostEqual(ascent, option["movement"]["ascent_m"], places=8)
        shape_ = tuple(self.result["grid"]["shape"])
        union = np.zeros(shape_, bool)
        for p in option["viewpoints"]:
            path = self.paths.state / "cache/viewsheds" / p["mask_key"] / "mask.npz"
            with np.load(path) as v:
                union |= (
                    np.unpackbits(v["bits"], count=union.size)
                    .reshape(shape_)
                    .astype(bool)
                )
        hpath = next((self.paths.state / "cache/habitat").glob("*/layers.npz"))
        with np.load(hpath) as layers:
            known = layers["known"]
            q = layers["h"] * layers["g"]
            # This real lower Soap Creek view lies wholly inside the target unit;
            # independently assert target physical area equals visible mask count.
            self.assertEqual(option["coverage"]["matching_m2"], union.sum() * 100)
            independent = float(
                np.dot(q.ravel(), (union & known).ravel().astype(float)) * 100
            )
        self.assertAlmostEqual(
            independent, option["coverage"]["effective_m2"], places=7
        )
        atomic(
            self.folder / "independent-totals.json",
            dict(
                distance_m=distance,
                ascent_m=ascent,
                weighted_union_m2=independent,
                option=option["id"],
            ),
        )

    def test_save_reopen_exports_exact_geometry_versions_and_stale(self):
        saved = self.saved
        reopened = self.client.get("/api/plans/" + saved["id"]).json()
        self.assertEqual(reopened, saved)
        out = self.client.get("/api/plans/" + saved["id"] + "/export/json").json()
        self.assertEqual(out["option"]["viewpoints"], saved["option"]["viewpoints"])
        gpx = ET.fromstring(
            self.client.get("/api/plans/" + saved["id"] + "/export/gpx").content
        )
        ns = {"g": "http://www.topografix.com/GPX/1/1"}
        segments = gpx.findall(".//g:trkseg", ns)
        self.assertEqual(len(segments), len(saved["option"]["legs"]))
        for seg, leg in zip(segments, saved["option"]["legs"]):
            actual = [(float(p.attrib["lon"]), float(p.attrib["lat"])) for p in seg]
            self.assertEqual(actual, [tuple(p) for p in leg["geometry"]["coordinates"]])
        self.assertIn(
            "America/Denver",
            self.client.get("/api/plans/" + saved["id"] + "/export/md").text,
        )
        changed = copy.deepcopy(self.result["settings"])
        changed["date"] = "2026-11-01"
        response = self.client.post(
            "/api/plans",
            json=dict(
                analysis_id=self.result["analysis_id"],
                option_id=self.option["id"],
                settings=changed,
                mode="am",
            ),
        )
        self.assertEqual(response.status_code, 409)
        new = self.save(self.result, self.option, parent_id=saved["id"])
        self.assertEqual(new["parent_id"], saved["id"])
        self.assertEqual(self.client.get("/api/plans/" + saved["id"]).json(), saved)
        conflict = self.client.post(
            "/api/plans",
            json=dict(
                analysis_id=self.result["analysis_id"],
                option_id=self.option["id"],
                settings=self.result["settings"],
                mode="am",
                parent_id=saved["id"],
            ),
        )
        self.assertEqual(conflict.status_code, 409)

    def test_owner_reject_pin_limits_and_segment_affect_actual_plans(self):
        point = self.option["viewpoints"][0]
        inputs = {
            **self.inputs,
            "pinned": [dict(longitude=point["longitude"], latitude=point["latitude"])],
        }
        pinned = self.calculate(inputs)
        self.assertTrue(pinned["options"])
        self.assertTrue(
            all(
                any(v["id"] == point["id"] for v in o["viewpoints"])
                for o in pinned["options"]
            )
        )
        rejected = self.calculate({**self.inputs, "rejected": [point["id"]]})
        self.assertTrue(
            all(
                all(v["id"] != point["id"] for v in o["viewpoints"])
                for o in rejected["options"]
            )
        )
        impossible = self.calculate(
            {**inputs, "profile": dict(preset="dad", max_gain_ft=50, max_miles=0.5)}
        )
        self.assertEqual(impossible["options"], [])
        self.assertTrue(impossible["pin_errors"])
        denied = self.client.post(
            "/api/jobs",
            json={
                **self.inputs,
                "excluded_segments": [self.result["start"]["segment"]],
            },
        ).json()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status = self.client.get("/api/jobs/" + denied["id"]).json()
            if status["status"] == "failed":
                break
            time.sleep(0.05)
        self.assertEqual(status["status"], "failed")
        self.assertIn("start", status["error"].lower())
        self.assertEqual(
            self.client.get("/api/plans/" + self.saved["id"]).json(), self.saved
        )

    def test_cancellation_duplicate_and_restart_preserve_saved(self):
        inputs = {**self.inputs, "candidate_budget": 17}
        response = self.client.post("/api/jobs", json=inputs)
        self.assertEqual(response.status_code, 200)
        job = response.json()
        duplicate = self.client.post("/api/jobs", json=inputs)
        self.assertEqual(duplicate.json()["id"], job["id"])
        conflict = self.client.post(
            "/api/jobs", json={**inputs, "candidate_budget": 18}
        )
        self.assertEqual(conflict.status_code, 409)
        self.client.post("/api/jobs/" + job["id"] + "/cancel")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status = self.client.get("/api/jobs/" + job["id"]).json()
            if status["status"] == "cancelled":
                break
            time.sleep(0.05)
        self.assertEqual(status["status"], "cancelled")
        ident = "1" * 32
        atomic(
            self.paths.artifact("jobs", ident).with_suffix(".json"),
            dict(id=ident, status="running", created_utc="2026-10-19T00:00:00+00:00"),
        )
        self.client.close()
        self.service.close()
        type(self).client = TestClient(create_app(self.paths))
        type(self).service = type(self).client.app.state.service
        self.assertEqual(self.service.job(ident)["status"], "interrupted")
        self.assertEqual(
            self.client.get("/api/plans/" + self.saved["id"]).json(), self.saved
        )

    def test_combined_can_be_saved_with_explicit_sufficient_day_limits(self):
        result = self.calculate(
            {
                **self.inputs,
                "profile": dict(
                    preset="together",
                    max_hours=18,
                    offtrail_miles=1,
                    offtrail_minutes=120,
                ),
            }
        )
        option = next(
            o for o in result["options"] if o["schedules"]["combined"]["feasible"]
        )
        response = self.client.post(
            "/api/plans",
            json=dict(
                analysis_id=result["analysis_id"],
                option_id=option["id"],
                settings=result["settings"],
                mode="combined",
                name="Engineering combined-day logistics check; uncalibrated edited limits",
            ),
        )
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()
        ns = {"g": "http://www.topografix.com/GPX/1/1"}
        root = ET.fromstring(
            self.client.get("/api/plans/" + saved["id"] + "/export/gpx").content
        )
        self.assertEqual(len(root.findall(".//g:trkseg", ns)), 2 * len(option["legs"]))
        geo = self.client.get("/api/plans/" + saved["id"] + "/export/geojson").json()
        tracks = [
            f for f in geo["features"] if f["properties"].get("kind") == "itinerary"
        ]
        self.assertEqual([f["properties"]["role"] for f in tracks].count("outbound"), 2)
        self.assertEqual([f["properties"]["role"] for f in tracks].count("return"), 2)
        self.assertAlmostEqual(
            sum(f["properties"]["distance_m"] for f in tracks),
            option["schedules"]["combined"]["movement"]["distance_m"],
        )

    def test_real_closed_road_is_explicit_scenario_and_foot_closure_excludes(self):
        pack = self.service.data()
        row = next(
            r
            for r in pack.network
            if r["motor_closed"]
            and r["geometry"].length > 300
            and pack.boundary.covers(Point(r["geometry"].coords[0]))
        )
        pt = Point(row["geometry"].coords[0])
        start = dict(id="real-closed-scenario", x=pt.x, y=pt.y, segment=row["id"])
        terrain = pack.terrain(pt.buffer(1500).bounds)
        layers, _ = habitat_layers(pack, terrain, self.paths.state / "cache")
        c = planner.validate(dict(corridor_m=1000, candidate_budget=8))
        with self.assertRaises(ValueError):
            Network(
                pack,
                start,
                terrain,
                profiles.validate(),
                c,
                layers["tree"],
                layers["shrub"],
            )
        c["explore_unknown"] = True
        network = Network(
            pack,
            start,
            terrain,
            profiles.validate(),
            c,
            layers["tree"],
            layers["shrub"],
        )
        self.assertTrue(any(e["segment"] == row["id"] for e in network.edges.values()))
        c["restrictions"] = [
            dict(
                segment=row["id"],
                foot="closed",
                provenance="LABELED ENGINEERING FIXTURE restriction on real source geometry; not an official closure finding",
            )
        ]
        with self.assertRaises(ValueError):
            Network(
                pack,
                start,
                terrain,
                profiles.validate(),
                c,
                layers["tree"],
                layers["shrub"],
            )
        atomic(
            self.folder / "real-closed-road-scenario.json",
            dict(
                segment=row["id"],
                properties=row["properties"],
                source=pack.extra_specs["closed_roads"],
                graph_edges=len(network.edges),
                status=access(row, date(2026, 10, 31)),
                interpretation="Real source geometry and motor-closed status. Foot use unknown, explored only as explicit scenario; fixture foot closure excludes it. No permission/safety certification.",
            ),
        )

    def test_real_closed_roads_and_competing_access_limits(self):
        pack = self.service.data()
        closed = [r for r in pack.network if r["motor_closed"]]
        self.assertTrue(
            closed,
            "Real USFS separate closed-road source is required for this assertion",
        )
        statuses = [access(r, date(2026, 10, 31)) for r in closed]
        self.assertTrue(all(s["motor"] == "closed" for s in statuses))
        self.assertTrue(any(s["foot"] == "unknown" for s in statuses))
        evidence = self.option["viewpoints"][0]["access"]
        self.assertIsNotNone(evidence["other_entry_straight_m"])
        self.assertGreaterEqual(evidence["nearest_motor_m"], 0)
        self.assertIn("may be missing", evidence["completeness"])
        atomic(
            self.folder / "real-access-evidence.json",
            dict(
                closed_count=len(closed),
                examples=[
                    dict(
                        id=r["id"],
                        properties=r["properties"],
                        status=access(r, date(2026, 10, 31)),
                    )
                    for r in closed[:3]
                ],
                competing=evidence,
            ),
        )


if __name__ == "__main__":
    unittest.main()
