"""Pack lifecycle/window contracts; artificial sources do not establish GMU readiness."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from osgeo import gdal, osr
import numpy as np
from shapely.geometry import box, mapping
from shapely.ops import transform
from glassing.transfer import project
from glassing.acquire import digest
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui.storage import write, read_json
from huntmaps_gui import unit_packs as p


class Packs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="huntmaps-pack-contract-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.config = AppConfig(
            workspace=self.home,
            state_dir=self.home / "state",
            pack_dir=self.home / "packs",
        )
        self.scope = configured(self.config)
        self.scope.__enter__()
        self.addCleanup(self.scope.__exit__, None, None, None)
        self.staging = p.root() / "preparing/test-v1"
        self.staging.mkdir(parents=True)
        self.area = transform(
            project(32613, 4326), box(300000, 4280000, 300400, 4280400)
        )
        boundary = transform(
            project(32613, 4326), box(299000, 4279000, 302000, 4282000)
        )
        write(
            self.staging / "boundary.geojson",
            dict(
                type="FeatureCollection",
                features=[
                    dict(type="Feature", properties={}, geometry=mapping(boundary))
                ],
            ),
        )
        write(
            self.staging / "context.geojson",
            dict(type="FeatureCollection", features=[]),
        )
        self.manifest = dict(
            contract=1,
            status="ready",
            unit_id="test",
            version="v1",
            label="Test fixture",
            state="test",
            gmu=0,
            epsg=32613,
            created_utc="test",
            boundary="boundary.geojson",
            context="context.geojson",
            bounds=list(boundary.bounds),
            detail={},
            support=dict(
                bounds=[285000, 4265000, 315000, 4295000],
                maximum_visibility_radius_m=3000,
                approach_radius_m=2000,
            ),
            network_provider="test",
            networks={"roads": [], "trails": []},
            assets={},
            data={},
        )
        for k in p.CORE:
            path = self.staging / (
                k + (".geojson" if k in ("summer", "winter") else ".tif")
            )
            if k in ("summer", "winter"):
                write(path, dict(type="FeatureCollection", features=[]))
            else:
                res = 10 if k == "dem" else 30
                ds = gdal.GetDriverByName("GTiff").Create(
                    str(path),
                    30000 // res,
                    30000 // res,
                    1,
                    gdal.GDT_Float32,
                    options=["COMPRESS=DEFLATE", "TILED=YES"],
                )
                sr = osr.SpatialReference()
                sr.ImportFromEPSG(32613)
                ds.SetProjection(sr.ExportToWkt())
                ds.SetGeoTransform((285000, res, 0, 4295000, 0, -res))
                ds.GetRasterBand(1).Fill(2500 if k == "dem" else 25)
                ds.GetRasterBand(1).SetNoDataValue(-9999)
                ds = None
            spec = dict(
                path=path.name,
                bytes=path.stat().st_size,
                sha256=digest(path),
                provider="fixture",
                acquisition_date="fixture",
                license="fixture",
                vertical_units="m",
                vertical_datum="fixture",
            )
            self.manifest["data"][k] = spec
        for path in self.staging.iterdir():
            self.manifest["assets"][path.name] = dict(
                path=path.name, bytes=path.stat().st_size, sha256=digest(path)
            )

    def publish(self):
        return p.publish(self.staging, self.manifest)

    def test_atomic_publication_and_pinned_window(self):
        self.manifest["data"]["tree"][
            "reuse_origin"
        ] = "Immutable prior pack; original bytes differ from this derived window"
        self.assertEqual(p.catalog()["units"], [])
        target = self.publish()
        pin = p.pin("test", "v1")
        config = dict(
            epsg=32613, resolution_m=10, max_cells=3000000, radius_m=500, data={}
        )
        with patch("urllib.request.urlopen", side_effect=AssertionError("offline")):
            p.configure(config, self.area, "test", "v1")
            ids = p.install_networks(pin, self.area)
            self.assertEqual(len(ids), 2)
            for k in ("dem", "tree", "shrub", "herb"):
                ds = gdal.Open(config["data"][k]["path"])
                self.assertLess(ds.RasterXSize, 200)
                self.assertEqual(
                    float(ds.ReadAsArray()[0, 0]), 2500 if k == "dem" else 25
                )
            self.assertNotIn("reuse_origin", config["data"]["tree"])
            self.assertIn(
                "reuse_origin", config["data"]["tree"]["pack_source_provenance"]
            )
            self.assertEqual(
                p.configure(copy.deepcopy(config), self.area, "test", "v1"), pin
            )
        self.assertEqual(config["unit_pack"], pin)
        self.assertEqual(p.load("test")[0], target)

    def test_reject_whole_unit_and_outside_observer(self):
        self.publish()
        pin = p.pin("test", "v1")
        config = dict(resolution_m=10, max_cells=3000000)
        with self.assertRaisesRegex(ValueError, "inside"):
            p.window(
                transform(project(32613, 4326), box(310000, 4280000, 310400, 4280400)),
                500,
                config,
                pin,
            )
        config["max_cells"] = 10
        with self.assertRaisesRegex(ValueError, "smaller"):
            p.window(self.area, 3000, config, pin)

    def test_corrupt_same_size_mtime_and_missing_recovery(self):
        target = self.publish()
        p.load("test")
        asset = target / "context.geojson"
        st = asset.stat()
        data = asset.read_bytes()
        asset.write_bytes(data.replace(b"FeatureCollection", b"FeatureCollectioX"))
        import os

        os.utime(asset, ns=(st.st_atime_ns, st.st_mtime_ns))
        self.assertEqual(p.catalog()["units"][0]["status"], "unavailable")
        asset.write_bytes(data)
        p.load("test")
        asset.unlink()
        with self.assertRaisesRegex(ValueError, "Missing"):
            p.load("test")

    def test_failed_update_keeps_ready_version_and_pin(self):
        self.publish()
        pin = p.pin("test", "v1")
        update = p.root() / "preparing/test-v2"
        update.mkdir()
        write(update / "progress.json", dict(stage="failed", error="interrupted"))
        bad = copy.deepcopy(self.manifest)
        bad["version"] = "v2"
        with self.assertRaises(ValueError):
            p.publish(update, bad)
        self.assertEqual(p.pin("test", "v1"), pin)
        self.assertEqual(p.catalog()["units"][0]["version"], "v1")
        with self.assertRaises(ValueError):
            p.publish(update, dict(bad, status="preparing", assets={}))

    def test_publication_storage_failure_preserves_staging(self):
        with patch(
            "huntmaps_gui.downloads.shutil.disk_usage",
            return_value=type("Disk", (), {"free": 1})(),
        ):
            with self.assertRaisesRegex(ValueError, "20 GiB"):
                self.publish()
        self.assertTrue(self.staging.is_dir())
        self.assertFalse((p.root() / "catalog.json").exists())

    def test_successful_update_and_interrupted_registration(self):
        import shutil

        first = self.publish()
        pin = p.pin("test", "v1")
        before = (first / "pack.json").read_bytes()
        update = p.root() / "preparing/test-v2"
        update.mkdir()
        for spec in self.manifest["assets"].values():
            shutil.copyfile(first / spec["path"], update / spec["path"])
        newer = copy.deepcopy(self.manifest)
        newer["version"] = "v2"
        p.publish(update, newer)
        self.assertEqual(p.catalog()["units"][0]["version"], "v2")
        self.assertEqual(p.resolve(pin)[0], first)
        self.assertEqual((first / "pack.json").read_bytes(), before)
        # Crash after version rename, before pointer publication: explicit version
        # resolution and registration recover without resetting the prior files.
        write(p.root() / "catalog.json", dict(contract=1, units={}))
        self.assertEqual(p.catalog()["units"], [])
        p.register_existing("test", "v2")
        self.assertEqual(p.catalog()["units"][0]["version"], "v2")

    def test_failed_update_progress_cannot_hide_ready_pack(self):
        self.publish()
        update = p.root() / "preparing/invalid"
        update.mkdir()
        (update / "progress.json").write_text("{invalid json")
        value = p.catalog()
        self.assertEqual(value["units"][0]["status"], "ready")
        self.assertEqual(value["preparations"][0]["stage"], "Recovery needed")

    def test_new_unrecorded_raster_companion_rejected(self):
        target = self.publish()
        p.load("test")
        (target / "dem.tif.aux.xml").write_text(
            '<PAMDataset><Metadata><MDI key="test">companion</MDI></Metadata></PAMDataset>'
        )
        with self.assertRaisesRegex(ValueError, "companion"):
            p.load("test")

    def test_sampling_resolves_run_workspace_without_changing_cwd(self):
        from huntmaps_gui.scouting_filters import sampling_exclusion
        from huntmaps_gui.scouting_network import save_network
        import os

        before_cwd = os.getcwd()
        write(
            self.home / "observer.geojson",
            dict(type="Feature", properties={}, geometry=mapping(self.area)),
        )
        line = transform(
            project(32613, 4326),
            __import__("shapely.geometry", fromlist=["LineString"]).LineString(
                [(300050, 4279800), (300050, 4280600)]
            ),
        )
        net = save_network(
            json.dumps(mapping(line)).encode(), ".geojson", "roads", "fixture"
        )
        c = dict(
            observer_polygon="observer.geojson",
            epsg=32613,
            resolution_m=10,
            max_cells=3000000,
            data={
                "dem": dict(
                    self.manifest["data"]["dem"],
                    path=str((self.staging / "dem.tif").relative_to(self.home)),
                )
            },
        )
        original = copy.deepcopy(c)
        excluded = sampling_exclusion(
            c,
            dict(network_ids=[net["id"]], distance_m=100, kinds=["roads"]),
            self.home / "exclusions.geojson",
        )
        self.assertTrue(Path(excluded).is_file())
        self.assertEqual(c, original)
        self.assertEqual(os.getcwd(), before_cwd)

    def test_approach_exports_keep_pack_identity_and_exact_coordinates(self):
        from huntmaps_gui import approach_service
        import xml.etree.ElementTree as ET

        self.publish()
        pin = p.pin("test", "v1")
        position = [-107.1, 38.6]
        line = [[-107.101, 38.601], position]
        value = dict(
            stale=False,
            point_stale={},
            scenario={"unit_pack": pin},
            results={
                "results": [
                    dict(
                        point=dict(
                            id="A1", longitude=position[0], latitude=position[1]
                        ),
                        alternatives=[dict(mapped=line, offtrail=line)],
                    )
                ]
            },
        )
        with patch.object(approach_service, "status", return_value=value):
            geo = json.loads(approach_service.export("unused", 0, 0, "geojson", None))
            gpx = ET.fromstring(approach_service.export("unused", 0, 0, "gpx", None))
        self.assertEqual(geo["properties"]["unit_pack"], pin)
        self.assertEqual(geo["features"][0]["geometry"]["coordinates"], line)
        self.assertIn(pin["manifest_sha256"], gpx.find(".//{*}metadata/{*}desc").text)
        waypoint = gpx.find(".//{*}wpt")
        self.assertEqual(
            [float(waypoint.attrib["lon"]), float(waypoint.attrib["lat"])], position
        )

    def test_malformed_control_records_report_recovery_without_reset(self):
        target = self.publish()
        seal = target / "seal.json"
        original = seal.read_bytes()
        for invalid in (None, [], {}, {"bytes": "bad", "sha256": "bad"}):
            with self.subTest(seal=invalid):
                if invalid is None:
                    seal.unlink()
                else:
                    write(seal, invalid)
                with self.assertRaisesRegex(ValueError, "restore|Restore"):
                    p.load("test", "v1")
                self.assertEqual(p.catalog()["units"][0]["status"], "unavailable")
                seal.write_bytes(original)
        catalog = p.root() / "catalog.json"
        prior = catalog.read_bytes()
        for invalid in ([], {}, dict(contract=1, units=[])):
            write(catalog, invalid)
            with self.assertRaisesRegex(ValueError, "restore"):
                p.catalog()
            self.assertEqual(p.load("test", "v1")[0], target)
            self.assertEqual(read_json(catalog), invalid)
        catalog.write_bytes(prior)

    def test_transfer_cancel_retry_and_corruption(self):
        from huntmaps_gui.pack_builder import Transfer

        t = Transfer(self.staging, budget=1000)

        class Response:
            headers = {"Content-Length": "2"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, n):
                raise KeyboardInterrupt("cancelled")

        with patch("urllib.request.urlopen", return_value=Response()):
            with self.assertRaises(KeyboardInterrupt):
                t.fetch("piece.json", "https://example.invalid", 20)
        self.assertTrue((self.staging / "piece.json.partial").exists())
        import io

        class Complete(io.BytesIO):
            headers = {"Content-Length": "2"}

        with patch("urllib.request.urlopen", return_value=Complete(b"{}")):
            path = t.fetch("piece.json", "https://example.invalid", 20)
        self.assertEqual(t.ledger["received_bytes"], 2)
        self.assertEqual(path.read_bytes(), b"{}")
        self.assertTrue(list(self.staging.glob("*.retained-*")))
        path.write_bytes(b"[]")
        with self.assertRaisesRegex(ValueError, "Changed source"):
            t.fetch("piece.json", "https://example.invalid", 20)


if __name__ == "__main__":
    unittest.main()
