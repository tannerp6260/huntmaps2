"""Independent numerical cases. All generated terrain here is a labeled fixture."""

import copy
from datetime import date, datetime
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
from osgeo import gdal, osr
from shapely.geometry import LineString, Point, box

from trail_scout import effort, profiles, schedule, planner
from trail_scout.sources import Terrain, access, date_match, Pack
from trail_scout.network import Network, measured, reverse, starts
from trail_scout.analysis import Spurs, coverage, habitat_layers
from trail_scout.storage import atomic, checked, seal, verify, file_hash
from trail_scout.preparation import validate_geojson


def terrain(a, res=10):
    a = np.asarray(a, dtype=float)
    ds = gdal.GetDriverByName("MEM").Create(
        "", a.shape[1], a.shape[0], 1, gdal.GDT_Float32
    )
    ds.SetGeoTransform((0, res, 0, a.shape[0] * res, 0, -res))
    s = osr.SpatialReference()
    s.ImportFromEPSG(32613)
    ds.SetProjection(s.ExportToWkt())
    ds.GetRasterBand(1).WriteArray(a)
    return Terrain(ds)


def row(id, line, **properties):
    return dict(
        id=id,
        kind="trails",
        geometry=LineString(line),
        properties=dict(hiker_pedestrian_managed="01/01-12/31", **properties),
        motor_closed=False,
        mvum=[],
    )


class Core(unittest.TestCase):
    def setUp(self):
        self.p = profiles.validate({"preset": "tanner"})

    def measure(self, z, spacing=20, p=None, off=False):
        d = np.arange(len(z)) * spacing
        return effort.measure(
            np.column_stack((d, np.zeros(len(d)))),
            z,
            np.full(len(d) - 1, off),
            p or self.p,
        )

    def test_explicit_travel_area_limits_mapped_route_independently_of_target(self):
        t = terrain(np.zeros((80, 80)))
        cover = np.zeros_like(t.a)
        pack = type(
            "SyntheticPack",
            (),
            {
                "network": [row("trail", [(100, 400), (700, 400)])],
                "boundary": box(90, 390, 200, 410),
            },
        )()
        start = dict(x=100, y=400, segment="trail")
        settings = planner.validate(dict(corridor_m=1000))
        unrestricted = Network(pack, start, t, self.p, settings, cover, cover)
        full = measured(
            unrestricted.path(max(unrestricted.dist, key=unrestricted.dist.get)),
            t,
            self.p,
            cover,
            cover,
        )
        self.assertAlmostEqual(full["distance_m"], 600)
        settings["_travel_geometry"] = box(90, 350, 450, 450)
        limited = Network(pack, start, t, self.p, settings, cover, cover)
        clipped = measured(
            limited.path(max(limited.dist, key=limited.dist.get)),
            t,
            self.p,
            cover,
            cover,
        )
        self.assertAlmostEqual(clipped["distance_m"], 350)
        self.assertLess(clipped["distance_m"], full["distance_m"])

    def test_contour_mapped_vs_ground_slope_and_offtrail(self):
        a = np.tile(np.arange(80)[:, None] * 10, (1, 80))
        t = terrain(a)
        cover = np.zeros_like(a, dtype=float)
        pack = type(
            "SyntheticPack", (), {"network": [row("contour", [(100, 400), (700, 400)])]}
        )()
        c = planner.validate(dict(corridor_m=1000, search_envelope_m=300))
        start = dict(x=100, y=400, segment="contour")
        n = Network(pack, start, t, self.p, c, cover, cover)
        path = n.path(max(n.dist, key=n.dist.get))
        m = measured(path, t, self.p, cover, cover)
        self.assertGreater(t.slope[40, 40], 40)
        self.assertLess(m["ascent_m"], 0.01)
        self.assertGreater(m["distance_m"], 500)
        spurs = Spurs(
            n,
            t,
            dict(tree=cover, shrub=cover),
            box(10, 10, 790, 790),
            300,
            lambda: None,
        )
        self.assertFalse(spurs.valid.any())
        self.assertIsNotNone(spurs.path((300, 450))[1])

    def test_repeated_hills_noise_and_short_sustained_climb(self):
        d = np.arange(101) * 20
        gentle = self.measure(np.zeros(101))
        hills = self.measure(
            np.tile(
                np.r_[
                    np.linspace(0, 50, 11), [50] * 3, np.linspace(50, 0, 11), [0] * 3
                ],
                4,
            )
        )
        noise = self.measure(np.sin(d / 8) * 0.4)
        short = self.measure([0, 0, 0, 4, 8, 12, 16, 16, 16, 16, 16])
        self.assertGreater(hills["ascent_m"], 180)
        self.assertGreater(hills["hours_high"], gentle["hours_high"] * 1.15)
        self.assertLess(noise["ascent_m"], 2)
        self.assertGreater(short["longest_climb_m"], 12)
        self.assertTrue(short["steep_sections"])

    def test_downhill_outbound_return_budget_and_direction(self):
        p = profiles.validate({"preset": "dad", "max_gain_ft": 400})
        out = self.measure(np.linspace(200, 0, 101), p=p)
        ret = self.measure(np.linspace(0, 200, 101), p=p)
        self.assertFalse(profiles.failures(out, p))
        self.assertTrue(profiles.failures(effort.add_metrics(out, ret), p))
        self.assertGreater(ret["hours_high"], out["hours_high"])
        self.assertAlmostEqual(ret["ascent_m"], 200)

    def test_far_gentle_open_spur_near_brushy_fails_and_new_search(self):
        a = np.zeros((80, 100))
        t = terrain(a)
        tree = np.zeros_like(a)
        shrub = np.zeros_like(a)
        tree[32:40, 30:40] = 0.9
        pack = type(
            "SyntheticPack", (), {"network": [row("trail", [(100, 400), (700, 400)])]}
        )()
        c = planner.validate(dict(corridor_m=1000, search_envelope_m=300))
        n = Network(
            pack, dict(x=100, y=400, segment="trail"), t, self.p, c, tree, shrub
        )
        spurs = Spurs(
            n, t, dict(tree=tree, shrub=shrub), box(10, 10, 990, 790), 300, lambda: None
        )
        self.assertIsNotNone(spurs.path((350, 450))[1])
        farther, error = spurs.path((350, 600))
        self.assertIsNone(error)
        self.assertTrue(farther[-1]["offtrail"])
        candidates = spurs.candidates(12)
        self.assertTrue(candidates)
        self.assertTrue(
            any(
                Point(p).distance(LineString([(100, 400), (700, 400)])) >= 40
                for p in candidates
            )
        )

    def test_retraced_geometry_and_weighted_union_independent_reference(self):
        t = terrain(np.zeros((80, 100)))
        cover = np.zeros_like(t.a)
        chunks = [
            dict(
                coords=[(100, 400), (300, 400), (300, 500)], offtrail=False, segment="a"
            ),
            dict(coords=[(300, 500), (400, 500)], offtrail=True, segment="b"),
        ]
        out = measured(chunks, t, self.p, cover, cover)
        ret = measured(reverse(chunks), t, self.p, cover, cover)
        m = effort.add_metrics(out, ret)
        self.assertAlmostEqual(m["distance_m"], 800, places=6)
        self.assertAlmostEqual(m["offtrail_m"], 200, places=6)
        self.assertAlmostEqual(m["mapped_m"], 600, places=6)
        a = np.array([[1, 1, 0], [0, 1, 0]], bool)
        b = np.array([[0, 1, 1], [0, 0, 1]], bool)
        h = np.array([[0.2, 0.8, 0.6], [0.7, 0.9, 0.3]])
        g = np.array([[0.9, 0.4, 0.7], [0.5, 0.8, 0.2]])
        layers = dict(h=h, g=g, known=np.ones(a.shape, bool))
        actual, _ = coverage([a, b], layers, np.ones(a.shape, bool), 100)
        expected = sum(
            100 * h[r, c] * g[r, c]
            for r in range(2)
            for c in range(3)
            if a[r, c] or b[r, c]
        )
        self.assertAlmostEqual(actual["effective_m2"], expected, places=10)
        self.assertEqual(actual["matching_m2"], 500)
        with self.assertRaises(ValueError):
            coverage([a, b[:1]], layers, np.ones(a.shape, bool), 100)

    def test_access_dates_motor_foot_and_manual_provenance(self):
        r = row("a", [(0, 0), (1, 0)])
        r["mvum"] = [dict(truck="open", truck_datesopen="05/15-10/31")]
        self.assertEqual(access(r, date(2026, 10, 31))["motor"], "supported")
        self.assertEqual(access(r, date(2026, 11, 1))["motor"], "closed")
        r["motor_closed"] = True
        self.assertEqual(access(r, date(2026, 10, 31))["foot"], "supported")
        self.assertEqual(access(r, date(2026, 10, 31))["motor"], "closed")
        r["properties"]["hiker_pedestrian_restricted"] = "10/20-11/10"
        self.assertEqual(access(r, date(2026, 10, 31))["foot"], "closed")
        r["properties"] = {}
        self.assertEqual(access(r, date(2026, 10, 31))["foot"], "unknown")
        manual = [dict(segment="a", foot="closed", from_="")]
        with self.assertRaises(ValueError):
            access(r, date(2026, 10, 31), manual=manual)
        self.assertNotEqual(
            planner.validate({"date": "2026-10-31"}),
            planner.validate({"date": "2026-11-01"}),
        )
        self.assertTrue(date_match("11/15-04/30", date(2026, 12, 1)))

    def test_manual_motor_closure_changes_supported_entries(self):
        trail = row("foot", [(100, 400), (700, 400)])
        road = row("road", [(100, 300), (100, 500)])
        road["kind"] = "roads"
        road["mvum"] = [dict(truck="open", truck_datesopen="01/01-12/31")]
        pack = type(
            "SyntheticPack",
            (),
            {"network": [trail, road], "boundary": box(0, 0, 1000, 1000)},
        )()
        self.assertTrue(starts(pack, date(2026, 10, 31)))
        rule = {
            "segment": "road",
            "motor": "closed",
            "from": "2026-10-31",
            "until": "2026-10-31",
            "provenance": "DATED ENGINEERING FIXTURE; not real closure evidence",
        }
        self.assertEqual(starts(pack, date(2026, 10, 31), manual=[rule]), [])
        self.assertTrue(starts(pack, date(2026, 11, 1), manual=[rule]))

    def test_no_crossing_or_near_gap_invented_junctions(self):
        t = terrain(np.zeros((100, 100)))
        cover = np.zeros_like(t.a)
        rows = [
            row("a", [(100, 500), (700, 500)]),
            row("cross", [(400, 200), (400, 800)]),
            row("gap", [(701, 500), (900, 500)]),
            row("overpass", [(700, 500), (700, 900)], layer=1),
        ]
        n = Network(
            type("SyntheticPack", (), {"network": rows})(),
            dict(x=100, y=500, segment="a"),
            t,
            self.p,
            planner.validate(dict(corridor_m=1500)),
            cover,
            cover,
        )
        reachable = [n.nodes[k] for k in n.dist]
        self.assertNotIn((400, 800), reachable)
        self.assertNotIn((900, 500), reachable)
        self.assertNotIn((700, 900), reachable)
        self.assertIn((700, 500), reachable)

    def test_search_seed_counts_directional_retraced_return(self):
        a = np.tile(np.linspace(240, 0, 240), (80, 1))
        t = terrain(a)
        cover = np.zeros_like(t.a)
        pack = type(
            "SyntheticPack",
            (),
            {"network": [row("downhill", [(100, 400), (2100, 400)])]},
        )()
        n = Network(
            pack,
            dict(x=100, y=400, segment="downhill"),
            t,
            self.p,
            planner.validate(dict(corridor_m=2500)),
            cover,
            cover,
        )
        last = max(n.dist, key=n.dist.get)
        self.assertGreater(n.return_cost[last], n.dist[last] * 1.2)

    def test_other_entry_has_actual_walking_evidence(self):
        t = terrain(np.zeros((80, 100)))
        cover = np.zeros_like(t.a)
        pack = type(
            "SyntheticPack", (), {"network": [row("trail", [(100, 400), (700, 400)])]}
        )()
        start = dict(id="own", x=100, y=400, segment="trail")
        n = Network(
            pack,
            start,
            t,
            self.p,
            planner.validate(dict(corridor_m=1000)),
            cover,
            cover,
        )
        n.prepare_other_access(
            [
                dict(
                    id="other",
                    label="Other mapped entry",
                    x=700,
                    y=400,
                    segment="trail",
                )
            ]
        )
        endpoint = min(n.dist, key=lambda node: math.dist(n.nodes[node], (580, 400)))
        evidence = n.other_access(n.path(endpoint), 0)
        self.assertIsNotNone(evidence)
        self.assertAlmostEqual(evidence["walking_distance_m"], 120)
        self.assertAlmostEqual(
            evidence["walking_hours_high"], 120 / (2 * 1609.344) * self.p["time_margin"]
        )
        self.assertEqual(evidence["entry"], "Other mapped entry")
        n.prepare_other_access([])
        self.assertIsNone(n.other_access(n.path(endpoint), 0))

    def test_combined_day_fails_when_individual_fits(self):
        p = profiles.validate({"preset": "dad"})
        m = self.measure(np.linspace(0, 80, 63), p=p)
        m.update(distance_m=2500, ascent_m=100)
        start = dict(latitude=38.66, longitude=-107.3)
        legs = [
            dict(hours_low=0.3, hours_high=0.5),
            dict(hours_low=0.3, hours_high=0.5),
        ]
        am = schedule.variant("2026-10-31", start, legs, p, {}, "am")
        pm = schedule.variant("2026-10-31", start, legs, p, {}, "pm")
        self.assertTrue(am["feasible"])
        self.assertTrue(pm["feasible"])
        both = schedule.combined(am, pm, m, p, {})
        self.assertFalse(both["feasible"])
        self.assertEqual(both["movement"]["distance_m"], 5000)
        self.assertTrue(any("elapsed" in s for s in both["reasons"]))

    def test_optimistic_only_arrival_and_minimum_glassing(self):
        p = profiles.validate({"preset": "dad", "max_hours": 12})
        legs = [dict(hours_low=0.1, hours_high=2), dict(hours_low=0.1, hours_high=2)]
        c = dict(
            am_start_offset=0,
            am_end_offset=120,
            earliest="07:30",
            latest="11:30",
            min_glassing_minutes=60,
        )
        v = schedule.variant(
            "2026-10-31", dict(latitude=38.66, longitude=-107.3), legs, p, c, "am"
        )
        self.assertFalse(v["feasible"])
        self.assertLess(v["observation_minutes"], 60)
        departure = datetime.fromisoformat(v["events"][0]["depart"])
        conservative = datetime.fromisoformat(v["events"][0]["arrival_range"][1])
        self.assertEqual((conservative - departure).total_seconds(), 7200)

    def test_solar_noaa_reference_and_dst(self):
        # Independent approximate equinox Greenwich sunrise 06:04 UTC;
        # coarse NOAA fractional-year method accepted within five minutes.
        sun = schedule.solar("2026-03-20", 0, 0, "UTC")
        minutes = sun["sunrise"].hour * 60 + sun["sunrise"].minute
        self.assertLess(abs(minutes - 364), 5)
        a = schedule.solar("2026-10-31", 38.66, -107.3)
        b = schedule.solar("2026-11-01", 38.66, -107.3)
        self.assertEqual(a["sunrise"].utcoffset().total_seconds(), -6 * 3600)
        self.assertEqual(b["sunrise"].utcoffset().total_seconds(), -7 * 3600)
        self.assertLess(
            abs(
                (a["sunrise"].hour * 60 + a["sunrise"].minute)
                - (b["sunrise"].hour * 60 + b["sunrise"].minute)
                - 60
            ),
            4,
        )

    def test_actual_elapsed_travel_across_fall_back(self):
        p = profiles.validate({"preset": "tanner", "max_hours": 18})
        legs = [dict(hours_low=1, hours_high=2), dict(hours_low=1, hours_high=2)]
        c = dict(
            dark_travel=True,
            earliest="00:00",
            latest="23:00",
            am_start_offset=-300,
            am_end_offset=-120,
        )
        v = schedule.variant(
            "2026-11-01", dict(latitude=38.66, longitude=-107.3), legs, p, c, "am"
        )
        event = v["events"][0]
        depart = datetime.fromisoformat(event["depart"])
        arrive = datetime.fromisoformat(event["arrival_range"][1])
        self.assertNotEqual(depart.utcoffset(), arrive.utcoffset())
        self.assertEqual((arrive - depart).total_seconds(), 7200)

    def test_guardrails_edits_and_strict_source_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "cache.json"
            atomic(p, dict(value=1))
            seal(p)
            checked(p)
            p.write_text('{"value":2}')
            with self.assertRaises(ValueError):
                checked(p)
        c = planner.validate(
            {
                "excluded_segments": ["a"],
                "pinned": [dict(longitude=-107.3, latitude=38.66)],
            }
        )
        self.assertEqual(c["excluded_segments"], ["a"])
        self.assertEqual(c["pinned"][0]["longitude"], -107.3)
        with self.assertRaises(ValueError):
            planner.validate(dict(view_radius_m=3500))
        with self.assertRaises(ValueError):
            planner.validate(
                dict(profile=dict(preset="together", pace_mph=float("nan")))
            )
        with self.assertRaises(ValueError):
            schedule.settings(dict(min_glassing_minutes=0))

    def cover_fixture(self, root):
        pack = Pack.__new__(Pack)
        pack.folder = root
        pack.files = {}
        pack.spec = dict(assets={}, data={})
        for name in ("tree", "shrub"):
            path = root / (name + ".tif")
            ds = gdal.GetDriverByName("GTiff").Create(
                str(path), 40, 40, 1, gdal.GDT_Byte
            )
            ds.SetGeoTransform((0, 30, 0, 1200, 0, -30))
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(32613)
            ds.SetProjection(srs.ExportToWkt())
            ds.GetRasterBand(1).WriteArray(np.full((40, 40), 20, np.uint8))
            ds.GetRasterBand(1).SetNoDataValue(255)
            ds = None
            sha = file_hash(path)
            pack.spec["assets"][name] = dict(path=path.name, sha256=sha)
            pack.spec["data"][name] = dict(
                path=path.name,
                sha256=sha,
                component=name,
                units="percent",
                observation_year=2023,
            )
        return pack

    def test_warm_habitat_cannot_hide_corrupt_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = self.cover_fixture(root)
            t = terrain(np.zeros((80, 80)))
            cache = root / "cache"
            habitat_layers(pack, t, cache)
            ds = gdal.Open(str(root / "tree.tif"), gdal.GA_Update)
            ds.GetRasterBand(1).WriteArray(np.full((40, 40), 99, np.uint8))
            ds = None
            with self.assertRaises(ValueError):
                habitat_layers(pack, t, cache)

    def test_unsealed_raster_companion_is_not_a_hash_cache_bypass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = self.cover_fixture(root)
            pack.asset("tree.tif")
            (root / "tree.tif.aux.xml").write_text(
                '<PAMDataset><PAMRasterBand band="1"><NoDataValue>20</NoDataValue></PAMRasterBand></PAMDataset>'
            )
            with self.assertRaises(ValueError):
                pack.asset("tree.tif")

    def test_import_preserves_unknown_attributes_rejects_truncation(self):
        data = dict(
            type="FeatureCollection",
            features=[
                dict(
                    type="Feature",
                    geometry=dict(
                        type="LineString",
                        coordinates=[[-107.3, 38.66], [-107.31, 38.67]],
                    ),
                    properties=dict(objectid=123, unrecognized={"retained": True}),
                )
            ],
        )
        self.assertEqual(
            validate_geojson(data, "closed_roads")["features"][0]["properties"][
                "unrecognized"
            ],
            {"retained": True},
        )
        bad = copy.deepcopy(data)
        bad["exceededTransferLimit"] = True
        with self.assertRaises(ValueError):
            validate_geojson(bad, "closed_roads")
        bad = copy.deepcopy(data)
        bad["features"][0]["geometry"]["coordinates"][0] = [0, 0]
        with self.assertRaises(ValueError):
            validate_geojson(bad, "closed_roads")


if __name__ == "__main__":
    unittest.main()
