"""Legacy lidar recovery through real LAS decoding, preparation and publication."""

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from huntmaps_gui import first_person as fp, first_person_worker as worker
from huntmaps_gui import scene_sources, scene_storage
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui.storage import write
import test_workflow as workflow_fixture


URL = "https://rockyweb.usgs.gov/project/LAZ/fixture.laz"


def cached_record(raw=b"lidar", url=URL, bounds=None):
    key = hashlib.sha256(url.encode()).hexdigest()[:24] + ".laz"
    path = fp.HOME / "sources" / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return key, dict(
        key=key,
        url=url,
        bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        title="Legacy fixture lidar",
        bounds=bounds or dict(minX=0, minY=0, maxX=2, maxY=2),
        acquisition_date="2019-01-01",
        # Historical manifests did not store acquisition or vertical_reference.
        candidates=["obsolete-setup"],
        cached=False,
    )


def make_lidar_plan(run, cid):
    """Bounded synthetic ground/foliage; also used by the isolated browser check."""
    laspy, pyproj = worker.deps()
    p = run.points[cid]
    rows, cols = np.mgrid[-45:46, -45:46]
    ground = np.column_stack(
        [cols.ravel(), rows.ravel(), np.full(cols.size, 2200), np.full(cols.size, 2)]
    )
    # Four distinct returns per foliage cell, at several heights in front of north.
    foliage = np.array(
        [
            [x + dx, y + dy, 2200 + z + dz, 5]
            for x in range(-4, 5)
            for y in range(12, 17)
            for z in range(1, 6)
            for dx, dy, dz in [
                (0.1, 0.1, 0.1),
                (0.3, 0.1, 0.2),
                (0.1, 0.3, 0.3),
                (0.3, 0.3, 0.4),
            ]
        ]
    )
    points = np.vstack([ground, foliage])
    header = laspy.LasHeader(point_format=6, version="1.4")
    header.add_crs(pyproj.CRS.from_user_input(f"EPSG:{run.config['epsg']}+5703"))
    header.scales = [0.001, 0.001, 0.001]
    header.offsets = [p["x"], p["y"], 2200]
    data = laspy.LasData(header)
    data.x, data.y, data.z = points[:, 0] + p["x"], points[:, 1] + p["y"], points[:, 2]
    data.classification = points[:, 3].astype("u1")
    stream = io.BytesIO()
    data.write(stream, do_compress=True)
    bbox = worker.geographic_box(run, cid)
    key, source = cached_record(
        stream.getvalue(), bounds=dict(zip(("minX", "minY", "maxX", "maxY"), bbox))
    )
    write(fp.HOME / "sources/manifest.json", {key: source})
    ident = fp.new_plan(run.id, [cid], "best")
    with patch.object(
        worker.urllib.request, "urlopen", side_effect=OSError("offline fixture")
    ), patch.object(scene_sources, "imagery_plan", return_value=[]):
        worker.discover(ident)
    return fp.plan(ident)


class LegacyLidarMetadata(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="huntmaps-lidar-metadata-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.context = configured(
            AppConfig(source_dir=root, workspace=root, state_dir=root / "state")
        )
        self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)
        self.plan = dict(
            id="a" * 32,
            run_id="fixture",
            candidates=["X", "Y"],
            fidelity="best",
            snapshots={},
        )
        write(fp.HOME / "plans" / (self.plan["id"] + ".json"), self.plan)
        self.run = SimpleNamespace(config=dict(radius_m=914.4))

    def discover(self, items=None):
        response = io.BytesIO(json.dumps(dict(items=items or [])).encode())
        with patch.object(fp, "scene_run", return_value=self.run), patch.object(
            worker, "geographic_box", return_value=[0, 0, 1, 1]
        ), patch.object(scene_sources, "imagery_plan", return_value=[]), patch.object(
            worker.urllib.request,
            "urlopen",
            side_effect=(
                (lambda *a, **k: io.BytesIO(response.getvalue()))
                if items is not None
                else OSError("offline")
            ),
        ):
            worker.discover(self.plan["id"])
        return fp.plan(self.plan["id"])

    def test_old_and_new_records_merge_without_losing_candidates_or_provenance(self):
        key, source = cached_record()
        other_key, other = cached_record(url=URL.replace("fixture", "other"))
        other["acquisition"] = scene_sources.lidar_acquisition(other["url"])
        manifest = fp.HOME / "sources/manifest.json"
        write(manifest, {key: source, other_key: other})
        original = manifest.read_bytes()
        items = [
            dict(
                downloadURL=s["url"],
                sizeInBytes=s["bytes"],
                title=s["title"],
                boundingBox=s["bounds"],
            )
            for s in [source, source, other]
        ]
        plan = self.discover(items)
        self.assertTrue(plan["prepared"])
        self.assertEqual(len(plan["sources"]), 2)
        self.assertEqual(plan["acquisitions"], ["/project"])
        self.assertEqual(plan["estimated_new_bytes"], 0)
        for s in plan["sources"]:
            self.assertTrue(s["cached"])
            self.assertEqual(s["candidates"], ["X", "Y"])
            self.assertEqual(s["remaining_bytes"], 0)
            self.assertIn("vertical_reference", s)
        self.assertEqual(manifest.read_bytes(), original)

    def test_offline_cache_retains_all_setup_associations(self):
        key, source = cached_record()
        write(fp.HOME / "sources/manifest.json", {key: source})
        plan = self.discover()
        self.assertEqual(plan["sources"][0]["candidates"], ["X", "Y"])
        self.assertEqual(plan["coverage"], dict(X=1, Y=1))
        self.assertIn("offline", plan["source_note"])

    def test_unidentifiable_cache_is_excluded_with_reason(self):
        key, source = cached_record(url="https://unknown.example/fixture.laz")
        write(fp.HOME / "sources/manifest.json", {key: source})
        plan = self.discover()
        self.assertTrue(plan["prepared"])
        self.assertEqual(plan["sources"], [])
        self.assertIn("Unrecognized USGS lidar source URL", plan["source_note"])

    def test_corrupt_cached_payload_still_fails_integrity_check(self):
        key, source = cached_record()
        write(fp.HOME / "sources/manifest.json", {key: source})
        (fp.HOME / "sources" / key).write_bytes(b"other")
        with self.assertRaises(ValueError):
            self.discover()

    def test_legacy_acquisitions_remain_separate_and_conflicting_identity_is_excluded(
        self,
    ):
        key, source = cached_record()
        other_key, other = cached_record(
            url=URL.replace("/project/", "/other-project/")
        )
        conflict_key, conflict = cached_record(url=URL.replace("fixture", "conflict"))
        conflict["acquisition"] = "/wrong-project"
        write(
            fp.HOME / "sources/manifest.json",
            {key: source, other_key: other, conflict_key: conflict},
        )
        plan = self.discover()
        self.assertEqual(len(plan["sources"]), 1)
        self.assertEqual(len(plan["acquisitions"]), 2)
        self.assertEqual(plan["sources"][0]["acquisition"], plan["acquisition"])
        self.assertIn("conflicts with its source URL", plan["source_note"])

    def test_catalog_size_change_cannot_reuse_old_payload(self):
        key, source = cached_record()
        write(fp.HOME / "sources/manifest.json", {key: source})
        item = dict(
            downloadURL=source["url"],
            sizeInBytes=source["bytes"] + 1,
            title=source["title"],
            boundingBox=source["bounds"],
        )
        with self.assertRaisesRegex(ValueError, "size differs from catalog"):
            self.discover([item])

    def test_partial_cached_coverage_keeps_missing_tile_in_transfer_estimate(self):
        key, source = cached_record()
        write(fp.HOME / "sources/manifest.json", {key: source})
        missing = dict(
            downloadURL=URL.replace("fixture", "missing"),
            sizeInBytes=123,
            title="Missing tile",
            boundingBox=source["bounds"],
        )
        plan = self.discover([missing])
        self.assertEqual(len(plan["sources"]), 2)
        self.assertEqual(plan["estimated_new_bytes"], 123)
        self.assertTrue(plan["review_signature"])

    def test_unprepared_plan_has_no_cached_download_time(self):
        self.assertNotIn("download_time", scene_storage.review(self.plan))

    def test_incomplete_cached_metadata_has_an_explicit_reason(self):
        key, source = cached_record()
        for value in [
            None,
            dict(source, url=None),
            dict(source, bounds=None),
            dict(source, sha256=None),
            dict(source, bounds=dict(minX=float("nan"))),
        ]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                scene_sources.cached_lidar(value, key)


class LidarSceneRecovery(unittest.TestCase):
    setUpClass = classmethod(workflow_fixture.WorkflowJourney.setUpClass.__func__)
    tearDownClass = classmethod(workflow_fixture.WorkflowJourney.tearDownClass.__func__)
    setUp = workflow_fixture.WorkflowJourney.setUp

    def test_legacy_cache_prepares_nonempty_foliage_and_refinable_ground(self):
        worker.publish(self.r, self.cid, [])
        prior = fp.scene(self.run, self.cid)
        self.assertFalse(prior["fine_observer_available"])
        plan = make_lidar_plan(self.r, self.cid)
        manifest = (fp.HOME / "sources/manifest.json").read_bytes()
        with patch.object(fp, "LIMIT", fp.LIMIT), patch.object(
            worker.urllib.request,
            "urlopen",
            side_effect=AssertionError("cached preparation must not download"),
        ):
            worker.prepare(plan["id"], False, plan["review_signature"])
        scene = fp.scene(self.run, self.cid)
        self.assertNotEqual(scene["key"], prior["key"])
        self.assertTrue(scene["fine_observer_available"])
        self.assertEqual(scene["fidelity"], "lidar")
        self.assertGreater(scene["raw_local_point_count"], 0)
        self.assertGreater(scene["above_ground_point_count"], 0)
        self.assertGreater(scene["vegetation"]["nearby_counts"]["120"], 0)
        for radius in ("30", "60", "120"):
            self.assertGreater(
                scene["vegetation"]["meshes"][radius]["scenarios"]["dense"][
                    "triangle_count"
                ],
                0,
            )
        pose = fp.observer(
            self.run, self.cid, dict(observer_east_m=1, observer_north_m=1)
        )
        self.assertEqual(pose["east_m"], 1)
        self.assertEqual((fp.HOME / "sources/manifest.json").read_bytes(), manifest)
        self.assertTrue((fp.HOME / "bundles" / prior["key"] / "scene.json").exists())


if __name__ == "__main__":
    unittest.main()
