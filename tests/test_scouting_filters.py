import unittest
import tempfile
from pathlib import Path
import numpy as np
from shapely.geometry import LineString
from huntmaps_gui.scouting_filters import terrain_mask, access_evidence, validate
from huntmaps_gui.scouting_network import (
    parse_lines,
    display_network,
    save_network,
    load_networks,
    network_plan,
    acquire,
    covering_networks,
    sampling_networks,
)
from huntmaps_gui.config import AppConfig, configured


class ScoutingFilterTests(unittest.TestCase):
    def test_empty_inventory_cache_reuse_and_sampling_binding(self):
        import json
        from unittest.mock import patch
        from huntmaps_gui.storage import read_json

        bounds = [-107.1, 37.9, -106.9, 38.1]
        with tempfile.TemporaryDirectory() as temp, configured(
            AppConfig(state_dir=Path(temp))
        ):
            empty = b'{"type":"FeatureCollection","features":[]}'
            import io

            fresh = network_plan(bounds, 600)
            nonempty = b'{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"LineString","coordinates":[[-107,38],[-107.01,38.01]]},"properties":{}}]}'
            with patch(
                "urllib.request.urlopen",
                side_effect=[io.BytesIO(empty), io.BytesIO(nonempty)],
            ):
                result = acquire(fresh["id"], 20000000)
            self.assertEqual([len(n["lines"]) for n in result], [0, 1])
            with self.assertRaises(ValueError):
                save_network(empty, ".geojson", "roads", "empty import")
            roads = save_network(
                empty, ".geojson", "roads", "bounded query", coverage=bounds
            )
            trail = save_network(
                b'{"type":"LineString","coordinates":[[-107,38],[-107.01,38.01]]}',
                ".geojson",
                "trails",
                "bounded query",
                coverage=bounds,
            )
            self.assertEqual(
                display_network(
                    read_json(Path(temp) / "networks" / roads["id"] / "network.json")
                )["display_features"],
                [],
            )
            self.assertEqual(len(covering_networks(bounds)), 2)
            plan = network_plan(bounds, 600)
            self.assertEqual(plan["estimated_bytes"], 0)
            with patch(
                "urllib.request.urlopen", side_effect=AssertionError("No redownload")
            ):
                inventories = acquire(plan["id"], 0)
            inventory = dict(networks=inventories, downloaded_bytes=0)
            settings = validate(dict(distance_m=0.5 * 1609.344))
            resolved, sources = sampling_networks(settings, inventory)
            self.assertEqual(settings["network_ids"], [])
            self.assertEqual(len(resolved["network_ids"]), 2)
            lines, _ = load_networks(resolved["network_ids"], 32613)
            self.assertEqual(len(lines), 1)
            from glassing.transfer import project

            point = project(4326, 32613)(-107.005, 38.005)
            self.assertEqual(
                access_evidence(
                    point, lines, np.zeros((1, 1)), (0, 1, 0, 1, 0, -1), settings
                )["status"],
                "qualifies",
            )
            with self.assertRaisesRegex(ValueError, "Select mapped network"):
                sampling_networks(settings)
            with self.assertRaisesRegex(ValueError, "contain no"):
                sampling_networks(dict(settings, network_ids=[roads["id"]]))
            selected, _ = sampling_networks(
                dict(settings, network_ids=[trail["id"]]), inventory
            )
            self.assertEqual(selected["network_ids"], [trail["id"]])
            (Path(temp) / "networks" / trail["id"] / "original.geojson").write_bytes(
                b"changed"
            )
            self.assertNotIn(trail["id"], [n["id"] for n in covering_networks(bounds)])

    def test_worker_binds_reviewed_cached_inventory_before_sampling(self):
        import json
        from unittest.mock import patch
        from huntmaps_gui.storage import write, read_json
        from huntmaps_gui import worker

        with tempfile.TemporaryDirectory() as temp, configured(
            AppConfig(state_dir=Path(temp) / "state", workspace=Path(temp))
        ):
            bbox = [-107.02, 38, -107, 38.02]
            for kind in ("roads", "trails"):
                save_network(
                    b'{"type":"LineString","coordinates":[[-107.01,38.005],[-107.01,38.015]]}',
                    ".geojson",
                    kind,
                    "fixture",
                    coverage=bbox,
                )
            ident = "a" * 32
            p = dict(
                name="fixture",
                area="fixture.geojson",
                polygon="1",
                max_download_mb=600,
                config="fixture-config.json",
                include_network=True,
                access_sampling=validate(dict(distance_m=804.672)),
            )
            path = Path(temp) / "state/plans" / (ident + ".json")
            write(path, p)
            root = Path(temp) / "results/fixture"
            root.mkdir(parents=True)
            area = dict(
                type="Polygon",
                coordinates=[
                    [
                        [-107.015, 38.005],
                        [-107.005, 38.005],
                        [-107.005, 38.015],
                        [-107.015, 38.015],
                        [-107.015, 38.005],
                    ]
                ],
            )

            def prepare(args):
                if args[0] == "prepare":
                    write(
                        root / "download_plan.json", dict(estimated_bytes=0, items=[])
                    )
                    write(root / "observer.geojson", area)
                    write(
                        root / "scouting.json",
                        dict(epsg=32613, observer_polygon="fixture.geojson"),
                    )
                return 0

            with patch.object(worker, "run", side_effect=prepare), patch(
                "sys.argv", ["worker", "prepare", ident]
            ):
                self.assertEqual(worker.main(), 0)
            reviewed = read_json(path)
            self.assertEqual(reviewed["acquisition"]["estimated_bytes"], 0)
            with patch.object(worker, "run", side_effect=prepare), patch(
                "huntmaps_gui.scouting_filters.sampling_exclusion", return_value=None
            ) as sample, patch("sys.argv", ["worker", "run", ident]):
                self.assertEqual(worker.main(), 0)
                self.assertEqual(len(sample.call_args.args[1]["network_ids"]), 2)
            evidence = read_json(root / "observer_sampling.json")
            self.assertEqual(len(evidence["sources"]), 2)
            self.assertEqual(read_json(path)["access_sampling"]["network_ids"], [])

    def test_display_attributes_preserve_sealed_geometry(self):
        import json

        with tempfile.TemporaryDirectory() as temp, configured(
            AppConfig(state_dir=Path(temp))
        ):
            geometry = {
                "type": "MultiLineString",
                "coordinates": [
                    [[-107, 38], [-107.01, 38.01]],
                    [[-107.02, 38], [-107.03, 38.01]],
                ],
            }
            raw = json.dumps(
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "surface_type": "AGG - AGGREGATE",
                        "name": "<script>test</script>",
                        "oper_maint_level": "2 - HIGH CLEARANCE",
                    },
                }
            ).encode()
            value = save_network(raw, ".geojson", "roads", "fixture")
            before = (
                Path(temp) / "networks" / value["id"] / "network.json"
            ).read_bytes()
            display = display_network(json.loads(before))
            self.assertEqual(len(display["display_features"]), 2)
            self.assertTrue(
                all(
                    f["properties"]["subtype"] == "gravel"
                    for f in display["display_features"]
                )
            )
            self.assertEqual(json.dumps(display["lines"]), json.dumps(value["lines"]))
            self.assertEqual(
                before,
                (Path(temp) / "networks" / value["id"] / "network.json").read_bytes(),
            )
            load_networks([value["id"]], 32613)
            for flag, expected in [
                ("N", "nonmotorized"),
                ("Y", "motorized"),
                (None, "unknown"),
            ]:
                raw = json.dumps(
                    {
                        "type": "Feature",
                        "geometry": geometry,
                        "properties": {"terra_motorized": flag},
                    }
                ).encode()
                value = save_network(raw, ".geojson", "trails", "fixture")
                self.assertEqual(
                    display_network(value)["display_features"][0]["properties"][
                        "subtype"
                    ],
                    expected,
                )
            kml = b'<kml><Placemark><name>Fixture</name><ExtendedData><Data name="surface_type"><value>NAT</value></Data></ExtendedData><LineString><coordinates>-107,38 -107.01,38.01</coordinates></LineString></Placemark></kml>'
            value = save_network(kml, ".kml", "roads", "fixture")
            self.assertEqual(
                display_network(value)["display_features"][0]["properties"]["subtype"],
                "natural",
            )

    def test_segment_proximity_units_and_height(self):
        dem = np.tile(np.arange(10), (10, 1)).astype(float) * 10
        gt = (0, 20, 0, 200, 0, -20)
        lines = [LineString([(10, 190), (190, 190)])]
        settings = validate(dict(distance_m=0.5 * 1609.344, height_m=1000 * 0.3048))
        v = access_evidence((110, 110), lines, dem, gt, settings)
        self.assertEqual(v["distance_m"], 80)
        self.assertEqual(v["height_m"], 0)
        self.assertEqual(v["nearest"], [110, 190])
        self.assertEqual(v["status"], "qualifies")
        lines = [LineString([(10, 190), (10, 10)])]
        v = access_evidence((110, 110), lines, dem, gt, dict(settings, height_m=49))
        self.assertEqual(v["height_m"], 50)
        self.assertEqual(v["status"], "excluded")
        self.assertEqual(
            access_evidence((110, 110), [], dem, gt, settings)["status"], "unknown"
        )
        outside = [LineString([(-10, 210), (-10, 10)])]
        self.assertEqual(
            access_evidence((110, 110), outside, dem, gt, settings)["status"], "unknown"
        )

    def test_aspect_flats_bands_unknown(self):
        gt = (0, 20, 0, 200, 0, -20)
        flat = np.zeros((10, 10))
        settings = validate({})
        self.assertTrue(terrain_mask(flat, gt, settings).all())
        self.assertFalse(terrain_mask(flat, gt, dict(settings, aspects=["N"])).any())
        dem = np.tile(np.arange(10), (10, 1)).astype(float) * 20
        self.assertTrue(terrain_mask(dem, gt, dict(settings, aspects=["W"])).all())
        self.assertFalse(terrain_mask(dem, gt, dict(settings, aspects=["E"])).any())
        mask = terrain_mask(
            dem, gt, dict(settings, elevation_m=[40, 60], slope_deg=[40, 50])
        )
        self.assertEqual(mask.sum(), 20)
        dem[0, 0] = np.nan
        self.assertFalse(
            terrain_mask(dem, gt, dict(settings, elevation_m=[0, 200]))[0, 0]
        )

    def test_line_import_formats_and_offline_seal(self):
        geo = b'{"type":"LineString","coordinates":[[-107,38],[-107.01,38.01]]}'
        kml = b"<kml><Placemark><LineString><coordinates>-107,38 -107.01,38.01</coordinates></LineString></Placemark></kml>"
        gpx = b'<gpx><trk><trkseg><trkpt lon="-107" lat="38"/><trkpt lon="-107.01" lat="38.01"/></trkseg></trk></gpx>'
        for data, ext in [(geo, ".geojson"), (kml, ".kml"), (gpx, ".gpx")]:
            self.assertEqual(len(parse_lines(data, ext)), 1)
        with tempfile.TemporaryDirectory() as temp, configured(
            AppConfig(state_dir=Path(temp))
        ):
            v = save_network(geo, ".geojson", "roads", "test fixture")
            lines, sources = load_networks([v["id"]], 32613)
            self.assertEqual(len(lines), 1)
            self.assertEqual(sources[0]["source_date"], "unknown")
            (Path(temp) / "networks" / v["id"] / "original.geojson").write_bytes(
                b"changed"
            )
            with self.assertRaises(ValueError):
                load_networks([v["id"]], 32613)
            with self.assertRaises(ValueError):
                network_plan([-108, 37, -106, 39], 600)
            larger = network_plan([-107, 38, -106.99, 38.01], 2500)
            self.assertEqual(larger["max_download_mb"], 2500)
            with self.assertRaises(ValueError):
                network_plan([-107, 38, -106.99, 38.01], 0)

    def test_reviewed_budget_no_fallback_and_kmz(self):
        import io, zipfile, json
        from unittest.mock import patch
        from huntmaps_gui.scouting_network import acquire

        data = b"<kml><LineString><coordinates>-107,38 -107.01,38.01</coordinates></LineString></kml>"
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as z:
            z.writestr("doc.kml", data)
        self.assertEqual(len(parse_lines(stream.getvalue(), ".kmz")), 1)
        with tempfile.TemporaryDirectory() as temp, configured(
            AppConfig(state_dir=Path(temp))
        ):
            plan = network_plan([-107.02, 38, -107, 38.02], 600)
            with patch("urllib.request.urlopen") as request:
                with self.assertRaisesRegex(ValueError, "budget"):
                    acquire(plan["id"], 19_999_999)
                request.assert_not_called()
            truncated = json.dumps(
                dict(type="FeatureCollection", features=[], exceededTransferLimit=True)
            ).encode()
            with patch(
                "urllib.request.urlopen", return_value=io.BytesIO(truncated)
            ) as request:
                with self.assertRaisesRegex(ValueError, "truncated"):
                    acquire(plan["id"], 600_000_000)
                self.assertEqual(request.call_count, 1)
