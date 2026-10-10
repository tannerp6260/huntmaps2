"""Provider errors must never become reusable source files."""

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from glassing.acquire import Fetcher, digest
from huntmaps_gui.acquisition import validating
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui.owner_worker import get
from huntmaps_gui.storage import read_json, write

XML_ERROR = b"""<?xml version="1.0"?><ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows">
<ows:Exception><ows:ExceptionText>Could not understand version:1.0.0</ows:ExceptionText>
</ows:Exception></ows:ExceptionReport>"""


class Response(io.BytesIO):
    def __init__(self, content):
        super().__init__(content)
        self.headers = {
            "Content-Length": str(len(content)),
            "Content-Type": "image/tiff",
        }


class AcquisitionValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="huntmaps-acquisition-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = self.root / "sources"
        self.fetcher = Fetcher(self.sources, 1_000_000)
        self.ledger = self.root / "ledger.json"
        write(self.ledger, dict(received_bytes=0, ceiling_bytes=1_000_000))
        env = patch.dict(
            os.environ,
            HUNTMAPS_PROGRESS_FILE="",
            HUNTMAPS_TRANSFER_LEDGER=str(self.ledger),
        )
        env.start()
        self.addCleanup(env.stop)
        context = configured(
            AppConfig(state_dir=self.root / "state", workspace=self.root)
        )
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def raster(self, value=20):
        from osgeo import gdal, osr

        path = self.root / "good.tif"
        ds = gdal.GetDriverByName("GTiff").Create(str(path), 4, 4, 1, gdal.GDT_Byte)
        sr = osr.SpatialReference()
        sr.ImportFromEPSG(32613)
        ds.SetProjection(sr.ExportToWkt())
        ds.SetGeoTransform((300000, 30, 0, 4282000, 0, -30))
        ds.GetRasterBand(1).Fill(value)
        ds = None
        return path.read_bytes()

    def fetch(self, body, name="tree_padded120.tif"):
        with patch("urllib.request.urlopen", return_value=Response(body)):
            return get(
                self.fetcher,
                name,
                "https://example.test/" + name,
                provider="USGS RCMAP",
            )

    def test_rejected_retry_then_valid_and_cached_has_exact_bytes_and_accounting(self):
        with self.assertRaisesRegex(ValueError, "returned an error"):
            self.fetch(XML_ERROR)
        valid = self.raster()
        path = self.fetch(valid)
        self.assertEqual(path.read_bytes(), valid)
        self.assertEqual(
            read_json(self.ledger)["received_bytes"], len(valid) + len(XML_ERROR)
        )
        with patch(
            "urllib.request.urlopen",
            side_effect=AssertionError("cached source downloaded again"),
        ):
            cached = get(
                self.fetcher,
                path.name,
                "https://example.test/" + path.name,
                provider="USGS RCMAP",
            )
        self.assertEqual(cached.read_bytes(), valid)
        self.assertEqual(
            read_json(self.ledger)["received_bytes"], len(valid) + len(XML_ERROR)
        )

    def test_legacy_cached_error_is_retained_and_reacquired(self):
        path = self.sources / "tree_padded120.tif"
        path.write_bytes(XML_ERROR)
        entry = dict(
            url="https://example.test/" + path.name,
            sha256=digest(path),
            bytes=len(XML_ERROR),
            provider="USGS RCMAP",
        )
        write(self.fetcher.manifest_path, {path.name: entry})
        before = self.raster()
        self.assertEqual(self.fetch(before).read_bytes(), before)
        records = list((self.sources / "rejected").glob("*/metadata.json"))
        self.assertEqual(len(records), 1)
        self.assertEqual(read_json(records[0])["source"], entry)
        self.assertEqual((records[0].parent / "response.tif").read_bytes(), XML_ERROR)
        self.assertEqual(read_json(self.ledger)["received_bytes"], len(before))

    def test_changed_cache_or_request_is_preserved_without_transfer(self):
        path = self.fetch(self.raster())
        entry = read_json(self.fetcher.manifest_path)
        path.write_bytes(b"tampered file")
        with patch(
            "urllib.request.urlopen", side_effect=AssertionError("unexpected download")
        ):
            with self.assertRaisesRegex(ValueError, "Unverified or changed input"):
                get(self.fetcher, path.name, entry[path.name]["url"])
        self.assertEqual(path.read_bytes(), b"tampered file")
        self.assertEqual(read_json(self.fetcher.manifest_path), entry)
        path.write_bytes(self.raster())
        with patch(
            "urllib.request.urlopen", side_effect=AssertionError("unexpected download")
        ):
            with self.assertRaisesRegex(ValueError, "Unverified or changed input"):
                get(self.fetcher, path.name, "https://changed.test/tree")
        self.assertFalse((self.sources / "rejected").exists())

    def test_unreadable_raster_and_geojson_errors_are_not_cached(self):
        for name, content in [
            ("shrub.tif", b"not a raster"),
            ("summer.geojson", b'{"error":{"message":"provider unavailable"}}'),
            (
                "winter.geojson",
                b'{"type":"FeatureCollection","features":[],"exceededTransferLimit":true}',
            ),
        ]:
            with self.subTest(name=name), self.assertRaisesRegex(
                ValueError, "returned"
            ):
                self.fetch(content, name)
            self.assertFalse((self.sources / name).exists())
            self.assertNotIn(name, read_json(self.fetcher.manifest_path, {}))

    def test_raster_extent_and_unknown_vegetation_follow_existing_checks(self):
        config = dict(epsg=32613, resolution_m=10)
        inputs = dict(
            acquisition_requests=dict(
                terrain=dict(bounds=[300000, 4281900, 300100, 4282000])
            )
        )
        with validating(config, inputs):
            path = self.fetch(self.raster())
            self.assertTrue(path.exists())
            unknown = self.fetch(self.raster(255), "herb.tif")
            from glassing.owner_data import coverage

            diagnostic = coverage(
                unknown, [300000, 4281900, 300100, 4282000], 32613, vegetation=True
            )
            self.assertEqual(diagnostic["unknown_fraction"], 1)
        inputs["acquisition_requests"]["terrain"]["bounds"] = [
            400000,
            4281900,
            400100,
            4282000,
        ]
        with validating(config, inputs), self.assertRaisesRegex(
            ValueError, "insufficient raster coverage"
        ):
            self.fetch(self.raster(), "shrub.tif")
        self.assertFalse((self.sources / "shrub.tif").exists())

    def test_truncated_raster_blocks_are_not_accepted(self):
        with self.assertRaisesRegex(ValueError, "invalid GeoTIFF"):
            self.fetch(self.raster()[:-10])
        self.assertFalse((self.sources / "tree_padded120.tif").exists())

    def test_cache_change_during_validation_stops_without_recovery(self):
        from huntmaps_gui.acquisition import ProviderResponseError

        path = self.fetch(self.raster())
        entry = read_json(self.fetcher.manifest_path)
        original = path.read_bytes()
        for raises in (False, True):
            path.write_bytes(original)

            def changed(*args):
                path.write_bytes(b"changed during validation")
                if raises:
                    raise ProviderResponseError("invalid response")

            with patch(
                "huntmaps_gui.owner_worker.validate", side_effect=changed
            ), patch(
                "urllib.request.urlopen",
                side_effect=AssertionError("stale source was reacquired"),
            ):
                with self.assertRaisesRegex(
                    ValueError, "Changed input during source validation"
                ):
                    get(self.fetcher, path.name, entry[path.name]["url"])
            self.assertEqual(read_json(self.fetcher.manifest_path), entry)
            self.assertFalse((self.sources / "rejected").exists())

    def test_actual_sampling_worker_recovers_from_legacy_provider_error(self):
        """Real jobs/worker/owner/sampling; a local provider changes from XML to TIFF."""
        import functools
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
        import shutil
        import subprocess
        import sys
        import threading
        import time

        from huntmaps_gui.downloads import baseline_review_signature
        from huntmaps_gui.jobs import Jobs, ACTIVE
        from huntmaps_gui.scouting_network import save_network

        project = Path(__file__).resolve().parents[1]
        root = self.root / "workspace"
        root.mkdir()
        for name in ["glassing", "configs", "docs", "huntmaps_gui"]:
            (root / name).symlink_to(project / name, target_is_directory=True)
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from glassing.transfer_fixture import create;create('fixture.json','fixture',32613)",
            ],
            cwd=root,
            env=dict(os.environ, PYTHONPATH=str(project)),
            check=True,
            capture_output=True,
        )
        config = read_json(root / "fixture.json")
        config.update(
            normal_scouting=True, candidate_count=24, spacing_m=150, radius_m=500
        )
        config["data"]["tree"] = None
        config["search"] = dict(
            version=1,
            recommendation_count=5,
            nearby_radius_m=30,
            tree_threshold_percent=10,
        )
        write(root / "fixture.json", config)
        (root / "fixture/provider.tif").write_bytes(XML_ERROR)

        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        http = ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Quiet, directory=str(root / "fixture"))
        )
        threading.Thread(target=http.serve_forever, daemon=True).start()
        self.addCleanup(http.server_close)
        self.addCleanup(http.shutdown)
        (root / "sitecustomize.py").write_text(
            f"""import urllib.request
original=urllib.request.urlopen
def routed(request,*args,**kwargs):
 url=request.full_url if hasattr(request,'full_url') else str(request)
 if 'geoserver/mrlc_tree' in url:
  request='http://127.0.0.1:{http.server_port}/provider.tif'
 elif not url.startswith('http://127.0.0.1:'):
  raise AssertionError('Unexpected external request: '+url)
 return original(request,*args,**kwargs)
urllib.request.urlopen=routed
"""
        )
        app = AppConfig(source_dir=root, state_dir=root / "state", workspace=root)
        ident = "a" * 32
        plan_path = app.state_dir / "plans" / (ident + ".json")
        with configured(app), patch.dict(
            os.environ, PYTHONPATH=str(root) + os.pathsep + str(project)
        ):
            from glassing.transfer import project as reproject
            from shapely.geometry import LineString, mapping
            from shapely.ops import transform
            from huntmaps_gui.scouting_filters import validate

            network = save_network(
                json.dumps(
                    mapping(
                        transform(
                            reproject(32613, 4326),
                            LineString([(450000, 4200000), (450500, 4200500)]),
                        )
                    )
                ).encode(),
                ".geojson",
                "roads",
                "Synthetic recovery fixture",
            )
            sampling = validate(dict(network_ids=[network["id"]], distance_m=100000))
            write(
                plan_path,
                dict(
                    id=ident,
                    name="acquisition-recovery",
                    area=str(root / "fixture/observer.geojson"),
                    polygon="1",
                    config=str(root / "fixture.json"),
                    max_download_mb=30,
                    prepared=False,
                    access_sampling=sampling,
                ),
            )
            jobs = Jobs()
            self.addCleanup(jobs.shutdown)

            def execute(action, signature=None):
                command = [
                    sys.executable,
                    "-u",
                    "-m",
                    "huntmaps_gui.worker",
                    action,
                    ident,
                ]
                if signature:
                    command += ["--download", "--review-signature", signature]
                job = jobs.start(
                    command,
                    "prepare" if action == "prepare" else "baseline",
                    name="acquisition-recovery",
                    plan=ident,
                )
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    record = next(j for j in jobs.list() if j["id"] == job["id"])
                    if record["status"] not in ACTIVE:
                        return record
                    time.sleep(0.05)
                self.fail("Recovery worker timed out")

            prepared = execute("prepare")
            self.assertEqual(prepared["status"], "complete", prepared.get("logs"))
            signature = baseline_review_signature(read_json(plan_path))
            result = root / "results/acquisition-recovery"
            downloads = result / "downloads"
            downloads.mkdir()
            tree = downloads / "tree_padded120.tif"
            tree.write_bytes(XML_ERROR)
            url = read_json(result / "download_plan.json")["items"][0]["url"]
            write(
                downloads / "manifest.json",
                {tree.name: dict(url=url, sha256=digest(tree), bytes=len(XML_ERROR))},
            )
            dem_path = root / config["data"]["dem"]["path"]
            dem_hash = digest(dem_path)
            failed = execute("run", signature)
            self.assertEqual(failed["status"], "failed", failed.get("logs"))
            self.assertEqual(
                failed["failure_code"], "provider_failed", failed.get("logs")
            )
            self.assertIn("tree-cover service", failed["failed_stage"])
            self.assertIn("Could not understand version", failed["error"])
            self.assertNotIn("Could not prepare approved DEM", failed["error"])
            self.assertFalse(tree.exists())
            self.assertNotIn(tree.name, read_json(downloads / "manifest.json"))
            self.assertEqual(
                len(list((downloads / "rejected").glob("*/metadata.json"))), 2
            )
            self.assertEqual(signature, baseline_review_signature(read_json(plan_path)))
            ledger_path = app.state_dir / "plans" / (ident + "-transfer.json")
            self.assertEqual(
                read_json(ledger_path)["received_bytes"], 2 * len(XML_ERROR)
            )
            dem_bytes = dem_path.read_bytes()
            dem_path.write_bytes(b"corrupt checked DEM")
            corrupt = execute("run", signature)
            self.assertEqual(corrupt["status"], "failed", corrupt.get("logs"))
            self.assertEqual(
                corrupt["failure_code"], "source_invalid", corrupt.get("logs")
            )
            self.assertIn("checksum", corrupt["error"].lower())
            self.assertNotIn("Could not understand version", corrupt["error"])
            self.assertEqual(
                read_json(ledger_path)["received_bytes"], 2 * len(XML_ERROR)
            )
            dem_path.write_bytes(dem_bytes)
            shutil.copy2(root / "fixture/tree.tif", root / "fixture/provider.tif")
            recovered = execute("run", signature)
            self.assertEqual(recovered["status"], "complete", recovered.get("logs"))
            self.assertEqual(digest(tree), digest(root / "fixture/tree.tif"))
            self.assertEqual(digest(dem_path), dem_hash)
            self.assertEqual(
                read_json(ledger_path)["received_bytes"],
                2 * len(XML_ERROR) + tree.stat().st_size,
            )
            self.assertEqual(signature, baseline_review_signature(read_json(plan_path)))
            self.assertTrue((result / "observer_sampling.json").exists())
            self.assertTrue((result / "manifest.json").exists())

    def test_http_error_body_is_retained_and_charged(self):
        from urllib.error import HTTPError

        error = HTTPError(
            "https://example.test/tree", 503, "Unavailable", {}, io.BytesIO(XML_ERROR)
        )
        with patch("urllib.request.urlopen", side_effect=error), self.assertRaisesRegex(
            ValueError, "returned an error"
        ):
            get(
                self.fetcher,
                "tree.tif",
                "https://example.test/tree",
                provider="USGS RCMAP",
            )
        self.assertFalse((self.sources / "tree.tif").exists())
        self.assertEqual(read_json(self.ledger)["received_bytes"], len(XML_ERROR))

    def test_transfer_ceiling_retains_partial_and_never_accepts_source(self):
        write(self.ledger, dict(received_bytes=999_999, ceiling_bytes=1_000_000))
        with self.assertRaisesRegex(ValueError, "Cumulative download allowance"):
            self.fetch(XML_ERROR)
        self.assertTrue((self.sources / "tree_padded120.tif.partial").exists())
        self.assertFalse((self.sources / "tree_padded120.tif").exists())
        self.assertEqual(
            read_json(self.ledger)["received_bytes"], 999_999 + len(XML_ERROR)
        )

    def test_concurrent_fetches_publish_once_and_keep_both_manifest_entries(self):
        from concurrent.futures import ThreadPoolExecutor

        first, second = Fetcher(self.sources, 1_000_000), Fetcher(
            self.sources, 1_000_000
        )
        content = self.raster()
        with patch(
            "urllib.request.urlopen", side_effect=lambda *args, **kw: Response(content)
        ) as opened:
            with ThreadPoolExecutor(max_workers=2) as pool:
                paths = list(
                    pool.map(
                        lambda f: get(f, "tree.tif", "https://example.test/tree"),
                        [first, second],
                    )
                )
        self.assertEqual(opened.call_count, 1)
        self.assertEqual(paths[0], paths[1])
        third = Fetcher(self.sources, 1_000_000)
        with patch(
            "urllib.request.urlopen", side_effect=lambda *args, **kw: Response(content)
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(
                    pool.map(
                        lambda item: get(
                            item[0], item[1], "https://example.test/" + item[1]
                        ),
                        [(second, "shrub.tif"), (third, "herb.tif")],
                    )
                )
        self.assertEqual(
            set(read_json(first.manifest_path)), {"tree.tif", "shrub.tif", "herb.tif"}
        )

    def test_provider_failure_summary_names_source_and_recovery(self):
        from huntmaps_gui.failures import summarize

        failure = summarize(
            [
                "STAGE Downloading and validating USGS RCMAP tree-cover service",
                "SCOUT: Approved source acquisition failed: tree: USGS RCMAP tree-cover service returned an error: unavailable",
            ]
        )
        self.assertEqual(failure["failure_code"], "provider_failed")
        self.assertEqual(failure["recovery_action"], "retry")
        self.assertIn("tree-cover", failure["error"])
        self.assertIn("reacquired", failure["error"])

    def test_http_200_xml_is_rejected_before_cache_publication(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(
            os.environ, HUNTMAPS_PROGRESS_FILE="", HUNTMAPS_TRANSFER_LEDGER=""
        ):
            fetcher = Fetcher(folder, 1_000_000)
            with patch("urllib.request.urlopen", return_value=Response(XML_ERROR)):
                with self.assertRaisesRegex(
                    ValueError, "tree-cover service returned an error"
                ):
                    get(
                        fetcher,
                        "tree_padded120.tif",
                        "https://example.test/tree",
                        provider="USGS RCMAP",
                    )
            self.assertFalse((Path(folder) / "tree_padded120.tif").exists())
            self.assertNotIn(
                "tree_padded120.tif", read_json(Path(folder) / "manifest.json", {})
            )
            self.assertTrue(
                any(
                    p.read_bytes() == XML_ERROR
                    for p in (Path(folder) / "rejected").glob("*/response*")
                )
            )


if __name__ == "__main__":
    unittest.main()
