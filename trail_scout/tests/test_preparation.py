"""Actual HTTP failure/retry fixture; never labeled as real area source evidence."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlparse, parse_qs

from trail_scout.preparation import prepare
from trail_scout.storage import Paths, read


class Acquisition(unittest.TestCase):
    def test_provider_failure_atomic_resume_and_retained_original_attributes(self):
        requests = []
        failure = [True]

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                requests.append(self.path)
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                if parsed.path.endswith("/query") and "returnCountOnly" in query:
                    value = dict(count=1)
                elif parsed.path.endswith("/query"):
                    if failure[0]:
                        self.send_error(503, "Labeled provider-unavailable fixture")
                        return
                    value = dict(
                        type="FeatureCollection",
                        features=[
                            dict(
                                type="Feature",
                                geometry=dict(
                                    type="LineString",
                                    coordinates=[[-107.31, 38.66], [-107.30, 38.67]],
                                ),
                                properties=dict(
                                    objectid=123,
                                    unexpected_attribute="preserved fixture",
                                    truck="open",
                                    truck_datesopen="01/01-12/31",
                                ),
                            )
                        ],
                    )
                else:
                    name = (
                        "National Forest System Roads closed to motorized uses"
                        if "RoadBasic" in parsed.path
                        else (
                            "Motor Vehicle Use Map: Trails"
                            if parsed.path.endswith("/2")
                            else "Motor Vehicle Use Map: Roads"
                        )
                    )
                    value = dict(
                        name=name,
                        geometryType="esriGeometryPolyline",
                        maxRecordCount=2000,
                    )
                data = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                paths = Paths(state=Path(tmp))
                folder = paths.state / "imports" / "33333333333333333333333333333333"
                body = dict(longitude=-107.31, latitude=38.66, radius_m=5000)
                base = f"http://127.0.0.1:{server.server_port}"
                with self.assertRaises(Exception):
                    prepare(paths, body, folder, lambda *a: None, lambda: None, base)
                self.assertFalse((paths.state / "imports/active.json").exists())
                self.assertTrue((folder / "closed_roads-metadata.json").exists())
                first_bytes = read(folder / "transfer.json")["received_bytes"]
                self.assertGreater(first_bytes, 0)
                metadata_requests = len(
                    [
                        p
                        for p in requests
                        if "returnCountOnly" not in p and "/query" not in p
                    ]
                )
                failure[0] = False
                result = prepare(
                    paths, body, folder, lambda *a: None, lambda: None, base
                )
                self.assertEqual(
                    result["published"]["closed_roads"]["complete_inventory_count"], 1
                )
                self.assertEqual(
                    read(folder / "closed_roads.geojson")["features"][0]["properties"][
                        "unexpected_attribute"
                    ],
                    "preserved fixture",
                )
                self.assertGreater(
                    read(folder / "transfer.json")["received_bytes"], first_bytes
                )
                # The first validated metadata/count pieces are reused on retry.
                self.assertEqual(
                    len(
                        [
                            p
                            for p in requests
                            if "returnCountOnly" not in p and "/query" not in p
                        ]
                    ),
                    metadata_requests + 2,
                )
                self.assertEqual(len(read(paths.state / "imports/active.json")), 3)
                active_before = read(paths.state / "imports/active.json")
                (folder / "closed_roads.geojson").write_text("{}")
                with self.assertRaises(ValueError):
                    prepare(paths, body, folder, lambda *a: None, lambda: None, base)
                self.assertEqual(
                    read(paths.state / "imports/active.json"), active_before
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
