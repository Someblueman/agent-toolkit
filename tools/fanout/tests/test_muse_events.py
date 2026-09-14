"""Parse captured Muse CLI events and reject incomplete or misattributed receipts."""

import copy
import json
import unittest
from pathlib import Path

from fixtures import load_fanout_module

load_fanout_module()
from muse_worker import parse_muse_output


class MuseEvents(unittest.TestCase):
    def setUp(self):
        self.raw = (Path(__file__).parent / "data/muse-completed.jsonl").read_bytes()
        self.records = [json.loads(line) for line in self.raw.splitlines()]

    def parse(self, records):
        return parse_muse_output(
            b"\n".join(json.dumps(r).encode() for r in records), "worker-0001"
        )

    def test_captured_native_completion(self):
        result, usage, error = parse_muse_output(self.raw, "worker-0001")
        self.assertIsNone(error)
        self.assertIsNone(usage)
        self.assertEqual(result["payload"]["evidence"], "fanout-verify-7c824d")

    def test_invalid_or_incomplete_streams(self):
        cases = [
            [None],
            self.records[:1],
            self.records[1:],
            self.records + self.records[-1:],
        ]
        for field, value in [
            ("terminal", "failed"),
            ("text", None),
            ("text", "{}"),
            ("text", "```json\n{}\n```"),
            ("command_id", "different"),
        ]:
            records = copy.deepcopy(self.records)
            records[-1]["payload"][field] = value
            cases.append(records)
        records = copy.deepcopy(self.records)
        records[-1]["payload"] = []
        cases.append(records)
        for records in cases:
            with self.subTest(records=records):
                result, _, error = self.parse(records)
                self.assertIsNone(result)
                self.assertIsNotNone(error)

    def test_child_completion_does_not_count_as_root(self):
        child = copy.deepcopy(self.records[-1])
        child["payload"]["command_id"] = "child-run"
        result, _, error = self.parse([self.records[0], child])
        self.assertIsNone(result)
        self.assertIsNotNone(error)
        result, _, error = self.parse([self.records[0], child, self.records[-1]])
        self.assertIsNone(error)
        self.assertEqual(result["outcome"], "completed")


if __name__ == "__main__":
    unittest.main()
