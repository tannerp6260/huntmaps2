import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import hashlib

from shapely.geometry import LineString, Point, box, mapping, shape
from shapely.ops import transform, unary_union
from glassing.transfer import project
from huntmaps_gui.config import AppConfig, configured
from huntmaps_gui.scouting_network import save_network
from huntmaps_gui.roadless import distant_land, overlay


class RoadlessTests(unittest.TestCase):
    def test_metric_distance_and_query_edge(self):
        area, support = distant_land(
            box(0, 0, 1000, 1000),
            box(-500, -500, 1500, 1500),
            [LineString([(500, -500), (500, 1500)])],
            200,
        )
        self.assertTrue(support.covers(box(0, 0, 1000, 1000)))
        self.assertFalse(area.covers(Point(650, 500)))
        self.assertTrue(area.covers(Point(750, 500)))
        area, _ = distant_land(box(0, 0, 1000, 1000), box(0, 0, 1000, 1000), [], 200)
        self.assertFalse(
            area.covers(Point(100, 500)),
            "Unknown roads beyond the query cannot look roadless",
        )
        self.assertTrue(area.covers(Point(500, 500)))

    def test_adjacent_inventory_tiles_and_offscreen_road(self):
        coverage = unary_union([box(-500, -500, 500, 1500), box(500, -500, 1500, 1500)])
        area, _ = distant_land(
            box(0, 0, 1000, 1000),
            coverage,
            [LineString([(-100, -500), (-100, 1500)])],
            200,
        )
        self.assertTrue(area.covers(Point(500, 500)), "No seam between inventory tiles")
        self.assertFalse(
            area.covers(Point(50, 500)), "Road outside view still affects distance"
        )

    def test_increasing_distance_only_removes_area(self):
        region = box(0, 0, 1000, 1000)
        roads = [LineString([(300, 200), (700, 800)])]
        a, _ = distant_land(region, region.buffer(500), roads, 100)
        b, _ = distant_land(region, region.buffer(500), roads, 300)
        self.assertLess(b.difference(a).area, 1e-6)
        self.assertLess(b.area, a.area)

    def test_sources_trails_unknown_coverage_and_integrity(self):
        with tempfile.TemporaryDirectory() as folder, configured(
            AppConfig(state_dir=Path(folder))
        ):
            ll = project(32613, 4326)
            coverage = list(transform(ll, box(299000, 4279000, 302000, 4282000)).bounds)
            bounds = list(transform(ll, box(300000, 4280000, 301000, 4281000)).bounds)

            def save(kind, x, covered):
                g = transform(ll, LineString([(x, 4279000), (x, 4282000)]))
                return save_network(
                    json.dumps(mapping(g)).encode(),
                    ".geojson",
                    kind,
                    "fixture",
                    coverage=coverage if covered else None,
                )

            save("trails", 300500, True)
            body = dict(bounds=bounds, distance_m=200)
            self.assertEqual(overlay(body)["status"], "unavailable")
            road = save("roads", 300000, False)
            self.assertEqual(overlay(body)["status"], "unavailable")
            save("roads", 300000, True)
            result = overlay(body)
            area = shape(result["features"][0]["geometry"])
            self.assertFalse(area.covers(Point(*ll(300100, 4280500))))
            self.assertTrue(
                area.covers(Point(*ll(300500, 4280500))),
                "Trail does not remove roadless shading",
            )
            original = Path(folder) / "networks" / road["id"] / "original.geojson"
            original.write_text("{}")
            with self.assertRaisesRegex(ValueError, "source changed"):
                overlay(body)

    def test_invalid_distance_and_unbounded_requests(self):
        for distance in (-1, 16094, float("nan"), True, "100"):
            with self.assertRaises(ValueError):
                overlay(dict(bounds=[-107.3, 38.5, -107.2, 38.6], distance_m=distance))
        with self.assertRaisesRegex(ValueError, "Zoom in"):
            overlay(dict(bounds=[-180, -80, 180, 80], distance_m=100))

    def test_unit_boundary_and_additional_imported_road(self):
        with tempfile.TemporaryDirectory() as folder, configured(
            AppConfig(state_dir=Path(folder) / "state")
        ):
            root = Path(folder)
            ll = project(32613, 4326)
            region = transform(ll, box(300000, 4280000, 301000, 4281000))
            coverage = list(transform(ll, box(299000, 4279000, 302000, 4282000)).bounds)
            boundary = root / "boundary.geojson"
            boundary.write_text(
                json.dumps(
                    dict(
                        type="FeatureCollection",
                        features=[
                            dict(
                                type="Feature", properties={}, geometry=mapping(region)
                            )
                        ],
                    )
                )
            )
            roads = root / "roads.geojson"
            roads.write_text(json.dumps(dict(type="FeatureCollection", features=[])))
            manifest = dict(
                epsg=32613,
                boundary=boundary.name,
                networks={"roads": [dict(path=roads.name, bounds=coverage)]},
                assets={
                    p.name: dict(
                        bytes=p.stat().st_size,
                        sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                    )
                    for p in (boundary, roads)
                },
            )
            body = dict(
                bounds=coverage,
                distance_m=100,
                unit_pack=dict(unit_id="fixture", version="v1"),
            )
            with patch(
                "huntmaps_gui.roadless.packs.load", return_value=(root, manifest)
            ):
                before = shape(overlay(body)["features"][0]["geometry"])
                self.assertFalse(
                    before.covers(Point(*ll(301200, 4280500))),
                    "Shading stays within selected GMU",
                )
                self.assertTrue(before.covers(Point(*ll(300500, 4280500))))
                line = transform(ll, LineString([(300500, 4279000), (300500, 4282000)]))
                save_network(
                    json.dumps(mapping(line)).encode(),
                    ".geojson",
                    "roads",
                    "Additional imported road",
                )
                after = shape(overlay(body)["features"][0]["geometry"])
                self.assertFalse(
                    after.covers(Point(*ll(300500, 4280500))),
                    "Imported road counts inside GMU",
                )
                self.assertTrue(after.covers(Point(*ll(300800, 4280500))))


if __name__ == "__main__":
    unittest.main()
