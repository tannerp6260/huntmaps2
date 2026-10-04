"""Additive API/worker/readback checks, preserving real saved controls."""

import json
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from fastapi.testclient import TestClient
from shapely.geometry import box, mapping, LineString
from shapely.ops import transform
from glassing.transfer import project
from huntmaps_gui.config import configured, AppConfig
from huntmaps_gui.catalog import Run
from huntmaps_gui.storage import read_json, write
from huntmaps_gui.server import create_app
from huntmaps_gui import approach_service as service
from huntmaps_gui.scouting_network import save_network
from huntmaps_gui.scouting_filters import FilteredRun, save, load
from huntmaps_gui.working_waypoints import DisplayRun
from huntmaps_gui.tiles import sources
from huntmaps_gui.maintenance import inventory, backup
from osgeo import gdal
import numpy as np


class ApproachServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="huntmaps-approach-test-")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.config = AppConfig(
            state_dir=self.folder / "state", workspace=self.folder / "workspace"
        )
        self.context = configured(self.config)
        self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)
        self.client = TestClient(create_app(self.config))
        self.addCleanup(self.client.app.state.jobs.shutdown)
        self.headers = {"X-HuntMaps": "local"}
        self.run = "soap-creek-decision-review-v2"
        r = Run(self.run)
        self.r = r
        p = r.points["A0075"]
        self.target = (p["x"], p["y"])
        x, y = self.target
        ll = project(r.config["epsg"], 4326)
        self.area = mapping(transform(ll, box(x - 200, y - 200, x + 200, y + 200)))
        line = transform(ll, LineString([(x - 90, y - 150), (x - 90, y + 150)]))
        n = save_network(
            json.dumps(mapping(line)).encode(),
            ".geojson",
            "trails",
            "Artificial engineering fixture, not mapped access",
        )
        self.network = n["id"]
        self.network_endpoints = n["lines"][0]["coordinates"]
        self.body = dict(
            ids=["A0075"],
            travel_area=self.area,
            network_ids=[self.network],
            weights=dict(slope=1, tree=1, shrub=1, gain=1),
            maximum_slope_deg=60,
        )
        write(
            self.config.state_dir / "annotations" / f"{self.run}.json",
            {"A0075": dict(status="keep", notes="Synthetic approach test only")},
        )

    def test_actual_worker_exports_stale_and_storage(self):
        body = dict(
            self.body,
            start=list(self.network_endpoints[0]),
            pinned=list(self.network_endpoints[-1]),
        )
        response = self.client.post(
            f"/api/runs/{self.run}/approaches", json=body, headers=self.headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        v = response.json()
        ident = v["scenario"]["id"]
        jid = v["job"]["id"]
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            job = next(j for j in self.client.app.state.jobs.list() if j["id"] == jid)
            if job["status"] not in ("running", "cancelling"):
                break
            time.sleep(0.02)
        self.assertEqual(job["status"], "complete", job.get("logs"))
        result = self.client.get("/api/approaches/" + ident).json()
        self.assertFalse(result["stale"])
        self.assertTrue(result["results"]["results"][0]["alternatives"])
        a = result["results"]["results"][0]["alternatives"][0]
        p = self.r.candidate("A0075")
        self.assertEqual(a["offtrail"][-1], [p["longitude"], p["latitude"]])
        self.assertEqual(a["mapped"][0], body["start"])
        pinned_path = next(
            a
            for a in result["results"]["results"][0]["alternatives"]
            if "Pinned departure" in a["labels"]
        )
        self.assertEqual(pinned_path["departure"], body["pinned"])
        self.assertEqual(pinned_path["offtrail"][0], body["pinned"])
        exported = self.client.get(f"/api/approaches/{ident}/export/gpx")
        self.assertEqual(exported.status_code, 200, exported.text)
        root = ET.fromstring(exported.content)
        wp = root.find("{*}wpt")
        self.assertEqual(
            (float(wp.attrib["lon"]), float(wp.attrib["lat"])),
            (p["longitude"], p["latitude"]),
        )
        json_export = self.client.get(f"/api/approaches/{ident}/export/geojson").json()
        self.assertIn("20 m", json_export["properties"]["notice"])
        xy = project(4326, self.r.config["epsg"])
        for kind, key in [
            ("mapped", "mapped_distance_m"),
            ("offtrail", "offtrail_distance_m"),
        ]:
            total = 0
            for f in json_export["features"]:
                if f["properties"].get("kind") == kind:
                    coords = [xy(*p) for p in f["geometry"]["coordinates"]]
                    total += sum(
                        float(np.linalg.norm(np.array(b) - a))
                        for a, b in zip(coords, coords[1:])
                    )
            self.assertAlmostEqual(total, a[key], places=6)
        self.assertTrue(
            any(f["geometry"]["type"] == "Point" for f in json_export["features"])
        )
        metric = read_json(self.config.state_dir / "scouting-metrics" / f"{ident}.json")
        self.assertLess(metric["runtime_s"], 30)
        self.assertLess(metric["peak_rss_kb"], 1536 * 1024)
        items = inventory()["items"]
        self.assertTrue(
            all(
                i["protected"]
                for i in items
                if i["kind"]
                in (
                    "saved approach scenario and referenced results",
                    "referenced network source",
                )
            )
        )
        key = backup()
        self.assertTrue(
            (
                self.config.state_dir
                / "backups"
                / key
                / "approaches"
                / ident
                / "results.json"
            ).exists()
        )
        self.client.put(
            f"/api/runs/{self.run}/annotations/A0075",
            json=dict(status="reject", notes="Changed"),
            headers=self.headers,
        )
        self.assertIn("A0075", self.client.get("/api/approaches/" + ident).json()["point_stale"])
        self.assertEqual(
            self.client.get(f"/api/approaches/{ident}/export/gpx").status_code, 400
        )

    def test_exact_filtered_areas_overlap_and_display_cache(self):
        profile = save(self.run, dict(elevation_m=[3000, 3200]))
        r = FilteredRun(
            DisplayRun(self.run, self.client.app.state.jobs),
            load(profile["id"], self.run),
        )
        result = r.results(["A0075", "V010"])
        self.assertEqual(
            [p["order"] for p in result["candidates"]],
            sorted(
                [p["order"] for p in result["candidates"]],
                key=lambda i: -result["candidates"][
                    next(
                        j for j, p in enumerate(result["candidates"]) if p["order"] == i
                    )
                ]["matching_km2"],
            ),
        )
        masks = {k: r.mask(k)[0] for k in ["A0075", "V010"]}
        gt = r.dem.GetGeoTransform()
        area = abs(gt[1] * gt[5]) / 1e6
        for row in result["candidates"]:
            self.assertAlmostEqual(row["matching_km2"], masks[row["id"]].sum() * area)
        response = self.client.get(
            f'/api/runs/{self.run}/filtered-overlap/{profile["id"]}',
            params={"ids": "A0075,V010"},
        )
        self.assertAlmostEqual(
            response.json()[0]["shared_km2"],
            (masks["A0075"] & masks["V010"]).sum() * area,
        )
        paths, key = sources(r, "visible", "A0075", 0)
        self.assertIn(profile["id"], key)
        ds = gdal.Open(str(paths[0]))
        self.assertEqual(
            (ds.GetRasterBand(4).ReadAsArray() > 0).sum(), masks["A0075"].sum()
        )
        original = self.r.mask("A0075")[0]
        self.assertGreaterEqual(original.sum(), masks["A0075"].sum())

    def test_not_kept_invalid_preferences_and_no_permission_inference(self):
        for extra in (
            dict(weights=dict(slope=-1, tree=1, shrub=1, gain=1)),
            dict(ids=["V010"]),
            dict(travel_area=dict(type="Point", coordinates=[-107, 38])),
        ):
            response = self.client.post(
                f"/api/runs/{self.run}/approaches",
                json=dict(self.body, **extra),
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(
            self.client.post(
                f"/api/runs/{self.run}/approaches", json=self.body
            ).status_code,
            403,
        )

    def test_sampling_changes_only_observer_domain(self):
        import copy
        from glassing.transfer import intake
        from huntmaps_gui.scouting_filters import sampling_exclusion

        c = copy.deepcopy(self.r.config)
        c["work"] = str(self.folder / "sampling-work")
        c["observer_polygon"] = str(self.folder / "observer.geojson")
        c["manual_points"] = None
        write(
            c["observer_polygon"],
            dict(type="Feature", geometry=self.area, properties={}),
        )
        original = intake(c)
        output = self.folder / "eligibility.geojson"
        result = sampling_exclusion(
            c, dict(network_ids=[self.network], distance_m=35), output
        )
        self.assertEqual(result, str(output.resolve()))
        c["observer_exclusions"] = c.get("observer_exclusions", []) + [result]
        constrained = intake(c)
        self.assertEqual(
            original["geometry"]["target"], constrained["geometry"]["target"]
        )
        self.assertEqual(
            original["geometry"]["terrain_halo"],
            constrained["geometry"]["terrain_halo"],
        )
        self.assertLess(constrained["observer_area_km2"], original["observer_area_km2"])
        self.assertTrue(Path(c["observer_polygon"]).exists())

    def test_approach_cancel_preserves_definition_and_previous_scenario(self):
        response = self.client.post(
            f"/api/runs/{self.run}/approaches", json=self.body, headers=self.headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        v = response.json()
        j = v["job"]
        ident = v["scenario"]["id"]
        cancel = self.client.post(
            "/api/jobs/" + j["id"] + "/cancel", headers=self.headers
        )
        self.assertEqual(cancel.status_code, 200, cancel.text)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            item = next(
                p for p in self.client.app.state.jobs.list() if p["id"] == j["id"]
            )
            if item["status"] == "cancelled":
                break
            time.sleep(0.02)
        self.assertEqual(item["status"], "cancelled")
        self.assertTrue(
            (self.config.state_dir / "approaches" / ident / "scenario.json").exists()
        )
        self.assertEqual(self.client.get("/api/approaches/" + ident).status_code, 200)
        # A new explicit scenario can be submitted without resetting the old one.
        next_response = self.client.post(
            f"/api/runs/{self.run}/approaches", json=self.body, headers=self.headers
        )
        self.assertEqual(next_response.status_code, 200, next_response.text)
        self.assertNotEqual(next_response.json()["scenario"]["id"], ident)
        self.assertTrue(
            (self.config.state_dir / "approaches" / ident / "scenario.json").exists()
        )
