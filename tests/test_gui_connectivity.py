"""Connectivity agrees with real approach hard constraints; isolated saved evidence."""

import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from shapely.geometry import box, LineString, Polygon
from huntmaps_gui import connectivity as c, complementary, workflow
from huntmaps_gui.approach_search import Grid, solve
from huntmaps_gui.scouting_network import save_network
from huntmaps_gui.storage import read_json, write
from huntmaps_gui.config import configured, AppConfig
import test_workflow as fixture


class HardConnectivity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="connection-graph-")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.context = configured(
            AppConfig(state_dir=__import__("pathlib").Path(self.temp.name))
        )
        self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)

    def compare(
        self,
        dem,
        area=None,
        exclusions=None,
        maximum=25,
        target=(170, 170),
        lines=None,
        start=None,
    ):
        area = area if area is not None else box(0, 0, 200, 200)
        exclusions = exclusions if exclusions is not None else Polygon()
        lines = lines if lines is not None else [LineString([(10, 10), (10, 190)])]
        grid = Grid(
            dem,
            np.zeros_like(dem),
            np.zeros_like(dem),
            (0, 200),
            area,
            exclusions,
            maximum,
        )
        quick = c.ConnectionGrid(dem, (0, 200), area, exclusions, maximum)
        np.testing.assert_equal(quick.valid, grid.valid)
        for a, b in zip(quick.edge_valid, grid.edge_valid):
            np.testing.assert_equal(a, b)
        actual = c.connection(quick, lines, target, start)
        expected = solve(grid, lines, target, c.ZERO, start)
        self.assertEqual(
            actual["status"] == "connection_found", bool(expected["alternatives"])
        )
        return actual

    def test_flat_hill_barrier_and_endpoint_slopes(self):
        flat = np.zeros((10, 10))
        self.assertEqual(self.compare(flat)["status"], "connection_found")
        ridge = flat.copy()
        ridge[:, 4:6] = 100
        self.assertEqual(self.compare(ridge)["status"], "no_connection")
        ramp = np.broadcast_to(
            np.arange(10) * 20 * np.tan(np.deg2rad(28)), (10, 10)
        ).copy()
        self.assertEqual(self.compare(ramp, maximum=25)["status"], "no_connection")
        self.assertEqual(self.compare(ramp, maximum=30)["status"], "connection_found")

    def test_exclusion_wall_unknown_terrain_and_no_corner_cutting(self):
        flat = np.zeros((10, 10))
        self.compare(flat, exclusions=box(80, 0, 120, 200))
        flat[:, 4:6] = np.nan
        self.compare(flat)
        flat[1, 8] = np.nan
        self.assertEqual(self.compare(flat)["status"], "unavailable")
        flat[:] = 0
        flat[4, 5] = flat[5, 4] = 100
        self.compare(flat, target=(110, 90))

    def test_concave_boundary_exact_connectors_and_network_start(self):
        self.compare(
            np.zeros((10, 10)),
            area=box(0, 0, 200, 200).difference(box(70, 60, 130, 200)),
            target=(170, 30),
        )
        self.compare(np.zeros((10, 10)), target=(201, 170))
        lines = [LineString([(10, 10), (10, 190)]), LineString([(170, 10), (170, 190)])]
        self.compare(np.zeros((10, 10)), lines=lines, start=(10, 30))

    def test_seeded_random_grids_agree_with_full_solver(self):
        rng = np.random.default_rng(178)
        for _ in range(12):
            self.compare(rng.normal(0, 12, (10, 10)), maximum=25)

    def test_screen_never_runs_weighted_terrain_search(self):
        grid = c.ConnectionGrid(
            np.zeros((10, 10)), (0, 200), box(0, 0, 200, 200), Polygon(), 25
        )
        with patch.object(
            Grid, "search", side_effect=AssertionError("weighted solver called")
        ):
            self.assertEqual(
                c.connection(grid, [LineString([(10, 10), (10, 190)])], (170, 170))[
                    "status"
                ],
                "connection_found",
            )


class ScreenPersistence(unittest.TestCase):
    setUpClass = classmethod(fixture.WorkflowJourney.setUpClass.__func__)
    tearDownClass = classmethod(fixture.WorkflowJourney.tearDownClass.__func__)
    setUp = fixture.WorkflowJourney.setUp

    def networks(self, coverage=True):
        t = c.Terrain(self.r)
        p = self.r.points[self.cid]
        ll = t.ll
        bounds = list(__import__("shapely").ops.transform(ll, t.footprint).bounds)
        raw = json.dumps(
            dict(
                type="LineString",
                coordinates=[
                    ll(p["x"] - 10, p["y"] - 20),
                    ll(p["x"] + 10, p["y"] + 20),
                ],
            )
        ).encode()
        road = save_network(
            raw,
            ".geojson",
            "roads",
            "Synthetic connection test",
            coverage=bounds if coverage else None,
        )
        trail = save_network(
            b'{"type":"FeatureCollection","features":[]}',
            ".geojson",
            "trails",
            "Verified empty fixture",
            coverage=bounds,
        )
        return road, trail

    def prepare(self):
        spec, _ = c.snapshot(self.run)
        token = c.digest(spec)[:32]
        write(
            c.path(token),
            dict(
                id=token,
                version=c.VERSION,
                run_id=self.run,
                status="running",
                maximum_slope_deg=spec["maximum_slope_deg"],
                snapshot=spec,
                points={},
                total=len(spec["rows"]),
                completed=0,
            ),
        )
        return token

    def test_actual_screen_cache_invalidation_and_saved_outputs(self):
        self.networks()
        before = (
            {p: p.read_bytes() for p in self.r.base.rglob("*") if p.is_file()}
            if hasattr(self.r.base, "rglob")
            else {}
        )
        token = self.prepare()
        with patch.object(Grid, "search", side_effect=AssertionError("route search")):
            result = c.calculate(self.run, token)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["completed"], len(self.r.points))
        self.assertIn(self.cid, c.eligible(self.run, token))
        self.assertEqual(c.current(self.run)["id"], token)
        cached = c.path(token).read_bytes()
        damaged = read_json(c.path(token))
        damaged["points"][self.cid]["status"] = "unavailable"
        write(c.path(token), damaged)
        with self.assertRaisesRegex(ValueError, "cache changed"):
            c.current(self.run)
        c.path(token).write_bytes(cached)
        with patch.object(c, "snapshot", wraps=c.snapshot):
            collection = complementary.calculate(
                self.run, 3, jobs=None, connection_screen=token
            )
        self.assertTrue(
            all(
                p["id"] in c.eligible(self.run, token)
                for p in collection["suggestions"]
            )
        )
        # A metadata replacement invalidates even unchanged raw line bytes.
        metadata = next((self.state / "networks").glob("*/network.json"))
        value = read_json(metadata)
        value["source_date"] = "2026-10-17"
        write(metadata, value)
        self.assertEqual(c.current(self.run)["status"], "not_started")
        with self.assertRaisesRegex(ValueError, "screen changed"):
            c.eligible(self.run, token)
        with self.assertRaises(ValueError):
            complementary.load_result(self.run, collection["id"])
        for p, raw in before.items():
            self.assertEqual(p.read_bytes(), raw)

    def test_unknown_networks_are_unavailable_not_disconnected(self):
        spec, r = c.snapshot(self.run)
        index = c.Index(r, [])
        row = spec["rows"][0]
        evidence = index.query(row["point"], row["settings"])
        self.assertEqual(evidence["status"], "unavailable")
        self.assertEqual(evidence["reason"], "network_coverage")
        self.assertEqual(evidence["maximum_slope_deg"], 25)

    def test_partial_sources_can_prove_a_connection_but_corruption_stays_unknown(self):
        road, _ = self.networks(coverage=False)
        spec, r = c.snapshot(self.run)
        index = c.Index(r, spec["inventory"])
        row = spec["rows"][0]
        self.assertEqual(
            index.query(row["point"], row["settings"])["status"], "connection_found"
        )
        source = next((self.state / "networks" / road["id"]).glob("original.*"))
        source.write_bytes(b"corrupt")
        spec, r = c.snapshot(self.run)
        index = c.Index(r, spec["inventory"])
        self.assertEqual(
            index.query(row["point"], row["settings"])["status"], "unavailable"
        )

    def test_proposal_matches_published_boundary_round_trip_and_grid(self):
        workflow.decide(
            self.run,
            self.cid,
            dict(
                action="shortlist",
                revision=workflow.records(self.run)["revision"],
                point=workflow.point(self.run, self.cid),
            ),
            None,
        )
        from huntmaps_gui.approach_preflight import suggest
        from shapely.geometry import shape
        from shapely.ops import transform

        t = c.Terrain(self.r)
        proposal = t.proposal(self.r.candidate(self.cid))
        published = transform(
            t.xy, shape(suggest(self.run, dict(id=self.cid))["travel_area"])
        )
        self.assertEqual(proposal.wkb, published.wkb)
        a, origin = t.raster(proposal)
        b, other = t.raster(published)
        self.assertEqual(origin, other)
        np.testing.assert_equal(a, b)

    def test_shortlisted_disconnected_spot_is_retained_in_collection(self):
        self.networks()
        t = c.Terrain(self.r)
        from shapely.geometry import mapping
        from shapely.ops import transform

        area = mapping(transform(t.ll, t.proposal(self.r.candidate(self.cid))))
        point = workflow.point(self.run, self.cid)
        workflow.decide(
            self.run,
            self.cid,
            dict(
                action="shortlist",
                point=point,
                revision=workflow.records(self.run)["revision"],
            ),
            None,
        )
        write(
            self.state / "approach-reviews" / f"{self.run}.json",
            dict(
                version=1,
                revision=1,
                queue=[self.cid],
                active_point=self.cid,
                defaults={},
                drafts={
                    self.cid: dict(point=point, travel_area=area, exclusions=[area])
                },
            ),
        )
        token = self.prepare()
        c.calculate(self.run, token)
        self.assertNotIn(self.cid, c.eligible(self.run, token))
        result = complementary.calculate(self.run, 3, connection_screen=token)
        self.assertIn(self.cid, [p["id"] for p in result["kept"]])

    def test_start_reuses_completed_cache_and_active_status_fetches_only_its_job(self):
        self.networks()
        job = dict(id="a" * 32, status="running", kind="connectivity-screen")
        jobs = SimpleNamespace(
            list=lambda *args: [], start=lambda *args, **kwargs: job, get=lambda _: job
        )
        value = c.start(self.run, {}, jobs)
        self.assertEqual(value["job"]["id"], job["id"])
        jobs.list = lambda *args: (_ for _ in ()).throw(
            AssertionError("history polling")
        )
        self.assertEqual(c.current(self.run, jobs)["status"], "running")
        c.calculate(self.run, value["id"])
        jobs.start = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("cached work restarted")
        )
        self.assertEqual(c.start(self.run, {}, jobs)["status"], "complete")

    def test_run_default_changes_preserve_saved_spot_limit(self):
        point = workflow.point(self.run, self.cid)
        write(
            self.state / "approach-reviews" / f"{self.run}.json",
            dict(
                version=1,
                revision=1,
                queue=[],
                active_point=None,
                defaults=dict(maximum_slope_deg=35),
                drafts={self.cid: dict(point=point, maximum_slope_deg=30)},
            ),
        )
        spec, _ = c.snapshot(self.run)
        self.assertEqual(spec["maximum_slope_deg"], 35)
        self.assertEqual(
            next(r for r in spec["rows"] if r["point"]["id"] == self.cid)["settings"][
                "maximum_slope_deg"
            ],
            30,
        )
        self.assertTrue(
            any(
                r["settings"]["maximum_slope_deg"] == 35
                for r in spec["rows"]
                if r["point"]["id"] != self.cid
            )
        )

    def test_slope_policy_and_cancelled_partial_is_retryable(self):
        for invalid in [0, 36, None, float("nan")]:
            with self.assertRaises(ValueError):
                c.limit(invalid)
        token = self.prepare()
        write(c.path(token).with_suffix(".job.json"), dict(id="f" * 32))
        jobs = SimpleNamespace(get=lambda _: dict(status="cancelled"))
        self.assertEqual(c.current(self.run, jobs)["status"], "cancelled")
        self.assertEqual(read_json(c.path(token))["status"], "running")
        busy = SimpleNamespace(list=lambda *args: [dict(status="running")])
        review = self.state / "approach-reviews" / f"{self.run}.json"
        with self.assertRaisesRegex(ValueError, "active job"):
            c.start(self.run, dict(save_default=True, maximum_slope_deg=30), busy)
        self.assertFalse(review.exists())

    def test_changed_coordinates_invalidate_only_current_display_evidence(self):
        token = self.prepare()
        from huntmaps_gui import manual_observers

        pose = dict(
            anchor=self.cid,
            longitude=self.r.candidate(self.cid)["longitude"],
            latitude=self.r.candidate(self.cid)["latitude"],
            east_m=1,
            north_m=0,
        )
        with patch.object(manual_observers.fp, "observer", return_value=pose):
            manual_observers.create(self.run, dict(name="Exact manual spot"))
        self.assertNotEqual(c.current(self.run)["id"], token)
        self.assertTrue(c.path(token).exists())


if __name__ == "__main__":
    unittest.main()
