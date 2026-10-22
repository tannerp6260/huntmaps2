"""Real stream faults exercise retained bytes, provider identity and transfer guards."""

import http.client
import io
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from huntmaps_gui import first_person_worker as worker
from huntmaps_gui.config import AppConfig, configured


class LidarTransport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lidar-transport-")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.context = configured(AppConfig(state_dir=self.folder))
        self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)
        self.source = dict(
            key="test.laz",
            title="Test lidar",
            bytes=12,
            url="https://rockyweb.usgs.gov/test.laz",
        )
        self.part = self.folder / "test.partial"
        self.pause = patch.object(worker.time, "sleep")
        self.pause.start()
        self.addCleanup(self.pause.stop)
        self.limit = patch.object(worker.fp, "LIMIT", 1000)
        self.limit.start()
        self.addCleanup(self.limit.stop)

    def stream(self, lo, data, etag='"original"', total=12):
        stream = io.BytesIO(data)
        stream.status, stream.url = 206, self.source["url"]
        stream.headers = {"Content-Range": f"bytes {lo}-11/{total}", "ETag": etag}
        return stream

    def run_piece(self):
        worker.download_piece(self.source, self.part, 0, 11, threading.Lock(), True)

    def test_connection_timeout_retries_then_finishes(self):
        with patch.object(
            worker.urllib.request,
            "urlopen",
            side_effect=[
                urllib.error.URLError(TimeoutError("connect timed out")),
                self.stream(0, b"abcdefghijkl"),
            ],
        ) as request:
            self.run_piece()
        self.assertEqual(request.call_count, 2)
        self.assertEqual(self.part.read_bytes(), b"abcdefghijkl")
        self.assertEqual(worker.read(self.folder / "ledger.json")["received_bytes"], 12)

    def test_midstream_failure_resumes_exact_bytes_and_validator(self):
        first = self.stream(0, b"")
        first.read = lambda _: (_ for _ in ()).throw(
            http.client.IncompleteRead(b"abcd", 8)
        )
        with patch.object(
            worker.urllib.request,
            "urlopen",
            side_effect=[first, self.stream(4, b"efghijkl")],
        ) as request:
            self.run_piece()
        req = request.call_args_list[1].args[0]
        self.assertEqual(req.get_header("Range"), "bytes=4-11")
        self.assertEqual(req.get_header("If-match"), '"original"')
        self.assertEqual(self.part.read_bytes(), b"abcdefghijkl")
        self.assertEqual(worker.read(self.folder / "ledger.json")["received_bytes"], 12)

    def test_exhausted_retry_retains_partial_and_reports_action(self):
        self.part.write_bytes(b"abcd")
        with patch.object(
            worker.urllib.request, "urlopen", side_effect=TimeoutError("timeout")
        ) as request:
            with self.assertRaisesRegex(
                ValueError, "after 3 attempts.*retry detailed view"
            ):
                self.run_piece()
        self.assertEqual(request.call_count, 3)
        self.assertEqual(self.part.read_bytes(), b"abcd")

    def test_bad_range_or_changed_identity_is_not_retried(self):
        with patch.object(
            worker.urllib.request,
            "urlopen",
            return_value=self.stream(0, b"abcdefghijkl", total=13),
        ) as request:
            with self.assertRaisesRegex(ValueError, "exact requested"):
                self.run_piece()
        self.assertEqual(request.call_count, 1)
        self.assertFalse(self.part.exists())
        worker.write(
            self.folder / "test.laz.http.json",
            dict(url=self.source["url"], bytes=12, etag='"old"', modified=None),
        )
        with patch.object(
            worker.urllib.request,
            "urlopen",
            return_value=self.stream(0, b"abcdefghijkl"),
        ) as request:
            with self.assertRaisesRegex(ValueError, "source changed"):
                self.run_piece()
        self.assertEqual(request.call_count, 1)
        self.assertFalse(self.part.exists())

    def test_404_and_exhausted_budget_are_not_retried(self):
        with patch.object(
            worker.urllib.request,
            "urlopen",
            side_effect=urllib.error.HTTPError(
                self.source["url"], 404, "missing", {}, None
            ),
        ) as request:
            with self.assertRaises(urllib.error.HTTPError):
                self.run_piece()
        self.assertEqual(request.call_count, 1)
        with patch.object(worker.fp, "LIMIT", 2), patch.object(
            worker.urllib.request,
            "urlopen",
            return_value=self.stream(0, b"abcdefghijkl"),
        ) as request:
            with self.assertRaisesRegex(ValueError, "transfer allowance"):
                self.run_piece()
        self.assertEqual(request.call_count, 1)
