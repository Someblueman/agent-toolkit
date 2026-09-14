"""Pi CLI options, terminal receipts, and bounded failures."""

import json
import unittest

from fixtures import BaseFanoutTestCase
from pi_fixture import create_fake_pi


class PiHarness(BaseFanoutTestCase):
    def setUp(self):
        super().setUp()
        self.pi = create_fake_pi(self.root / "pi")

    def run_pi(self, mode="success", **kwargs):
        return self.run_fanout(
            harness="pi",
            extra_args=["--pi", str(self.pi)],
            env_vars={"PI_TEST_MODE": mode},
            max_output=8192,
            **kwargs,
        )

    def test_native_model_default_and_ephemeral_flags(self):
        completed, packet = self.run_pi(workers=2, concurrency=2)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(packet["valid_results"], 2)
        self.assertIsNone(packet["model"])
        self.assertEqual(packet["total_tokens"], 84)
        self.assertEqual(packet["total_cost_usd"], 0.02)
        self.assertEqual(packet["total_retries"], 0)
        args = json.loads(
            (self.root / "run-pi-success-2-2/worker-0001/invocation.json").read_text()
        )
        self.assertNotIn("--model", args)

    def test_model_override_and_partial_quorum(self):
        completed, packet = self.run_pi(
            "partial",
            workers=2,
            concurrency=2,
            min_results=1,
            model="provider/model:high",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([w["status"] for w in packet["workers"]], ["ok", "blocked"])
        args = json.loads(
            (self.root / "run-pi-success-2-2/worker-0001/invocation.json").read_text()
        )
        self.assertEqual(args[args.index("--model") + 1], "provider/model:high")

    def test_errors_and_timeout_never_count_or_retry(self):
        for mode, status in [
            ("malformed", "invalid_result"),
            ("incomplete", "invalid_result"),
            ("nonzero", "nonzero_exit"),
            ("oversized", "oversized_output"),
            ("hang", "timeout"),
        ]:
            with self.subTest(mode=mode):
                completed, packet = self.run_pi(
                    mode, output_dir=self.root / mode, timeout=1.1
                )
                self.assertEqual(completed.returncode, 1)
                self.assertEqual(packet["valid_results"], 0)
                self.assertEqual(packet["workers"][0]["status"], status)
                self.assertEqual(packet["workers"][0]["attempt_count"], 1)


if __name__ == "__main__":
    unittest.main()
