"""Real prepared GMU, socket-denied service, immutable saves and warm allocation."""

from copy import deepcopy
from datetime import date
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import numpy as np
from fastapi.testclient import TestClient
from trail_scout.app import create_app
from trail_scout.storage import Paths, ROOT, atomic, read
from trail_scout.planner import calculate, validate
from trail_scout.sources import Pack
from trail_scout.network import starts
from practical_glassing.package import installed_root
from practical_glassing.timed import Objective
from practical_glassing.selection import select_options
from trail_scout.analysis import habitat_layers
from shapely.geometry import Point


class RealTimed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = Path(tempfile.mkdtemp(prefix="trailscout-timed-real-"))
        source = cls.folder / "source"
        (source / "data").mkdir(parents=True)
        (source / ".trailscout").mkdir()
        (source / "data/unit-packs").symlink_to(
            ROOT / "data/unit-packs", target_is_directory=True
        )
        (source / ".trailscout/community").symlink_to(
            ROOT / ".trailscout/community", target_is_directory=True
        )
        cls.paths = Paths(source=source, state=cls.folder / "state")
        cls.guard = patch(
            "socket.socket.connect",
            side_effect=AssertionError("Offline prepared operation must not connect"),
        )
        cls.guard.start()
        cls.pack = Pack(cls.paths)
        entry = next(
            e
            for e in starts(cls.pack, date(2026, 10, 31))
            if e["label"] == "Soap Creek · entry"
        )
        cls.body = dict(start_id=entry["id"], candidate_budget=16, practical_plan={})
        cls.client = TestClient(create_app(cls.paths))
        cls.service = cls.client.app.state.service
        cls.result = cls.job(cls.body)
        cls.option = next(
            o
            for o in cls.result["options"]
            if o["id"] == cls.result["recommended"]["am"]
        )
        print("REAL TIMED OFFLINE EVIDENCE:", cls.folder, flush=True)

    @classmethod
    def job(cls, body):
        response = cls.client.post("/api/jobs", json=body)
        assert response.status_code == 200, response.text
        job = response.json()
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            j = cls.client.get("/api/jobs/" + job["id"]).json()
            if j["status"] == "completed":
                return cls.client.get("/api/analyses/" + j["analysis_id"]).json()
            if j["status"] in ("failed", "cancelled", "interrupted"):
                raise AssertionError(j)
            time.sleep(0.05)
        raise AssertionError("timed job timeout")

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.service.close()
        cls.guard.stop()

    def test_actual_budget_accounting_return_and_export(self):
        r, o = self.result, self.option
        self.assertEqual(r["version"], 2)
        self.assertEqual(
            r["search"]["pair_search_leaders"], r["search"]["supported_viewpoints"]
        )
        self.assertEqual(
            o["movement"]["distance_m"], sum(l["distance_m"] for l in o["legs"])
        )
        self.assertEqual(
            o["movement"]["ascent_m"], sum(l["ascent_m"] for l in o["legs"])
        )
        p = o["schedules"]["am"]["practical"]
        self.assertAlmostEqual(
            sum(v["marginal_relative_m2"] for v in p["visits"]),
            p["relative_m2"],
            places=8,
        )
        self.assertEqual(
            len(p["sectors"]["features"]), sum(len(v["patches"]) for v in p["visits"])
        )
        for v, e in zip(
            p["visits"],
            [e for e in o["schedules"]["am"]["events"] if e["kind"] == "observe"],
        ):
            self.assertEqual(v["observation_minutes"], e["minutes"])
            self.assertLessEqual(v["minutes_used"], e["minutes"])
            self.assertAlmostEqual(
                v["minutes_used"] + v["unused_observation_minutes"], e["minutes"]
            )
        self.assertFalse(o["schedules"]["combined"]["feasible"])
        response = self.client.post(
            "/api/plans",
            json=dict(
                analysis_id=r["analysis_id"],
                option_id=o["id"],
                settings=r["settings"],
                mode="am",
            ),
        )
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()
        self.assertEqual(saved["version"], 2)
        self.assertEqual(saved["option"]["schedules"]["am"]["practical"], p)
        prefix = "/api/plans/" + saved["id"]
        self.assertEqual(self.client.get(prefix).json(), saved)
        geo = self.client.get(prefix + "/export/geojson").json()
        sectors = [
            f
            for f in geo["features"]
            if f["properties"].get("kind") == "selected scan footprint"
        ]
        self.assertEqual(sectors, p["sectors"]["features"])
        gpx = ET.fromstring(self.client.get(prefix + "/export/gpx").content)
        ns = {"g": "http://www.topografix.com/GPX/1/1"}
        self.assertEqual(len(gpx.findall(".//g:trkseg", ns)), len(o["legs"]))
        for seg, leg in zip(gpx.findall(".//g:trkseg", ns), o["legs"]):
            self.assertEqual(
                [(float(p.attrib["lon"]), float(p.attrib["lat"])) for p in seg],
                [tuple(p) for p in leg["geometry"]["coordinates"]],
            )
        self.assertIn(
            "Experimental practical scans", self.client.get(prefix + "/export/md").text
        )
        denied = self.client.post(
            "/api/plans",
            json=dict(
                analysis_id=r["analysis_id"],
                option_id=o["id"],
                settings=r["settings"],
                mode="combined",
            ),
        )
        self.assertEqual(denied.status_code, 422)
        atomic(self.folder / "saved.json", saved)

    def test_schedule_cap_warm_replan_and_cold_equivalence(self):
        body = deepcopy(self.body)
        body["practical_plan"] = {"search_minutes_cap": 30}
        body["schedule"] = {"am_end_offset": 160}
        warm = self.job(body)
        self.assertTrue(warm["search"]["route_basis_reused"])
        self.assertEqual(
            [(p["id"], p["longitude"], p["latitude"]) for p in warm["candidates"]],
            [
                (p["id"], p["longitude"], p["latitude"])
                for p in self.result["candidates"]
            ],
        )
        for o in warm["options"]:
            for v in (o["schedules"]["am"].get("practical") or {}).get("visits", []):
                self.assertLessEqual(v["minutes_used"], 30)
        # Full recomputation in a distinct state is an independent cache-path check.
        coldpaths = Paths(source=self.paths.source, state=self.folder / "cold-state")
        cold = calculate(
            coldpaths, self.pack, body, coldpaths.artifact("analyses", "b" * 32)
        )
        cold = read(coldpaths.artifact("analyses", "b" * 32) / "result.json")
        self.assertEqual(cold["recommended"], warm["recommended"])
        a = {o["id"]: o for o in cold["options"]}
        b = {o["id"]: o for o in warm["options"]}
        self.assertEqual(set(a), set(b))
        for ident in a:
            for options in (a, b):
                for mode in ("am", "pm"):
                    practical = options[ident]["schedules"][mode].get("practical")
                    if practical:
                        url = practical["coverage_url"]
                        (
                            self.assertEqual(self.client.get(url).status_code, 200)
                            if options is b
                            else self.assertTrue(
                                (
                                    coldpaths.artifact("analyses", "b" * 32)
                                    / url.split("/")[-1]
                                ).is_file()
                            )
                        )
                        practical["coverage_url"] = url.split("/")[-1]
            self.assertEqual(a[ident]["schedules"], b[ident]["schedules"])
        atomic(self.folder / "warm.json", warm)

    def test_no_source_or_owner_state_required_and_coarse_honesty(self):
        self.assertFalse((self.paths.source / "data/scouting").exists())
        self.assertFalse((self.paths.source / ".gui").exists())
        for o in self.result["options"]:
            for d in o["inspection"]:
                self.assertIn(d["status"], ("coarse risk", "unknown/uninspected"))
                self.assertFalse(d.get("numerical_adjustment", False))
                self.assertIsNone(d.get("perspective_url"))
            for m in ("am", "pm"):
                for v in (o["schedules"][m].get("practical") or {}).get("visits", []):
                    for p in v["patches"]:
                        self.assertEqual(len(p["foreground_transects"]), 3)
                        self.assertTrue(
                            all(
                                t["status"] in ("coarse risk", "unknown/uninspected")
                                for t in p["foreground_transects"]
                            )
                        )

    def test_stale_settings_and_schema_rejected(self):
        body = deepcopy(self.result["settings"])
        body["practical_plan"]["search_minutes_cap"] = 1
        response = self.client.post(
            "/api/plans",
            json=dict(
                analysis_id=self.result["analysis_id"],
                option_id=self.option["id"],
                settings=body,
                mode="am",
            ),
        )
        self.assertEqual(response.status_code, 409)
        for value in (
            {"version": True},
            {"policy": {"scan_minutes": 30}},
            {"search_minutes_cap": 721},
        ):
            self.assertEqual(
                self.client.post(
                    "/api/jobs", json={**self.body, "practical_plan": value}
                ).status_code,
                422,
            )


if __name__ == "__main__":
    unittest.main()
