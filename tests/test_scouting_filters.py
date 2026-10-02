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
)
from huntmaps_gui.config import AppConfig, configured


class ScoutingFilterTests(unittest.TestCase):
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
            with self.assertRaises(ValueError):
                network_plan([-107, 38, -106.99, 38.01], 1901)

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
