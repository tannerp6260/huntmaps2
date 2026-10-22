"""Independent engineering oracles and faults; no synthetic wildlife labels."""

from datetime import date
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from osgeo import gdal, osr

from practical_glassing import model
from practical_glassing.engine import evaluate, packed_indices, Visits, community_layers
from practical_glassing.package import CommunityPackage, Receiver, legends
from trail_scout.storage import file_hash, atomic, read
from trail_scout.sources import access, date_match
from trail_scout import profiles, planner
from huntmaps_gui import complementary

ROOT = Path(__file__).resolve().parents[1]


def fixture_legends():
    evt = {
        int(c): dict(EVT_NAME=t["name"], EVT_LF=t["lifeform"])
        for c, t in model.TRAITS["classes"].items()
    }
    evt[-9999] = dict(EVT_NAME="Fill-NoData", EVT_LF="Fill-NoData")
    evt[99999] = dict(
        EVT_NAME="Explicit unsupported engineering test class", EVT_LF="Herb"
    )
    return dict(
        EVT=evt,
        EVC={
            -9999: dict(CLASSNAMES="Fill-NoData"),
            168: dict(CLASSNAMES="Tree Cover = 68%"),
        },
        EVH={
            -9999: dict(CLASSNAMES="Fill-NoData"),
            104: dict(CLASSNAMES="Tree Height = 4 meters"),
            204: dict(CLASSNAMES="Shrub Height = 0.4 meter"),
        },
    )


def mem(shape=(30, 30), gt=(300000, 10, 0, 4300000, 0, -10)):
    ds = gdal.GetDriverByName("MEM").Create("", shape[1], shape[0], 1, gdal.GDT_Float32)
    ds.SetGeoTransform(gt)
    sr = osr.SpatialReference()
    sr.ImportFromEPSG(32613)
    ds.SetProjection(sr.ExportToWkt())
    ds.GetRasterBand(1).WriteArray(np.zeros(shape))
    return ds


class PracticalNumerical(unittest.TestCase):
    def test_unknown_only_is_not_known_zero_and_obstruction_nodata_rejected(self):
        from practical_glassing.engine import compare

        shape = (2, 3)
        ones = np.ones(shape)
        no = np.zeros(shape, dtype=bool)
        old = dict(
            h=ones * 0.5, g=ones * 0.5, known=no, tree=ones * 0.2, shrub=ones * 0.2
        )
        new = dict(
            h=np.full(shape, np.nan),
            known=no,
            deciduous=ones * 0,
            group=np.zeros(shape, dtype=np.uint8),
            short_aspen=no,
            evt=ones * 7011,
        )
        values, unknown = evaluate(
            dict(x=300005, y=4299995),
            np.arange(6),
            shape,
            (300000, 10, 0, 4300000, 0, -10),
            old,
            new,
            1000,
            {},
        )
        self.assertIsNone(unknown["scores"]["combined"])
        self.assertEqual(unknown["status"], "insufficient_data")
        new["h"] = np.zeros(shape)
        new["known"] = ~no
        values, known = evaluate(
            dict(x=300005, y=4299995),
            np.arange(6),
            shape,
            (300000, 10, 0, 4300000, 0, -10),
            old,
            new,
            1000,
            {},
        )
        self.assertEqual(known["scores"]["combined"], 0)
        self.assertEqual(known["habitat_unknown_m2"], 0)
        ds = mem(shape)
        ds.GetRasterBand(1).WriteArray(np.full(shape, -9999))
        ds.GetRasterBand(1).SetNoDataValue(-9999)
        with tempfile.TemporaryDirectory(
            prefix="practical-nodata-"
        ) as td, self.assertRaisesRegex(ValueError, "Obstruction terrain"):
            compare(ds, [], lambda _: no, no, old, None, Path(td), {}, 1000)

    def test_receiver_failure_counts_retained_bytes_and_exact_request_reuse(self):
        import io

        class Reply(io.BytesIO):
            status = 200
            headers = {}

        with tempfile.TemporaryDirectory(prefix="practical-transfer-") as td:
            receiver = Receiver(td)
            with patch("urllib.request.urlopen", return_value=Reply(b"abc")):
                with self.assertRaisesRegex(ValueError, "byte cap"):
                    receiver.get("https://example.invalid/bounded", 2)
            self.assertEqual(receiver.ledger["received_bytes"], 3)
            self.assertTrue(list(Path(td).glob("*.partial")))
            with patch("urllib.request.urlopen", return_value=Reply(b"valid")):
                path, record = receiver.get("https://example.invalid/bounded", 20)
            self.assertEqual(receiver.ledger["received_bytes"], 8)
            with patch(
                "urllib.request.urlopen",
                side_effect=AssertionError("must reuse immutable object"),
            ):
                self.assertEqual(
                    receiver.get("https://example.invalid/bounded", 20)[0], path
                )
            self.assertEqual(record["sha256"], file_hash(path))

    def test_naip_actual_resolution_field_and_no_false_crs_claim(self):
        from types import SimpleNamespace
        from huntmaps_gui import scene_sources
        from huntmaps_gui.config import AppConfig, configured

        run = SimpleNamespace(
            points={"X": dict(x=300000, y=4280000)}, config=dict(epsg=32613), images=[]
        )
        rows = dict(
            features=[
                dict(
                    attributes=dict(
                        OBJECTID=29489,
                        Year=2019,
                        acquisition_date=1568332800000,
                        resolution_value=0.6,
                    )
                )
            ]
        )
        with tempfile.TemporaryDirectory(prefix="practical-naip-") as td, configured(
            AppConfig(state_dir=Path(td))
        ), patch.object(scene_sources, "metadata", return_value=rows):
            sources = scene_sources.imagery_plan(run, ["X"], 1000)
            self.assertEqual(sources[0]["native_resolution_m"], [0.6])
            self.assertEqual(sources[0]["dates"], ["2019-09-13"])

    def test_official_units_decode_labels_not_code_magnitude(self):
        l = fixture_legends()
        self.assertEqual(model.decode_structure(l["EVC"], "EVC")[168]["value"], 68)
        self.assertEqual(model.decode_structure(l["EVH"], "EVH")[204]["value"], 0.4)
        with self.assertRaises(ValueError):
            legends(b"VALUE,CLASSNAMES\n1,a\n1,b\n", "EVH")
        with self.assertRaises(ValueError):
            legends(b"<html>no raster legend</html>", "EVT")

    def test_community_equal_browse_nonhabitat_zero_unknown_and_halo(self):
        l = fixture_legends()
        evt = np.full((19, 19), 7011)
        evc = np.full(evt.shape, 168)
        evh = np.full(evt.shape, 104)
        for code in (7011, 7061, 7107, 7080):
            out = model.community(np.full(evt.shape, code), evc, evh, l)
            self.assertAlmostEqual(out["h"][9, 9], 1)
            self.assertFalse(out["known"][0, 0])
        evt[9, 9] = 7292
        out = model.community(evt, evc, evh, l)
        self.assertEqual(out["h"][9, 9], 0)
        self.assertTrue(out["known"][9, 9])
        self.assertFalse(out["short_aspen"][9, 9])
        evt[9, 9] = 99999
        out = model.community(evt, evc, evh, l)
        self.assertTrue(np.isnan(out["h"][9, 9]))
        self.assertFalse(out["known"][9, 10])
        self.assertTrue(out["known"][4, 4])
        self.assertTrue(out["short_aspen"][4, 4])

    def test_release_identity_and_fractional_class_rejected(self):
        l = fixture_legends()
        a = np.full((7, 7), 7011)
        l["EVT"][7011]["EVT_NAME"] = "Different release meaning"
        with self.assertRaises(ValueError):
            model.community(a, a, a, l)
        with self.assertRaises(ValueError):
            model.community(
                a + 0.1, np.full(a.shape, 168), np.full(a.shape, 104), fixture_legends()
            )
        with self.assertRaises(ValueError):
            model.settings(dict(context_m=False))

    def test_context_uses_full_disk_and_single_bounded_term(self):
        l = fixture_legends()
        a = np.full((31, 31), 7145)
        c = np.full(a.shape, 168)
        h = np.full(a.shape, 104)
        a[10:20, 10:20] = 7011
        base = model.community(a, c, h, l, policy=dict(context_m=0))
        edge = model.community(a, c, h, l)
        self.assertLessEqual(np.nanmax(edge["h"] - base["h"]), 0.2 + 1e-12)
        self.assertTrue(
            np.all((edge["h"][edge["known"]] >= 0) & (edge["h"][edge["known"]] <= 1))
        )

    def test_task_distance_order_and_leaf_retains_obstruction(self):
        d = np.array([0, 500, 1000, 1500, 2000, 3000])
        self.assertTrue(
            np.all(
                model.distance_preference(d, "spot")
                >= model.distance_preference(d, "identify")
            )
        )
        self.assertTrue(
            np.all(
                model.distance_preference(d, "identify")
                >= model.distance_preference(d, "assess")
            )
        )
        self.assertTrue(np.all(model.distance_preference(d, "uniform") == 1))
        t = s = np.ones(3)
        dec = np.array([1, 0.5, 0])
        on = model.concealment(t, s, dec, "unknown")
        off = model.concealment(t, s, dec, "off")
        self.assertTrue(np.all(off >= on))
        self.assertLess(off[0], 0.2)
        self.assertEqual(on[2], off[2])
        with self.assertRaises(ValueError):
            model.concealment(t * 100, s, dec, "off")

    def test_attention_monotonic_fixed_cost_and_radius_boundary(self):
        dx = np.array([0, 0, 400, 0])
        dy = np.array([100, 500, 0, 900])
        q = np.array([1, 0.5, 0, 0.0])
        m, a = model.allocate(dx, dy, q, 100, 1000, 30)
        m2, b = model.allocate(dx, dy, q + np.array([0, 0, 0.1, 0.1]), 100, 1000, 30)
        self.assertGreaterEqual(b["score"], a["score"])
        self.assertLessEqual(a["minutes_used"], 30)
        costs = lambda x: {p["id"]: p["full_area_km2"] for p in x["patches"]}
        for k, v in costs(a).items():
            if k in costs(b):
                self.assertEqual(v, costs(b)[k])
        mask, at = model.allocate(
            np.array([0]), np.array([500]), np.array([1.0]), 100, 500, 30
        )
        self.assertTrue(mask[0])
        self.assertEqual(at["score"], 100)
        self.assertEqual(model.allocate(dx, dy, q, 100, 1000, 0)[1]["score"], 0)

    def test_best_view_full_reference_duplicates_and_improvement(self):
        rng = np.random.default_rng(21)
        dense = rng.random((6, 41))
        dense[dense < 0.5] = 0
        visits = [model.Visit(np.flatnonzero(a), a[a > 0]) for a in dense]
        score, values = model.best_view(visits, 41, 100)
        np.testing.assert_allclose(values, dense.max(axis=0), rtol=0, atol=0)
        self.assertAlmostEqual(score, float(dense.max(axis=0).sum() * 100), places=10)
        self.assertEqual(
            model.best_view([visits[0], visits[0]], 41)[0],
            model.best_view([visits[0]], 41)[0],
        )
        v1 = model.Visit(np.array([0, 1]), np.array([0.2, 0.6]))
        v2 = model.Visit(np.array([0, 1]), np.array([0.4, 0.5]))
        self.assertAlmostEqual(model.best_view([v1, v2], 2)[0] - 0.8, 0.2)
        with self.assertRaises(ValueError):
            model.best_view([model.Visit(np.array([1, 1]), np.ones(2))], 2)
        with self.assertRaises(ValueError):
            model.best_view([model.Visit(np.array([2]), np.ones(1))], 2)

    def test_original_packed_union_matches_generalized_shared_q(self):
        rng = np.random.default_rng(27)
        shape = (13, 19)
        masks = rng.random((5, *shape)) > 0.6
        q = rng.random(shape)
        visits = [
            model.Visit(np.flatnonzero(m), q.ravel()[np.flatnonzero(m)]) for m in masks
        ]
        shared = np.logical_or.reduce(masks)
        packed = complementary.pack(shared)
        self.assertAlmostEqual(
            packed.weighted(None, q), model.best_view(visits, shared.size)[0], places=12
        )
        for m in masks:
            p = packed_indices(np.flatnonzero(m), shape[1])
            out = np.zeros((shape[0], (shape[1] + 7) // 8), np.uint8)
            p.include(out)
            np.testing.assert_array_equal(
                np.unpackbits(out, axis=1)[:, : shape[1]].astype(bool), m
            )

    def test_shortlist_kept_spacing_fewer_than_quota_and_oracle(self):
        rows = [dict(id=chr(65 + i), x=i * 100, y=0) for i in range(4)]
        dense = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0.7, 0], [0, 0, 0, 0.0]])
        visits = {
            r["id"]: model.Visit(np.flatnonzero(a), a[a > 0])
            for r, a in zip(rows, dense)
        }
        got = model.shortlist(rows, visits.__getitem__, 4, 1, count=5)
        self.assertEqual(got["ids"], ["A", "B", "C"])
        self.assertAlmostEqual(got["relative_m2"], 2.7)
        got = model.shortlist(
            rows, visits.__getitem__, 4, 1, count=2, separation=150, kept=["B"]
        )
        self.assertEqual(got["ids"], ["B"])
        self.assertTrue(got["members"][0]["retained"])
        got = model.shortlist(rows, visits.__getitem__, 4, 1, count=2)
        oracle = max(
            model.best_view([visits[r["id"]] for r in choice], 4)[0]
            for choice in itertools.combinations(rows, 2)
        )
        self.assertEqual(got["relative_m2"], oracle)

    def test_sparse_cache_same_size_mtime_corruption_rejected(self):
        with tempfile.TemporaryDirectory(prefix="practical-unit-") as td:
            from trail_scout.storage import digest
            import os

            store = Visits(td, cap=1)
            store.write("A", np.array([0, 2]), dict(combined=np.array([0.4, 0.5])))
            self.assertAlmostEqual(store.get("A", "combined").values.sum(), 0.9)
            p = Path(td) / (digest("A") + ".npz")
            stamp = p.stat()
            b = bytearray(p.read_bytes())
            b[-1] ^= 1
            p.write_bytes(b)
            os.utime(p, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            with self.assertRaises(ValueError):
                Visits(td).get("A", "combined")

    def test_access_conflicts_dates_width_and_prohibitions(self):
        row = dict(
            id="r",
            kind="trails",
            properties=dict(hiker_pedestrian_managed="yearlong"),
            motor_closed=False,
            mvum=[
                dict(truck="open", truck_datesopen="yearlong"),
                dict(truck="open", truck_datesopen="05/01-10/30"),
            ],
        )
        for records in (row["mvum"], list(reversed(row["mvum"]))):
            row["mvum"] = records
            self.assertEqual(access(row, date(2026, 10, 31))["motor"], "closed")
        row["mvum"] = [
            dict(other_ohv_gt50inches="open", other_ohv_gt50inches_datesopen="yearlong")
        ]
        self.assertEqual(access(row, date(2026, 10, 31), "teryx")["motor"], "unknown")
        self.assertEqual(
            access(row, date(2026, 10, 31), "teryx", width_inches=64)["motor"],
            "supported",
        )
        self.assertEqual(
            access(row, date(2026, 10, 31), "teryx", width_inches=48)["motor"],
            "unknown",
        )
        rules = [
            dict(segment="r", foot="closed", provenance="fixture dated restriction"),
            dict(
                segment="r",
                foot="supported",
                provenance="fixture conflicting assertion",
            ),
        ]
        for rs in (rules, list(reversed(rules))):
            self.assertEqual(
                access(row, date(2026, 10, 31), manual=rs)["foot"], "closed"
            )
        self.assertIsNone(date_match("02/31-12/31", date(2026, 10, 31)))
        self.assertTrue(date_match("11/01-03/01", date(2027, 1, 2)))
        self.assertEqual(profiles.validate()["max_miles"], 2.5)
        self.assertEqual(profiles.validate()["max_gain_ft"], 750)
        self.assertEqual(profiles.validate(dict(preset="extended"))["max_gain_ft"], 900)


class InstalledPackage(unittest.TestCase):
    def test_real_corridor_works_without_historical_archives(self):
        from trail_scout.storage import Paths, seal
        from trail_scout.sources import Pack
        from trail_scout.network import starts
        from trail_scout.planner import calculate

        if not self.pack.spec.get("extra_sources"):
            self.skipTest(
                "Portable access snapshot not prepared; run explicit companion preparation"
            )
        with tempfile.TemporaryDirectory(
            prefix="huntmaps-practical-archive-free-"
        ) as td:
            root = Path(td) / "source"
            (root / "data").mkdir(parents=True)
            (root / ".trailscout").mkdir()
            (root / "data/unit-packs").symlink_to(
                ROOT / "data/unit-packs", target_is_directory=True
            )
            (root / ".trailscout/community").symlink_to(
                self.root, target_is_directory=True
            )
            paths = Paths(source=root, state=Path(td) / "state")
            with patch(
                "urllib.request.urlopen",
                side_effect=AssertionError(
                    "No providers in normal archived-free analysis"
                ),
            ):
                pack = Pack(paths)
                self.assertFalse((root / "data/scouting").exists())
                self.assertTrue(pack.extra["mvum_roads"])
                self.assertTrue(pack.extra["ownership"])
                self.assertFalse(
                    any(p.is_relative_to(ROOT / "data/scouting") for p in pack.files)
                )
                entry = next(
                    r
                    for r in starts(pack, date(2026, 10, 31))
                    if r["label"] == "Soap Creek · entry"
                )
                result = calculate(
                    paths,
                    pack,
                    dict(start_id=entry["id"], candidate_budget=16, practical={}),
                    paths.artifact("analyses", "a" * 32),
                )
                self.assertTrue(result["options"])
                self.assertTrue(result["practical"]["rows"])
                self.assertEqual(result["source_revision"], Pack(Paths()).revision)

    @classmethod
    def setUpClass(cls):
        cls.root = ROOT / ".trailscout/community"
        if not (cls.root / "active.json").exists():
            raise unittest.SkipTest(
                "Real companion is not installed; no substitute download"
            )
        cls.pack = CommunityPackage(cls.root)

    def test_real_native_grid_codes_dates_and_vector_indexes(self):
        import sqlite3

        spec = self.pack.spec
        self.assertEqual(spec["release"], "LF2025")
        self.assertLess(spec["source_received_bytes"], 250 * 1024**2)
        for source in spec["sources"].values():
            ds = gdal.Open(str(self.pack.asset(source["cog"])))
            self.assertEqual(ds.GetMetadata("IMAGE_STRUCTURE")["LAYOUT"], "COG")
            self.assertEqual(ds.GetGeoTransform()[1], 30)
            self.assertEqual(ds.GetSpatialRef().GetAuthorityCode(None), "5070")
            self.assertIsNone(source["acquisition_dates"])
        with sqlite3.connect(self.pack.asset(spec["vectors"])) as c:
            tables = {
                r[0]
                for r in c.execute("select name from sqlite_master where type='table'")
            }
            self.assertIn("rtree_network_geom", tables)
            self.assertIn("rtree_unit_geom", tables)
            attrs = json.loads(
                c.execute("select attributes_json from network limit 1").fetchone()[0]
            )
            self.assertIn("inventory_kind", attrs)

    def test_real_window_halo_alignment_categorical_and_footprint(self):
        from pyproj import Transformer

        x, y = Transformer.from_crs(4326, 32613, always_xy=True).transform(
            -107.1, 38.65
        )
        x = int(x // 30) * 30
        y = int(y // 30) * 30
        full, gt, wkt = self.pack.window([x - 600, y - 600, x + 600, y + 600])
        small, sg, _ = self.pack.window([x - 300, y - 300, x + 300, y + 300])
        for name in full:
            np.testing.assert_array_equal(full[name][10:30, 10:30], small[name])
        h = model.community(full["EVT"], full["EVC"], full["EVH"], self.pack.legend)
        cropped = model.community(
            small["EVT"], small["EVC"], small["EVH"], self.pack.legend
        )
        np.testing.assert_allclose(
            h["h"][14:26, 14:26], cropped["h"][4:16, 4:16], equal_nan=True
        )
        outside, _, _ = self.pack.window([500000, 4500000, 500300, 4500300])
        self.assertTrue(np.all(outside["EVT"] == -9999))

    def test_real_offline_window_does_not_fetch(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("offline")):
            layers = community_layers(
                self.pack, mem((30, 30), (300000, 10, 0, 4280000, 0, -10))
            )
            self.assertEqual(layers["h"].shape, (30, 30))
            self.assertTrue(np.all(layers["evt"] == np.trunc(layers["evt"])))

    def test_real_road_budget_review_save_exports_restart_and_corruption(self):
        import time
        from fastapi.testclient import TestClient
        from trail_scout.app import create_app
        from trail_scout.storage import Paths
        from practical_glassing.packet import artifact

        with tempfile.TemporaryDirectory(prefix="huntmaps-practical-api-") as td:
            paths = Paths(source=ROOT, state=Path(td) / "state")
            with patch(
                "urllib.request.urlopen",
                side_effect=AssertionError("Core analysis must stay offline"),
            ):
                with TestClient(create_app(paths)) as client:
                    area = client.get("/api/areas").json()[0]
                    self.assertEqual(area["practical"]["status"], "ready")
                    entries = client.get("/api/starts").json()
                    entry = next(
                        r for r in entries if r["label"] == "Soap Creek · entry"
                    )
                    response = client.post(
                        "/api/jobs",
                        json=dict(
                            start_id=entry["id"], candidate_budget=16, practical={}
                        ),
                    )
                    self.assertEqual(response.status_code, 200, response.text)
                    job = response.json()
                    deadline = time.monotonic() + 90
                    while time.monotonic() < deadline:
                        job = client.get("/api/jobs/" + job["id"]).json()
                        if job["status"] in ("completed", "failed", "cancelled"):
                            break
                        time.sleep(0.05)
                    self.assertEqual(job["status"], "completed", job)
                    result = client.get("/api/analyses/" + job["analysis_id"]).json()
                    review = result["practical"]
                    self.assertTrue(review["rows"])
                    self.assertFalse(review["collections"]["combined"]["timed_plan"])
                    for row in review["rows"]:
                        self.assertAlmostEqual(
                            sum(b["physical_m2"] for b in row["bands"]),
                            row["visible_matching_m2"],
                        )
                        self.assertAlmostEqual(
                            row["scorable_m2"] + row["habitat_unknown_m2"],
                            row["visible_matching_m2"],
                        )
                        self.assertAlmostEqual(
                            sum(row["community_m2"].values()),
                            row["visible_matching_m2"],
                        )
                        self.assertLessEqual(row["scan"]["minutes_used"], 30)
                    report = client.get(review["report_url"])
                    self.assertEqual(report.status_code, 200)
                    self.assertIn("Canonical candidate order", report.text)
                    option = next(
                        o for o in result["options"] if o["schedules"]["am"]["feasible"]
                    )
                    self.assertLessEqual(
                        option["movement"]["distance_m"], 2.5 * 1609.344 * 0.75
                    )
                    self.assertLessEqual(
                        option["movement"]["ascent_m"], 750 * 0.3048 * 0.75
                    )
                    saved = client.post(
                        "/api/plans",
                        json=dict(
                            analysis_id=result["analysis_id"],
                            settings=result["settings"],
                            option_id=option["id"],
                            mode="am",
                            name="Engineering test; real source data",
                        ),
                    )
                    self.assertEqual(saved.status_code, 200, saved.text)
                    saved = saved.json()
                    self.assertEqual(saved["practical"]["package"], review["package"])
                    exported = client.get(
                        "/api/plans/" + saved["id"] + "/export/json"
                    ).json()
                    self.assertEqual(exported["practical"]["orders"], review["orders"])
                with TestClient(create_app(paths)) as restarted:
                    self.assertEqual(
                        restarted.get("/api/plans/" + saved["id"]).json()["practical"][
                            "package"
                        ],
                        review["package"],
                    )
                    self.assertEqual(
                        restarted.get(review["report_url"]).status_code, 200
                    )
                folder = paths.artifact("analyses", result["analysis_id"]) / "practical"
                original = artifact(folder, "community.png").read_bytes()
                (folder / "community.png").write_bytes(
                    original[:-1] + bytes([original[-1] ^ 1])
                )
                with self.assertRaises(ValueError):
                    artifact(folder, "community.png")


if __name__ == "__main__":
    unittest.main()
