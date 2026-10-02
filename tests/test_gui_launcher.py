"""Port checks must allow recently closed servers and reject live listeners."""

import socket
import os
import tempfile
import unittest
from unittest.mock import patch

from huntmaps_gui.__main__ import main


class LauncherTests(unittest.TestCase):
    def launch(self, port, state):
        with patch(
            "sys.argv",
            ["huntmaps-gui", "--no-browser", "--port", str(port), "--state-dir", state],
        ), patch.dict(os.environ), patch("uvicorn.run") as run:
            main()
            run.assert_called_once()

    def test_restart_with_connection_in_time_wait(self):
        with tempfile.TemporaryDirectory() as state:
            with socket.socket() as listener:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
                listener.listen()
                with socket.create_connection(("127.0.0.1", port)) as client:
                    connection, _ = listener.accept()
                    connection.close()
                    self.assertEqual(client.recv(1), b"")
            # Verify this fixture actually reproduces the old launcher's failure.
            with socket.socket() as probe:
                with self.assertRaises(OSError):
                    probe.bind(("127.0.0.1", port))
            self.launch(port, state)

    def test_live_listener_is_rejected(self):
        with tempfile.TemporaryDirectory() as state, socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            with self.assertRaisesRegex(SystemExit, "Cannot bind"):
                self.launch(listener.getsockname()[1], state)
