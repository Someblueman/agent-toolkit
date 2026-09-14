"""Claude Code CLI, receipt boundary, and bounded execution tests."""

import json
import unittest

from claude_fixture import create_fake_claude
from fixtures import BaseFanoutTestCase, load_fanout_module

load_fanout_module()
from claude_worker import parse_claude_output


class ClaudeHarness(BaseFanoutTestCase):
    def setUp(self):
        super().setUp()
        self.claude = create_fake_claude(self.root / "claude")

    def run_claude(self, mode="success", **kwargs):
        return self.run_fanout(
            harness="claude",
            extra_args=["--claude", str(self.claude)],
            env_vars={"CLAUDE_TEST_MODE": mode},
            max_output=8192,
            **kwargs,
        )

    def test_native_default_stdin_context_and_usage(self):
        completed, packet = self.run_claude(workers=2, concurrency=2)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(packet["valid_results"], 2)
        self.assertIsNone(packet["model"])
        self.assertEqual(packet["total_tokens"], 84)
        self.assertEqual(packet["total_cost_usd"], 0.02)
        self.assertEqual(packet["total_retries"], 0)
        payload = packet["workers"][0]["result"]["payload"]
        self.assertIsNone(payload["model"])
        self.assertEqual(payload["cwd"], str(self.root.resolve()))
        self.assertIn(self.prompt.read_text().strip(), payload["prompt"])

    def test_model_override_and_partial_quorum(self):
        completed, packet = self.run_claude(
            "partial", workers=2, concurrency=2, min_results=1, model="sonnet"
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([w["status"] for w in packet["workers"]], ["ok", "blocked"])
        self.assertEqual(packet["workers"][0]["result"]["payload"]["model"], "sonnet")
        self.assertEqual(packet["model"], "sonnet")

    def test_errors_and_timeout_never_count_or_retry(self):
        for mode, status in [
            ("malformed", "invalid_result"),
            ("nonzero", "nonzero_exit"),
            ("oversized", "oversized_output"),
            ("hang", "timeout"),
        ]:
            with self.subTest(mode=mode):
                completed, packet = self.run_claude(
                    mode, output_dir=self.root / mode, timeout=1.1
                )
                self.assertEqual(completed.returncode, 1)
                self.assertEqual(packet["valid_results"], 0)
                self.assertEqual(packet["workers"][0]["status"], status)
                self.assertEqual(packet["workers"][0]["attempt_count"], 1)


class ClaudeResults(unittest.TestCase):
    def test_only_successful_structured_receipts_count(self):
        receipt = {
            "worker_id": "worker-0001",
            "outcome": "completed",
            "summary": "Checked",
            "result_json": '{"answer":42}',
        }
        envelope = {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "structured_output": receipt,
        }
        result, usage, error = parse_claude_output(
            json.dumps(envelope).encode(), "worker-0001"
        )
        self.assertIsNone(error)
        self.assertEqual(result["payload"], {"answer": 42})
        self.assertNotIn("total_tokens", usage)
        for patch in [
            {"type": "assistant"},
            {"is_error": True},
            {"is_error": None},
            {"subtype": "error_max_turns"},
            {"subtype": "error_during_execution"},
            {"subtype": "error_max_structured_output_retries"},
            {"structured_output": None, "result": json.dumps(receipt)},
            {"structured_output": {**receipt, "worker_id": "worker-0002"}},
            {"structured_output": {**receipt, "result_json": {"answer": 42}}},
            {"structured_output": {**receipt, "extra": "field"}},
        ]:
            with self.subTest(patch=patch):
                _, _, error = parse_claude_output(
                    json.dumps({**envelope, **patch}).encode(), "worker-0001"
                )
                self.assertIsNotNone(error)
        for output in (
            b"[]",
            b"{}",
            b"not json",
            b"\xff",
            json.dumps([envelope]).encode(),
        ):
            self.assertIsNotNone(parse_claude_output(output, "worker-0001")[2])


if __name__ == "__main__":
    unittest.main()
