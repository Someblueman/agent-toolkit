"""Regression checks for worker database isolation and OS launch failures."""

import asyncio
import contextlib
import io
import json
import sys
import unittest
from unittest import mock

from fixtures import BaseFanoutTestCase, load_fanout_module


class OpenCodeRuntime(BaseFanoutTestCase):
    def test_port_permission_error_keeps_successful_sibling_and_packet(self):
        fanout = load_fanout_module()
        output = self.root / "permission-error"
        argv = [
            "fanout",
            str(self.prompt),
            "--harness",
            "opencode",
            "--workers",
            "2",
            "--min-results",
            "1",
            "--output",
            str(output),
            "--opencode",
            str(self.fake_opencode),
            "--node",
            str(self.fake_node),
            "--opencode-sdk",
            str(self.fake_sdk),
            "--working-directory",
            str(self.root),
        ]
        with mock.patch.object(sys, "argv", argv):
            args = fanout.parse_args()
        with (
            mock.patch.object(
                fanout,
                "available_tcp_port",
                side_effect=[PermissionError(1, "Operation not permitted"), 12345],
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = asyncio.run(fanout.run(args))
        packet = json.loads((output / "packet.json").read_text())
        self.assertEqual(code, 0)
        self.assertEqual(
            [w["status"] for w in packet["workers"]], ["runner_error", "ok"]
        )
        self.assertIn(
            "Operation not permitted", packet["workers"][0]["attempts"][0]["error"]
        )

    def test_each_worker_gets_its_own_database(self):
        source = self.fake_node.read_text()
        source = source.replace(
            'agent = get_arg("--agent", "plan")',
            """agent = get_arg("--agent", "plan")
import sqlite3
from pathlib import Path
db_path = Path(os.environ["OPENCODE_DB"])
assert db_path.parent.name == worker_id
connection = sqlite3.connect(db_path, timeout=0)
connection.execute("BEGIN EXCLUSIVE")
time.sleep(0.1)
connection.close()
""",
        )
        self.fake_node.write_text(source)
        completed, packet = self.run_fanout(
            harness="opencode", workers=4, concurrency=4
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(packet["valid_results"], 4)
        files = list(
            (self.root / "run-opencode-success-4-4").glob("worker-*/opencode.db")
        )
        self.assertEqual(len(files), 4)

    def test_exec_format_failure_still_writes_all_worker_receipts(self):
        self.fake_node.write_text("this is not an executable format\n")
        completed, packet = self.run_fanout(
            harness="opencode", workers=2, concurrency=2
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["valid_results"], 0)
        self.assertEqual([w["status"] for w in packet["workers"]], ["runner_error"] * 2)
        self.assertIn("OSError", packet["workers"][0]["attempts"][0]["error"])


if __name__ == "__main__":
    unittest.main()
