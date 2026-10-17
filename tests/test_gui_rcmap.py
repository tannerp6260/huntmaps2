"""Annual MRLC requests, provenance and non-destructive acquisition recovery."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from glassing import owner_data
from huntmaps_gui import rcmap_sources as rcmap
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui.source_reuse import compatible
from huntmaps_gui.storage import read_json, write


class AnnualRcmap(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="huntmaps-annual-rcmap-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app_config = AppConfig(workspace=self.root, state_dir=self.root / "state")
        context = configured(self.app_config)
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.config = dict(
            data=dict(
                dem=True, tree=None, shrub=None, herb=None, summer=True, winter=True
            ),
            epsg=32613,
            resolution_m=10,
        )
        self.inputs = dict(
            acquisition_requests=dict(
                terrain=dict(bounds=[300000, 4280000, 301000, 4281000])
            )
        )

    def items(self):
        return rcmap.plan(self.config, self.inputs, owner_data.plan)[0]

    def legacy(self):
        return owner_data.plan(self.config, self.inputs)[0]

    def test_annual_sources_preserve_request_geometry_and_freeze_cli(self):
        old = self.legacy()
        new = self.items()
        self.assertEqual(self.legacy(), old)
        self.assertEqual([v["key"] for v in new], ["tree", "shrub", "herb"])
        for before, after in zip(old, new):
            q = parse_qs(urlparse(after["url"]).query)
            original = parse_qs(urlparse(before["url"]).query)
            key = after["key"]
            self.assertEqual(urlparse(after["url"]).hostname, "www.mrlc.gov")
            self.assertEqual(
                q["coverage"], [f"rcmap_{key}:rcmap_{rcmap.COMPONENTS[key]}_2023"]
            )
            self.assertNotIn("time", q)
            for field in (
                "bbox",
                "crs",
                "response_crs",
                "resx",
                "resy",
                "format",
                "interpolation",
            ):
                self.assertEqual(q[field], original[field])
            self.assertNotEqual(before["name"], after["name"])
            self.assertEqual(after["required_bounds"], before["required_bounds"])
            self.assertGreater(after["estimated_bytes"], before["estimated_bytes"])
            self.assertEqual(after["observation_year"], 2023)
            self.assertIn("Unknown", after["product_release"])

    def test_nonvegetation_sources_and_errors_pass_through(self):
        item = dict(key="dem", url="https://example.test/dem", name="dem.tif")
        error = "Catalog unavailable"
        got, errors = rcmap.plan({}, {}, lambda *_: ([item], [error]))
        self.assertEqual(got, [item])
        self.assertEqual(errors, [error])

    def test_delivered_grid_and_unknown_cover_are_preserved(self):
        import numpy as np
        from osgeo import gdal, osr
        from huntmaps_gui.acquisition import validate, validating

        path = self.root / rcmap.filename("tree")
        ds = gdal.GetDriverByName("GTiff").Create(str(path), 8, 8, 1, gdal.GDT_Byte)
        sr = osr.SpatialReference()
        sr.ImportFromEPSG(32613)
        ds.SetProjection(sr.ExportToWkt())
        ds.SetGeoTransform((299900, 29.5, 0, 4280150, 0, -30.4))
        values = np.full((8, 8), 20, dtype=np.uint8)
        values[3:5, 3:5] = 101
        ds.GetRasterBand(1).SetNoDataValue(101)
        ds.GetRasterBand(1).WriteArray(values)
        ds = None
        before = path.read_bytes()
        inputs = dict(
            acquisition_requests=dict(
                terrain=dict(bounds=[300000, 4280000, 300100, 4280100])
            )
        )
        with validating(self.config, inputs):
            validate(path, path.name, self.items()[0])
        diagnostic = owner_data.coverage(
            path, [300000, 4280000, 300100, 4280100], 32613, vegetation=True
        )
        self.assertTrue(diagnostic["geographic_coverage"])
        self.assertGreater(diagnostic["unknown_cells"], 0)
        self.assertEqual(diagnostic["nodata"], 101)
        self.assertEqual(path.read_bytes(), before)

    def test_cache_does_not_equate_year_or_endpoint_or_release(self):
        request = self.items()[0]
        self.assertTrue(compatible("tree", request, request, [], 32613))
        for change in (
            dict(url=self.legacy()[0]["url"]),
            dict(url=request["url"].replace("_2023", "_2024")),
            dict(component="shrub"),
            dict(product_release="Different release"),
            dict(source_policy_version=0),
            dict(observation_year=2024),
        ):
            with self.subTest(change=change):
                self.assertFalse(
                    compatible("tree", dict(request, **change), request, [], 32613)
                )

    def record(self):
        ident = "a" * 32
        root = self.root / "results" / "failed-area"
        root.mkdir(parents=True)
        (root / "analysis").mkdir()
        for name in ["intake.json", "manual_import.json", "transfer_owner.json"]:
            write(root / "analysis" / name, {})
        config_path = self.root / "state" / "plans" / (ident + "-config.json")
        write(
            config_path, dict(radius_m=500, observation_minutes=30, candidate_count=24)
        )
        area = self.root / "area.geojson"
        write(area, {})
        record = dict(
            id=ident,
            name="failed-area",
            config=str(config_path),
            area=str(area),
            prepared=True,
            max_download_mb=600,
            acquisition=dict(items=self.legacy(), estimated_bytes=10000, errors=[]),
        )
        write(self.root / "state" / "plans" / (ident + ".json"), record)
        for name in ["scouting.json", "acquisition.json", "download_plan.json"]:
            write(root / name, {"original": name})
        return record, root

    def test_snapshot_and_analysis_guard_preserve_previous_files(self):
        record, root = self.record()
        before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
        self.assertTrue(rcmap.refresh_required(record))
        folder = Path(rcmap.snapshot(record))
        self.assertEqual(read_json(folder / "plan.json"), record)
        for name in ["scouting.json", "acquisition.json", "download_plan.json"]:
            self.assertEqual((folder / name).read_bytes(), (root / name).read_bytes())
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        write(root / "analysis/pool.json", [])
        with self.assertRaisesRegex(ValueError, "new run name"):
            rcmap.snapshot(record)
        (root / "analysis/pool.json").unlink()
        write(root / "manifest.json", {})
        with self.assertRaisesRegex(ValueError, "Completed results"):
            rcmap.snapshot(record)

    def test_api_reports_refresh_and_rejects_stale_start(self):
        from huntmaps_gui.server import create_app

        record, root = self.record()
        app = create_app(self.app_config)
        self.addCleanup(app.state.jobs.shutdown)
        client = TestClient(app)
        path = "/api/plans/" + record["id"]
        value = client.get(path).json()
        self.assertTrue(value["source_refresh_required"])
        self.assertIsNone(value["source_refresh_error"])
        with patch.object(
            app.state.jobs, "start", return_value={"id": "prepare"}
        ) as start:
            saved_path = self.root / "state/plans" / (record["id"] + ".json")
            before = saved_path.read_bytes()
            with patch.object(
                app.state.jobs, "list", return_value=[dict(status="running")]
            ):
                r = client.post(path + "/prepare", headers={"X-HuntMaps": "local"})
                self.assertEqual(r.status_code, 400, r.text)
            self.assertEqual(saved_path.read_bytes(), before)
            r = client.post(
                path + "/start",
                headers={"X-HuntMaps": "local"},
                json={"download": True, "review_signature": value["review_signature"]},
            )
            self.assertEqual(r.status_code, 400, r.text)
            start.assert_not_called()
            r = client.post(path + "/prepare", headers={"X-HuntMaps": "local"})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(start.call_count, 1)
            history = Path(read_json(saved_path)["source_history"])
            self.assertEqual((history / "plan.json").read_bytes(), before)
            write(root / "analysis/scores.json", {})
            value = client.get(path).json()
            self.assertIn("new run name", value["source_refresh_error"])
            r = client.post(path + "/prepare", headers={"X-HuntMaps": "local"})
            self.assertEqual(r.status_code, 400, r.text)
            self.assertEqual(start.call_count, 1)

    def test_cached_only_approvals_need_no_endpoint_migration(self):
        self.assertFalse(rcmap.refresh_required(dict(acquisition=dict(items=[]))))
        self.assertFalse(
            rcmap.refresh_required(
                dict(
                    source_policy_version=rcmap.POLICY_VERSION,
                    acquisition=dict(items=self.items()),
                )
            )
        )
        self.assertTrue(
            rcmap.refresh_required(
                dict(
                    source_policy_version=rcmap.POLICY_VERSION,
                    acquisition=dict(items=self.legacy()),
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
