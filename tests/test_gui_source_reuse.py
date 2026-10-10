"""Verified raw sources can be reused without depending on an old result archive."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from glassing.acquire import digest
from huntmaps_gui.storage import read_json, write
from huntmaps_gui.config import AppConfig, configured


class SourceReuse(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="huntmaps-source-reuse-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = Path(__file__).resolve().parents[1]
        for name in ("glassing", "configs", "docs", "huntmaps_gui"):
            (self.root / name).symlink_to(self.project / name, target_is_directory=True)
        self.env = dict(
            os.environ,
            PYTHONPATH=str(self.root) + os.pathsep + str(self.project),
            HUNTMAPS_WORKSPACE=str(self.root),
            HUNTMAPS_SOURCE_DIR=str(self.root),
            HUNTMAPS_STATE_DIR=str(self.root / "state"),
            HUNTMAPS_DISABLE_SPEED_PROBE="1",
        )
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from glassing.transfer_fixture import create; create('fixture.json','fixture',32613)",
            ],
            cwd=self.root,
            env=self.env,
            check=True,
            capture_output=True,
        )
        self.config = read_json(self.root / "fixture.json")
        self.config.update(normal_scouting=True, manual_points=None)
        self.config["data"]["tree"] = None
        write(self.root / "fixture.json", self.config)
        # Complete, authoritative-product provenance attached to artificial bytes.
        # This is an offline engineering fixture, never a real USGS observation.
        from urllib.parse import urlencode

        params = dict(
            service="WCS",
            version="1.0.0",
            request="GetCoverage",
            coverage="mrlc_tree_westernconus_year_data:tree_westernconus_year_data",
            crs="EPSG:32613",
            response_crs="EPSG:32613",
            bbox="449400,4199400,451320,4201320",
            resx=30,
            resy=30,
            format="GeoTIFF",
            time="2023-01-01T00:00:00Z",
            interpolation="nearest neighbor",
        )
        self.donor = self.root / "results/old-run/downloads/tree_padded120.tif"
        self.donor.parent.mkdir(parents=True)
        from osgeo import gdal

        gdal.Translate(
            str(self.donor), str(self.root / "fixture/tree.tif"), xRes=30, yRes=30
        )
        self.entry = dict(
            url="https://dmsdata.cr.usgs.gov/geoserver/mrlc_tree_westernconus_year_data/wcs?"
            + urlencode(params),
            sha256=digest(self.donor),
            bytes=self.donor.stat().st_size,
            provider="USGS RCMAP",
            acquisition_date="2023 annual product",
            license="USGS public domain",
            retrieved_utc="2026-10-03T00:00:00Z",
        )
        write(self.donor.parent / "manifest.json", {self.donor.name: self.entry})
        (self.root / "sitecustomize.py").write_text(
            "import urllib.request\ndef blocked(*args,**kwargs):\n raise AssertionError('Unexpected external request')\nurllib.request.urlopen=blocked\n"
        )

    def prepare(self, name="reuse"):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "huntmaps_gui.owner_worker",
                "prepare",
                "--area",
                "fixture/observer.geojson",
                "--name",
                name,
                "--polygon",
                "1",
                "--source-config",
                "fixture.json",
                "--max-download-mb",
                "30",
            ],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
        )

    def test_actual_prepare_reuses_raw_download_and_survives_missing_archive(self):
        before = self.donor.read_bytes()
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        selected = read_json(self.root / "results/reuse/scouting.json")["data"]["tree"]
        self.assertEqual(selected["url"], self.entry["url"])
        self.assertEqual(Path(selected["path"]).read_bytes(), before)
        self.assertEqual(self.donor.read_bytes(), before)
        self.assertTrue(
            Path(selected["path"]).is_relative_to(self.root / "state/sources")
        )
        shutil.rmtree(self.donor.parent.parent)
        second = self.prepare("reuse-again")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(
            read_json(self.root / "results/reuse-again/download_plan.json")["items"], []
        )

    def select(self):
        from huntmaps_gui.source_reuse import cached

        config = json.loads(json.dumps(self.config))
        inputs = dict(
            acquisition_requests=dict(
                terrain=dict(bounds=[449450, 4199450, 451150, 4201250])
            )
        )
        with configured(
            AppConfig(
                source_dir=self.root, workspace=self.root, state_dir=self.root / "state"
            )
        ):
            return cached(config, inputs, lambda *_: {}), config

    def update_entry(self, **values):
        self.entry.update(values)
        write(self.donor.parent / "manifest.json", {self.donor.name: self.entry})

    def test_wrong_year_product_or_query_is_not_reused(self):
        original = self.entry["url"]
        for changed in [
            original.replace("2023-", "2024-"),
            original.replace("mrlc_tree_", "mrlc_shrub_"),
            original.replace("resx=30", "resx=60"),
            original + "&resultRecordCount=1",
        ]:
            with self.subTest(url=changed):
                self.update_entry(url=changed)
                found, _ = self.select()
                self.assertEqual(found, {})

    def test_corrupt_or_unreadable_raw_source_is_retained_and_not_reused(self):
        for content, rehash in [(b"tampered", False), (b"<ExceptionReport/>", True)]:
            self.donor.write_bytes(content)
            if rehash:
                self.update_entry(sha256=digest(self.donor))
            found, _ = self.select()
            self.assertEqual(found, {})
            self.assertEqual(self.donor.read_bytes(), content)

    def test_insufficient_raster_coverage_is_not_reused(self):
        from osgeo import gdal

        ds = gdal.Open(str(self.donor), gdal.GA_Update)
        ds.SetGeoTransform((550000, 30, 0, 5200000, 0, -30))
        ds = None
        self.update_entry(sha256=digest(self.donor))
        self.assertEqual(self.select()[0], {})

    def test_raster_companion_metadata_is_not_silently_lost(self):
        sidecar = self.donor.with_name(self.donor.name + ".aux.xml")
        content = '<PAMDataset><PAMRasterBand band="1"><NoDataValue>12</NoDataValue></PAMRasterBand></PAMDataset>'
        sidecar.write_text(content)
        self.assertEqual(self.select()[0], {})
        self.assertEqual(sidecar.read_text(), content)

    def test_changed_selected_source_or_provenance_stops_without_fallback(self):
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        spec = read_json(self.root / "results/reuse/scouting.json")["data"]["tree"]
        managed = Path(spec["path"])
        original = managed.read_bytes()
        managed.write_bytes(b"corrupted selected source")
        failed = self.prepare()
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("Changed managed source", failed.stderr)
        self.assertEqual(managed.read_bytes(), b"corrupted selected source")
        managed.write_bytes(original)
        manifest = managed.parent / "manifest.json"
        record = read_json(manifest)
        record[managed.name]["provider"] = "changed provider"
        write(manifest, record)
        self.assertIn("Changed managed source", self.prepare().stderr)

    def test_range_query_coverage_and_completeness_are_required(self):
        from glassing.owner_data import CPW, plan
        from huntmaps_gui.source_reuse import compatible
        from urllib.parse import urlencode

        bounds = [449450, 4199450, 451150, 4201250]
        config = json.loads(json.dumps(self.config))
        config["data"]["summer"] = None
        inp = dict(acquisition_requests=dict(terrain=dict(bounds=bounds)))
        request = next(i for i in plan(config, inp)[0] if i["key"] == "summer")
        q = dict(
            where="1=1",
            geometry="449000,4199000,452000,4202000",
            geometryType="esriGeometryEnvelope",
            inSR=32613,
            outSR=4326,
            spatialRel="esriSpatialRelIntersects",
            outFields="*",
            f="geojson",
        )
        entry = dict(self.entry, url=CPW + "/99/query?" + urlencode(q))
        self.assertTrue(compatible("summer", entry, request, bounds, 32613))
        q["geometry"] = "450000,4200000,450100,4200100"
        entry["url"] = CPW + "/99/query?" + urlencode(q)
        self.assertFalse(compatible("summer", entry, request, bounds, 32613))
        q["geometry"] = "449000,4199000,452000,4202000"
        path = self.donor.parent / "summer.geojson"
        entry["url"] = CPW + "/99/query?" + urlencode(q)
        path.write_text(
            '{"type":"FeatureCollection","features":[],"exceededTransferLimit":true}'
        )
        entry["sha256"] = digest(path)
        write(path.parent / "manifest.json", {path.name: entry})
        from huntmaps_gui.source_reuse import cached

        with configured(AppConfig(workspace=self.root, state_dir=self.root / "state")):
            self.assertEqual(cached(config, inp, lambda *_: {}), {})
        path.write_bytes((self.root / "fixture/range.geojson").read_bytes())
        entry["sha256"] = digest(path)
        write(path.parent / "manifest.json", {path.name: entry})
        before = path.parent.stat().st_mtime_ns
        with configured(AppConfig(workspace=self.root, state_dir=self.root / "state")):
            imported = cached(config, inp, lambda *_: {})["summer"]
        self.assertEqual(Path(imported["path"]).read_bytes(), path.read_bytes())
        self.assertEqual(
            path.parent.stat().st_mtime_ns,
            before,
            "Raw donor directories are read-only; validation scratch belongs in GUI state",
        )

    def test_concurrent_imports_publish_one_independent_source(self):
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(
                pool.map(self.prepare, ["parallel-1", "parallel-2", "parallel-3"])
            )
        for result in results:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            len(list((self.root / "state/sources").glob("*/*/manifest.json"))), 1
        )
        self.assertEqual(
            self.donor.read_bytes(),
            (next((self.root / "state/sources").glob("*/*/tree.tif"))).read_bytes(),
        )

    def test_interrupted_copy_is_not_published_and_can_retry(self):
        from huntmaps_gui.source_reuse import import_source

        app = AppConfig(workspace=self.root, state_dir=self.root / "state")
        with configured(app), patch(
            "huntmaps_gui.source_reuse.os.fsync",
            side_effect=InterruptedError("cancelled"),
        ):
            with self.assertRaises(InterruptedError):
                import_source(
                    "tree",
                    self.donor,
                    self.entry,
                    self.donor.parent / "manifest.json",
                    digest(self.donor.parent / "manifest.json"),
                )
        self.assertEqual(
            list((self.root / "state/sources").glob("*/*/manifest.json")), []
        )
        # A killed process can leave unregistered partial bytes; discovery ignores them.
        partial = next((self.root / "state/sources").glob("tree/*")) / ".killed.partial"
        partial.write_bytes(b"partial")
        self.assertEqual(self.prepare().returncode, 0)
        self.assertEqual(partial.read_bytes(), b"partial")

    def test_changed_input_during_validation_is_not_published(self):
        from huntmaps_gui.source_reuse import cached

        config = json.loads(json.dumps(self.config))
        inp = dict(
            acquisition_requests=dict(
                terrain=dict(bounds=[449450, 4199450, 451150, 4201250])
            )
        )
        with configured(
            AppConfig(workspace=self.root, state_dir=self.root / "state")
        ), patch(
            "huntmaps_gui.source_reuse.validate",
            side_effect=lambda *args, **kwargs: self.donor.write_bytes(b"changed"),
        ):
            self.assertEqual(cached(config, inp, lambda *_: {}), {})
        self.assertEqual(
            list((self.root / "state/sources").glob("*/*/manifest.json")), []
        )

    def test_approval_binds_local_bytes_and_original_provenance(self):
        from huntmaps_gui.worker import approval_inventory

        found, _ = self.select()
        descriptor = found["tree"]
        original = approval_inventory(dict(data=dict(tree=descriptor)), {})
        for field in ("sha256", "url", "provider", "retrieved_utc"):
            changed = dict(descriptor, **{field: "changed"})
            self.assertNotEqual(
                original, approval_inventory(dict(data=dict(tree=changed)), {})
            )
        self.assertNotEqual(
            original, approval_inventory(dict(data=dict(tree=self.entry)), {})
        )

    def test_source_path_escape_and_insufficient_storage_do_not_import(self):
        outside = self.root.parent / (self.root.name + "-outside.tif")
        outside.write_bytes(self.donor.read_bytes())
        self.addCleanup(outside.unlink, missing_ok=True)
        self.donor.unlink()
        self.donor.symlink_to(outside)
        self.assertEqual(self.select()[0], {})
        self.donor.unlink()
        self.donor.write_bytes(outside.read_bytes())
        with patch(
            "huntmaps_gui.source_reuse.check_space",
            side_effect=ValueError("Insufficient storage"),
        ):
            with self.assertRaisesRegex(ValueError, "Insufficient storage"):
                self.select()

    def test_remote_approval_requires_refresh_when_local_sources_become_available(self):
        from huntmaps_gui.downloads import baseline_review_signature

        stored = self.root / "donor-held"
        self.donor.parent.parent.rename(stored)
        ident = "c" * 32
        plan = self.root / "state/plans" / (ident + ".json")
        write(
            plan,
            dict(
                id=ident,
                name="review-change",
                area=str(self.root / "fixture/observer.geojson"),
                polygon="1",
                config=str(self.root / "fixture.json"),
                max_download_mb=30,
                prepared=False,
            ),
        )

        def execute(action, signature=None):
            command = [sys.executable, "-m", "huntmaps_gui.worker", action, ident]
            if signature:
                command += ["--review-signature", signature]
            return subprocess.run(
                command, cwd=self.root, env=self.env, capture_output=True, text=True
            )

        self.assertEqual(execute("prepare").returncode, 0)
        before = read_json(plan)
        signature = baseline_review_signature(before)
        stored.rename(self.donor.parent.parent)
        failed = execute("run", signature)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("Prepare again and review", failed.stdout + failed.stderr)
        self.assertFalse(
            (self.root / "results/review-change/analysis/scores.json").exists()
        )
        self.assertEqual(
            read_json(plan)["approval_inventory"], before["approval_inventory"]
        )
        self.assertEqual(execute("prepare").returncode, 0)
        self.assertNotEqual(baseline_review_signature(read_json(plan)), signature)

    def test_changed_copy_during_validation_is_not_published(self):
        from huntmaps_gui.source_reuse import import_source

        def change(path, *args, **kwargs):
            if Path(path).suffix == ".partial":
                Path(path).write_bytes(b"changed copy")

        with configured(
            AppConfig(workspace=self.root, state_dir=self.root / "state")
        ), patch("huntmaps_gui.source_reuse.validate", side_effect=change):
            with self.assertRaisesRegex(ValueError, "Changed local copy"):
                import_source(
                    "tree",
                    self.donor,
                    self.entry,
                    self.donor.parent / "manifest.json",
                    digest(self.donor.parent / "manifest.json"),
                )
        self.assertEqual(
            list((self.root / "state/sources").glob("*/*/manifest.json")), []
        )

    def test_explicit_sources_are_preferred_and_selection_is_deterministic(self):
        original = read_json(self.root / "fixture.json")
        original["data"]["tree"] = dict(self.entry, path=str(self.donor))
        from huntmaps_gui.source_reuse import cached

        inp = dict(
            acquisition_requests=dict(
                terrain=dict(bounds=[449450, 4199450, 451150, 4201250])
            )
        )
        with configured(AppConfig(workspace=self.root, state_dir=self.root / "state")):
            self.assertEqual(cached(original, inp, lambda *_: {}), {})
        a = self.select()[0]["tree"]
        b = self.select()[0]["tree"]
        self.assertEqual(a, b)

    def test_analysis_matches_identical_original_raw_sources(self):
        import numpy as np
        from osgeo import gdal

        reference = json.loads(json.dumps(self.config))
        reference["data"]["tree"] = dict(self.entry, path=str(self.donor))
        for config in (self.config, reference):
            config["search"] = dict(
                version=1,
                recommendation_count=5,
                nearby_radius_m=30,
                tree_threshold_percent=10,
            )
        write(self.root / "fixture.json", self.config)
        write(self.root / "reference.json", reference)
        for name, config in (
            ("imported", "fixture.json"),
            ("reference", "reference.json"),
        ):
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "huntmaps_gui.owner_worker",
                    "run",
                    "--area",
                    "fixture/observer.geojson",
                    "--name",
                    name,
                    "--polygon",
                    "1",
                    "--source-config",
                    config,
                    "--max-download-mb",
                    "30",
                ],
                cwd=self.root,
                env=self.env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        a, b = [
            self.root / "results" / name / "analysis"
            for name in ("imported", "reference")
        ]
        for name in (
            "pool.json",
            "scores.json",
            "leading.json",
            "recommendations.json",
        ):
            self.assertEqual(read_json(a / name), read_json(b / name), name)
        names = sorted(str(p.relative_to(a)) for p in a.rglob("*.tif"))
        self.assertEqual(names, sorted(str(p.relative_to(b)) for p in b.rglob("*.tif")))
        self.assertTrue(any("visibility" in name for name in names))
        for name in names:
            ds_a, ds_b = gdal.Open(str(a / name)), gdal.Open(str(b / name))
            self.assertEqual(ds_a.GetGeoTransform(), ds_b.GetGeoTransform(), name)
            np.testing.assert_array_equal(
                ds_a.ReadAsArray(), ds_b.ReadAsArray(), err_msg=name
            )
