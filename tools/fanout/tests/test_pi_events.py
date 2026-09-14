"""Pi's authoritative terminal message must be complete and schema-valid."""

import copy
import json
import unittest

from fixtures import load_fanout_module

load_fanout_module()
from pi_worker import parse_pi_output


class PiEvents(unittest.TestCase):
    def setUp(self):
        receipt = {
            "worker_id": "worker-0001",
            "outcome": "completed",
            "summary": "Done",
            "result_json": '{"answer":42}',
        }
        self.message = {
            "role": "assistant",
            "stopReason": "stop",
            "content": [{"type": "text", "text": json.dumps(receipt)}],
            "usage": {"totalTokens": 10, "cost": {"total": 0.02}},
        }
        self.terminal = {
            "type": "agent_end",
            "messages": [self.message],
            "willRetry": False,
        }

    def parse(self, events):
        return parse_pi_output(
            b"\n".join(json.dumps(e).encode() for e in events), "worker-0001"
        )

    def test_final_receipt_and_usage(self):
        result, usage, error = self.parse([self.terminal])
        self.assertIsNone(error)
        self.assertEqual(result["payload"], {"answer": 42})
        self.assertEqual(usage, {"total_tokens": 10, "cost": 0.02})

    def test_streamed_or_interrupted_output_does_not_count(self):
        cases = [
            [{"type": "message_end", "message": self.message}],
            [None],
            [self.terminal, self.terminal],
        ]
        for field, value in [
            ("stopReason", "error"),
            ("stopReason", "aborted"),
            ("stopReason", "length"),
            ("role", "toolResult"),
            ("content", None),
        ]:
            terminal = copy.deepcopy(self.terminal)
            terminal["messages"][0][field] = value
            cases.append([terminal])
        for events in cases:
            with self.subTest(events=events):
                result, _, error = self.parse(events)
                self.assertIsNone(result)
                self.assertIsNotNone(error)

    def test_pending_native_retry_is_not_final(self):
        transient = {"type": "agent_end", "messages": [], "willRetry": True}
        result, _, error = self.parse([transient])
        self.assertIsNone(result)
        self.assertIsNotNone(error)
        result, _, error = self.parse([transient, self.terminal])
        self.assertIsNone(error)
        self.assertEqual(result["outcome"], "completed")


if __name__ == "__main__":
    unittest.main()
