"""Guided source/data boundaries, exact units and corruption checks; disposable state."""

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui.requests import Preparation
from huntmaps_gui import scene_sources, scouting_network as network, browsing


class GuidedSources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="guided-sources-")
        self.addCleanup(self.temp.cleanup)
        self.config = AppConfig(
            state_dir=Path(self.temp.name) / "state", workspace=Path(self.temp.name)
        )
        self.environment = patch.dict(os.environ, {"HUNTMAPS_DISABLE_BROWSING": "0"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.context = configured(self.config)
        self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)

    def test_yard_presets_and_legacy_values_are_exact(self):
        for yard in [500, 1000, 1500, 2000, 2500, 3000]:
            for radius in [yard, yard * 0.9144]:
                self.assertEqual(
                    Preparation(
                        name="test", import_id="a" * 32, polygon="all", radius_m=radius
                    ).radius_m,
                    radius,
                )
        for invalid in [0, 400, 777, 3001, float("nan")]:
            with self.assertRaises(ValueError):
                Preparation(
                    name="test", import_id="a" * 32, polygon="all", radius_m=invalid
                )

    def test_verified_network_cache_detects_source_and_metadata_replacement(self):
        source = network.save_network(
            json.dumps(
                dict(type="LineString", coordinates=[[-108, 38], [-108.01, 38.01]])
            ).encode(),
            ".geojson",
            "trails",
            "fixture",
        )
        with patch.object(network, "parse_lines", wraps=network.parse_lines) as parse:
            a = network.load_networks([source["id"]], 32613)
            self.assertEqual(network.load_networks([source["id"]], 32613), a)
            self.assertEqual(parse.call_count, 1)
            metadata = (
                self.config.state_dir / "networks" / source["id"] / "network.json"
            )
            value = json.loads(metadata.read_text())
            value["source_date"] = "2026-01-01"
            metadata.write_text(json.dumps(value))
            self.assertEqual(
                network.load_networks([source["id"]], 32613)[1][0]["source_date"],
                "2026-01-01",
            )
            self.assertEqual(parse.call_count, 2)
        original = next(metadata.parent.glob("original.*"))
        st = original.stat()
        raw = original.read_bytes()
        original.write_bytes(raw.replace(b"108", b"109"))
        os.utime(original, ns=(st.st_atime_ns, st.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, "source changed"):
            network.load_networks([source["id"]], 32613)

    def test_deterministic_single_acquisition_prefers_verified_cache_then_coverage_date_size_id(
        self,
    ):
        def source(name, date="2020-01-01", cached=False, size=100, bounds=None):
            return dict(
                acquisition=name,
                acquisition_date=date,
                cached=cached,
                bytes=size,
                bounds=bounds or dict(minX=0, minY=0, maxX=2, maxY=2),
            )

        bounds = [[0, 0, 2, 2]]
        self.assertEqual(
            scene_sources.choose_acquisition(
                [source("new", "2026-01-01"), source("cached", cached=True)], bounds
            ),
            "cached",
        )
        self.assertEqual(
            scene_sources.choose_acquisition(
                [source("old"), source("new", "2026-01-01")], bounds
            ),
            "new",
        )
        self.assertEqual(
            scene_sources.choose_acquisition(
                [source("large", size=200), source("small", size=10)], bounds
            ),
            "small",
        )
        self.assertEqual(
            scene_sources.choose_acquisition([source("b"), source("a")], bounds), "a"
        )
        self.assertIsNone(scene_sources.choose_acquisition([], bounds))

    def test_dated_imagery_is_bounded_and_unavailable_detail_remains_explicit(self):
        run = SimpleNamespace(
            points={"X": dict(x=300000, y=4200000)}, config=dict(epsg=32613), images=[]
        )
        rows = dict(
            features=[
                dict(
                    attributes=dict(
                        OBJECTID=10,
                        Year=2020,
                        acquisition_date=1600000000000,
                        Resolution=0.6,
                    )
                ),
                dict(
                    attributes=dict(
                        OBJECTID=9, Year=2018, acquisition_date=1500000000000
                    )
                ),
            ]
        )
        with patch.object(scene_sources, "metadata", return_value=rows):
            sources = scene_sources.imagery_plan(run, ["X"], 914.4)
        self.assertEqual(len(sources), 2)
        self.assertTrue(
            all(
                s["object_ids"] == [10] and s["dates"] == ["2020-09-13"]
                for s in sources
            )
        )
        self.assertLess(sum(s["bytes"] for s in sources), 30_000_000)
        self.assertEqual(
            sources[1]["bounds"], [299085.6, 4199085.6, 300914.4, 4200914.4]
        )
        with patch.object(scene_sources, "metadata", return_value={"features": []}):
            self.assertEqual(scene_sources.imagery_plan(run, ["X"], 914.4), [])
        self.assertIsNone(scene_sources.acquire_imagery(sources[0], False))

    def test_actual_yard_radius_owner_worker_preserves_exact_radius_and_frozen_engine(
        self,
    ):
        import shutil, subprocess, sys

        root = Path(__file__).resolve().parents[1]
        workspace = Path(self.temp.name) / "yard-workspace"
        workspace.mkdir()
        for folder in ("glassing", "configs"):
            shutil.copytree(
                root / folder,
                workspace / folder,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        env = dict(
            os.environ,
            PYTHONPATH=str(root),
            HUNTMAPS_WORKSPACE=str(workspace),
            HUNTMAPS_STATE_DIR=str(workspace / "state"),
            HUNTMAPS_SOURCE_DIR=str(root),
            PYTHONDONTWRITEBYTECODE="1",
        )

        def run(*args):
            result = __import__("subprocess").run(
                [sys.executable, *args],
                cwd=workspace,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        run(
            "-c",
            "from glassing.transfer_fixture import create;create('fixture.json','fixture')",
        )
        config_path = workspace / "fixture.json"
        config = json.loads(config_path.read_text())
        config.update(normal_scouting=True, radius_m=457.2)
        config["search"] = dict(
            version=1,
            ranking_version=2,
            target_filters={},
            avoid_dense_vegetation=False,
            recommendation_count=5,
            nearby_radius_m=30,
            tree_threshold_percent=10,
        )
        config_path.write_text(json.dumps(config))
        run(
            "-m",
            "huntmaps_gui.owner_worker",
            "run",
            "--area",
            "fixture/observer.geojson",
            "--source-config",
            "fixture.json",
            "--name",
            "yards",
        )
        saved = json.loads((workspace / "results/yards/scouting.json").read_text())
        self.assertEqual(saved["radius_m"], 457.2)
        analysis = workspace / "results/yards/analysis"
        self.assertTrue(list((analysis / "additional_visibility").glob("*_457.2.tif")))
        self.assertEqual(
            (root / "glassing/transfer.py").read_bytes(),
            (workspace / "glassing/transfer.py").read_bytes(),
        )

    def test_best_available_provider_failure_keeps_approvable_terrain_plan(self):
        from huntmaps_gui import first_person_worker as worker, first_person as fp

        plan = dict(
            id="c" * 32,
            run_id="test",
            candidates=["X"],
            fidelity="best",
            snapshots={},
            download_cap_bytes=10_000_000,
            context_version=2,
        )
        run = SimpleNamespace(config=dict(radius_m=914.4))
        with patch.object(fp, "plan", return_value=plan), patch.object(
            fp, "scene_run", return_value=run
        ), patch.object(
            worker, "geographic_box", return_value=[0, 0, 1, 1]
        ), patch.object(
            worker, "read", return_value={}
        ), patch.object(
            worker.urllib.request, "urlopen", side_effect=OSError("offline")
        ), patch.object(
            scene_sources, "imagery_plan", side_effect=OSError("offline imagery")
        ):
            worker.discover(plan["id"])
        self.assertTrue(plan["prepared"])
        self.assertFalse(plan["needs_acquisition_selection"])
        self.assertEqual(plan["estimated_new_bytes"], 0)
        self.assertEqual(plan["sources"], [])
        self.assertEqual(plan["errors"], [])
        self.assertIn("offline imagery", plan["source_note"])
        self.assertTrue(plan["review_signature"])

    def test_imagery_acquisition_coverage_cache_and_actual_transfer_accounting(self):
        from osgeo import gdal, osr
        from huntmaps_gui import first_person as fp

        source_path = Path(self.temp.name) / "rgb.tif"
        ds = gdal.GetDriverByName("GTiff").Create(
            str(source_path), 2, 2, 3, gdal.GDT_Byte
        )
        ds.SetGeoTransform((100, 1, 0, 200, 0, -1))
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(32613)
        ds.SetProjection(srs.ExportToWkt())
        ds = None
        raw = source_path.read_bytes()
        source = dict(
            key="clip",
            url=scene_sources.NAIP + "/exportImage",
            bytes=len(raw) + 100,
            pixels=2,
            epsg=32613,
            bounds=[100, 198, 102, 200],
            dates=["2020-01-01"],
            cached=False,
        )
        response = io.BytesIO(raw)
        response.url = source["url"]
        with patch.object(
            scene_sources.urllib.request, "urlopen", return_value=response
        ), patch.object(fp, "LIMIT", len(raw) + 100):
            image = scene_sources.acquire_imagery(source, True)
        self.assertEqual(image["downloaded_bytes"], len(raw))
        self.assertEqual(
            json.loads((fp.HOME / "sources/ledger.json").read_text())["received_bytes"],
            len(raw),
        )
        with patch.object(
            scene_sources.urllib.request,
            "urlopen",
            side_effect=AssertionError("cache must be offline"),
        ):
            self.assertEqual(
                scene_sources.acquire_imagery(dict(image, cached=True), True)["sha256"],
                image["sha256"],
            )
        Path(image["path"]).write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            scene_sources.acquire_imagery(dict(image, cached=True), True)

    def test_browsing_context_is_cached_without_analysis_inventory_or_allowance(self):
        data = io.BytesIO()
        Image.new("RGBA", (256, 256)).save(data, format="PNG")
        with patch.object(
            browsing.urllib.request, "urlopen", return_value=io.BytesIO(data.getvalue())
        ) as fetch:
            self.assertEqual(browsing.transportation(10, 123, 456), data.getvalue())
            self.assertEqual(browsing.transportation(10, 123, 456), data.getvalue())
            self.assertEqual(fetch.call_count, 1)
        self.assertFalse((self.config.state_dir / "networks").exists())
        self.assertFalse((self.config.state_dir / "plans").exists())
        self.assertFalse((self.config.state_dir / "network-plans").exists())
        with self.assertRaises(ValueError):
            browsing.transportation(17, 1, 1)
        with patch.object(
            browsing.urllib.request, "urlopen", side_effect=OSError("offline")
        ):
            with self.assertRaises(OSError):
                browsing.transportation(10, 124, 456)
