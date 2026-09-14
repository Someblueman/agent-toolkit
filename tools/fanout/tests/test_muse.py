"""Exercise Muse dispatch, receipt validation, quorum, and bounded execution."""

import json
import os
import signal
import subprocess
import sys
import time
import unittest

from fixtures import FANOUT_BIN, BaseFanoutTestCase
from muse_fixture import create_fake_muse


class MuseHarness(BaseFanoutTestCase):
    def setUp(self):
        super().setUp()
        self.muse = create_fake_muse(self.root / "muse")

    def run_muse(self, mode="success", **kwargs):
        return self.run_fanout(
            harness="muse",
            extra_args=["--muse", str(self.muse)],
            env_vars={"MUSE_TEST_MODE": mode},
            max_output=8192,
            **kwargs,
        )

    def test_default_model_and_real_concurrency(self):
        completed, packet = self.run_muse(workers=4, concurrency=2)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(packet["valid_results"], 4)
        self.assertIsNone(packet["model"])
        self.assertEqual(packet["total_retries"], 0)
        events = []
        for worker in packet["workers"]:
            directory = self.root / "run-muse-success-4-2" / worker["worker_id"]
            args = json.loads((directory / "invocation.json").read_text())
            self.assertNotIn("--model", args)
            self.assertEqual(worker["result"]["payload"], {"evidence": "fixture"})
            self.assertEqual((directory / "stdout.jsonl").stat().st_mode & 0o777, 0o600)
            events.extend(
                [
                    (float((directory / "start").read_text()), 1),
                    (float((directory / "end").read_text()), -1),
                ]
            )
        active = peak = 0
        for _, delta in sorted(events):
            active += delta
            peak = max(peak, active)
        self.assertEqual(peak, 2)
        self.assertEqual(active, 0)

    def test_model_override_and_blocked_quorum(self):
        completed, packet = self.run_muse(
            "partial",
            workers=2,
            concurrency=2,
            min_results=1,
            model="custom-muse-model",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(packet["model"], "custom-muse-model")
        self.assertEqual([w["status"] for w in packet["workers"]], ["ok", "blocked"])
        args = json.loads(
            (self.root / "run-muse-success-2-2/worker-0001/invocation.json").read_text()
        )
        self.assertEqual(args[args.index("--model") + 1], "custom-muse-model")

    def test_invalid_and_failed_workers_never_count_or_retry(self):
        for mode, status in [
            ("malformed", "invalid_result"),
            ("wrong_id", "invalid_result"),
            ("missing_terminal", "invalid_result"),
            ("nonzero", "nonzero_exit"),
            ("oversized", "oversized_output"),
        ]:
            with self.subTest(mode=mode):
                completed, packet = self.run_muse(mode, output_dir=self.root / mode)
                self.assertEqual(completed.returncode, 1)
                self.assertEqual(packet["valid_results"], 0)
                self.assertEqual(packet["workers"][0]["status"], status)
                self.assertEqual(packet["workers"][0]["attempt_count"], 1)

    def assert_pids_gone(self, path):
        for pid in map(int, path.read_text().split()):
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_timeout_cleans_up_worker_and_descendant(self):
        completed, packet = self.run_muse("hang", timeout=1.1)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(packet["workers"][0]["status"], "timeout")
        self.assert_pids_gone(self.root / "run-muse-success-1-1/worker-0001/pids")

    def test_sigterm_cleans_up_worker_and_descendant(self):
        output = self.root / "cancelled"
        process = subprocess.Popen(
            [
                sys.executable,
                str(FANOUT_BIN),
                str(self.prompt),
                "--harness",
                "muse",
                "--muse",
                str(self.muse),
                "--workers",
                "1",
                "--output",
                str(output),
            ],
            env={**os.environ, "MUSE_TEST_MODE": "hang"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            pids = output / "worker-0001/pids"
            deadline = time.monotonic() + 5
            while not pids.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(pids.exists())
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=6)
            self.assertEqual(process.returncode, 2)
            self.assert_pids_gone(pids)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


if __name__ == "__main__":
    unittest.main()
