"""Tier 1 & Tier 2 tests: Schema validation, atomic packet writes, provenance, and aggregate rollups."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path

# Ensure tests directory is on sys.path
TESTS_DIR = str(Path(__file__).resolve().parent)
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

try:
    from .fixtures import (
        BaseFanoutTestCase,
        FANOUT_BIN,
        SCHEMA_PATH,
        load_fanout_module,
    )
except ImportError:
    from fixtures import (
        BaseFanoutTestCase,
        FANOUT_BIN,
        SCHEMA_PATH,
        load_fanout_module,
    )


class TestAgySchemaValidation(unittest.TestCase):
    """Unit tests for Agy worker result validation."""

    def setUp(self) -> None:
        self.fanout = load_fanout_module()

    def test_valid_agy_result_passes(self) -> None:
        valid_result = {
            "worker_id": "worker-0001",
            "summary": "Valid summary within limits",
            "findings": ["Finding 1", "Finding 2"],
            "uncertainties": ["Uncertainty 1"],
        }
        err = self.fanout.validate_agy_result(valid_result, "worker-0001")
        self.assertIsNone(err)

    def test_unexpected_or_missing_keys_rejected(self) -> None:
        # Extra key
        with_extra = {
            "worker_id": "worker-0001",
            "summary": "Valid summary",
            "findings": [],
            "uncertainties": [],
            "extra_field": "disallowed",
        }
        self.assertIsNotNone(self.fanout.validate_agy_result(with_extra, "worker-0001"))

        # Missing key
        missing_key = {
            "worker_id": "worker-0001",
            "summary": "Valid summary",
            "findings": [],
        }
        self.assertIsNotNone(self.fanout.validate_agy_result(missing_key, "worker-0001"))

    def test_mismatched_worker_id_rejected(self) -> None:
        result = {
            "worker_id": "worker-9999",
            "summary": "Valid summary",
            "findings": [],
            "uncertainties": [],
        }
        err = self.fanout.validate_agy_result(result, "worker-0001")
        self.assertIsNotNone(err)
        self.assertIn("worker_id", err)

    def test_summary_length_bounds(self) -> None:
        # Empty summary
        empty_sum = {
            "worker_id": "worker-0001",
            "summary": "",
            "findings": [],
            "uncertainties": [],
        }
        self.assertIsNotNone(self.fanout.validate_agy_result(empty_sum, "worker-0001"))

        # Oversized summary (> 2000 chars)
        long_sum = {
            "worker_id": "worker-0001",
            "summary": "a" * 2001,
            "findings": [],
            "uncertainties": [],
        }
        self.assertIsNotNone(self.fanout.validate_agy_result(long_sum, "worker-0001"))

    def test_findings_and_uncertainties_bounds(self) -> None:
        # More than 10 findings
        too_many_findings = {
            "worker_id": "worker-0001",
            "summary": "Valid summary",
            "findings": [f"finding {i}" for i in range(11)],
            "uncertainties": [],
        }
        self.assertIsNotNone(self.fanout.validate_agy_result(too_many_findings, "worker-0001"))

        # Finding exceeding 500 chars
        oversized_finding = {
            "worker_id": "worker-0001",
            "summary": "Valid summary",
            "findings": ["x" * 501],
            "uncertainties": [],
        }
        self.assertIsNotNone(self.fanout.validate_agy_result(oversized_finding, "worker-0001"))

        # Empty string finding
        empty_finding = {
            "worker_id": "worker-0001",
            "summary": "Valid summary",
            "findings": [""],
            "uncertainties": [],
        }
        self.assertIsNotNone(self.fanout.validate_agy_result(empty_finding, "worker-0001"))


class TestOpenCodeReceiptValidation(unittest.TestCase):
    """Unit tests for OpenCode universal receipt validation and payload decoding."""

    def setUp(self) -> None:
        self.fanout = load_fanout_module()

    def test_valid_opencode_receipt_decodes_payload(self) -> None:
        receipt = {
            "worker_id": "worker-0001",
            "outcome": "completed",
            "summary": "Task completed successfully",
            "result_json": json.dumps({"custom_key": "custom_value", "items": [1, 2, 3]}),
        }
        decoded, err = self.fanout.validate_opencode_receipt(receipt, "worker-0001")
        self.assertIsNone(err)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["worker_id"], "worker-0001")
        self.assertEqual(decoded["outcome"], "completed")
        self.assertEqual(decoded["summary"], "Task completed successfully")
        self.assertEqual(decoded["payload"]["custom_key"], "custom_value")
        self.assertEqual(decoded["payload"]["items"], [1, 2, 3])

    def test_invalid_outcome_rejected(self) -> None:
        receipt = {
            "worker_id": "worker-0001",
            "outcome": "unknown_status",
            "summary": "Task status unknown",
            "result_json": "{}",
        }
        decoded, err = self.fanout.validate_opencode_receipt(receipt, "worker-0001")
        self.assertIsNone(decoded)
        self.assertIsNotNone(err)
        self.assertIn("outcome", err)

    def test_non_json_or_non_dict_result_json_rejected(self) -> None:
        # Not JSON
        receipt_not_json = {
            "worker_id": "worker-0001",
            "outcome": "completed",
            "summary": "Task completed",
            "result_json": "raw string not json",
        }
        decoded, err = self.fanout.validate_opencode_receipt(receipt_not_json, "worker-0001")
        self.assertIsNone(decoded)
        self.assertIn("valid json", err.lower())

        # JSON array instead of JSON object (dict)
        receipt_array = {
            "worker_id": "worker-0001",
            "outcome": "completed",
            "summary": "Task completed",
            "result_json": json.dumps([1, 2, 3]),
        }
        decoded, err = self.fanout.validate_opencode_receipt(receipt_array, "worker-0001")
        self.assertIsNone(decoded)
        self.assertIn("json object", err.lower())


class TestPacketProvenanceAndPermissions(BaseFanoutTestCase):
    """Test atomic write, file modes, prompt hashing, and rollups in packet.json."""

    def test_atomic_packet_write_and_permissions(self) -> None:
        completed, packet = self.run_fanout("success", workers=2, concurrency=2)
        self.assertEqual(completed.returncode, 0, completed.stderr)

        output_dir = self.root / "run-agy-success-2-2"
        # Directory permissions: 0700
        dir_mode = stat.S_IMODE(output_dir.stat().st_mode)
        self.assertEqual(dir_mode, 0o700)

        # packet.json permissions: 0600
        packet_path = output_dir / "packet.json"
        self.assertTrue(packet_path.is_file())
        file_mode = stat.S_IMODE(packet_path.stat().st_mode)
        self.assertEqual(file_mode, 0o600)

        # Worker subdirectory permissions: 0700
        worker_dir = output_dir / "worker-0001"
        self.assertEqual(stat.S_IMODE(worker_dir.stat().st_mode), 0o700)

        # Attempt subdirectory and artifact permissions: 0700 / 0600
        attempt_dir = worker_dir / "attempt-1"
        self.assertEqual(stat.S_IMODE(attempt_dir.stat().st_mode), 0o700)
        stdout_path = attempt_dir / "stdout.json"
        self.assertTrue(stdout_path.is_file())
        self.assertEqual(stat.S_IMODE(stdout_path.stat().st_mode), 0o600)

    def test_prompt_sha256_provenance(self) -> None:
        custom_prompt = self.root / "custom_task.md"
        prompt_content = "# Highly Specific Task Prompt\nUnique token: XYZ-98765\n"
        custom_prompt.write_text(prompt_content, encoding="utf-8")
        expected_sha = hashlib.sha256(prompt_content.encode("utf-8")).hexdigest()

        completed, packet = self.run_fanout("success", prompt_file=custom_prompt)
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["prompt_sha256"], expected_sha)
        self.assertEqual(packet["prompt_path"], str(custom_prompt.resolve()))

    def test_aggregate_token_and_cost_rollups(self) -> None:
        # Agy run rollups
        completed, packet = self.run_fanout("success", workers=3, concurrency=3)
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["schema_version"], 3)
        self.assertEqual(packet["requested_workers"], 3)
        self.assertEqual(packet["valid_results"], 3)
        self.assertIn("total_tokens", packet)
        if packet.get("total_tokens") is not None:
            self.assertEqual(packet["total_tokens"], 3 * 150)

        # OpenCode run rollups
        completed_oc, packet_oc = self.run_fanout("success", harness="opencode", workers=2, concurrency=2)
        self.assertEqual(completed_oc.returncode, 0)
        self.assertIsNotNone(packet_oc)
        self.assertIn("total_tokens", packet_oc)
        self.assertIn("total_cost_usd", packet_oc)
        if packet_oc.get("total_cost_usd") is not None:
            self.assertAlmostEqual(packet_oc["total_cost_usd"], 0.02, places=4)


if __name__ == "__main__":
    unittest.main()
