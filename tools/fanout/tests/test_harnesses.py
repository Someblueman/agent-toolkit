"""Tier 3 & Tier 4 tests: Agy harness, OpenCode harness, and K-of-N Quorum thresholding."""

from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path

# Ensure tests directory is on sys.path
TESTS_DIR = str(Path(__file__).resolve().parent)
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

try:
    from .fixtures import (
        BaseFanoutTestCase,
        FANOUT_BIN,
    )
except ImportError:
    from fixtures import (
        BaseFanoutTestCase,
        FANOUT_BIN,
    )


class TestAgyHarness(BaseFanoutTestCase):
    """End-to-end integration tests for Agy / Gemini harness execution."""

    def test_successes_collected_in_deterministic_worker_order(self) -> None:
        completed, packet = self.run_fanout("success", workers=4, concurrency=2)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["harness"], "agy")
        self.assertEqual(packet["model"], "gemini-3.7-flash-low")
        self.assertEqual(packet["valid_results"], 4)
        self.assertEqual(
            [w["worker_id"] for w in packet["workers"]],
            ["worker-0001", "worker-0002", "worker-0003", "worker-0004"],
        )
        self.assertTrue(all(w["status"] == "ok" for w in packet["workers"]))
        for worker in packet["workers"]:
            self.assertIn("result", worker)
            self.assertEqual(worker["result"]["worker_id"], worker["worker_id"])
            self.assertIn("summary", worker["result"])
            self.assertIsInstance(worker["result"]["findings"], list)

    def test_custom_model_override_passed_to_agy(self) -> None:
        completed, packet = self.run_fanout(
            "success",
            workers=1,
            model="gemini-2.5-pro",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["model"], "gemini-2.5-pro")

    def test_log_file_created_with_private_permissions(self) -> None:
        completed, packet = self.run_fanout("success", workers=1)
        self.assertEqual(completed.returncode, 0)
        output_dir = self.root / "run-agy-success-1-1"
        log_path = output_dir / "worker-0001" / "attempt-1" / "agy.log"
        # If created by agy
        if log_path.is_file():
            self.assertEqual(stat.S_IMODE(log_path.stat().st_mode), 0o600)


class TestOpenCodeHarness(BaseFanoutTestCase):
    """End-to-end integration tests for OpenCode SDK v2 helper and receipt protocol."""

    def test_opencode_receipt_supports_selected_agent_and_dynamic_payload(self) -> None:
        completed, packet = self.run_fanout(
            "success",
            harness="opencode",
            agent="build",
            workers=2,
            concurrency=2,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["harness"], "opencode")
        self.assertEqual(packet["model"], "opencode-go/minimax-m3")
        self.assertEqual(packet["agent"], "build")
        self.assertEqual(packet["valid_results"], 2)

        worker = packet["workers"][0]
        self.assertEqual(worker["status"], "ok")
        self.assertEqual(worker["result"]["worker_id"], "worker-0001")
        self.assertEqual(worker["result"]["outcome"], "completed")
        self.assertEqual(worker["result"]["payload"]["kind"], "task-specific")
        self.assertEqual(worker["result"]["payload"]["selected_agent"], "build")
        self.assertIn("recommendations", worker["result"]["payload"])

    def test_opencode_blocked_outcome_retained_in_evidence_but_not_counted_towards_quorum(self) -> None:
        completed, packet = self.run_fanout(
            "blocked",
            harness="opencode",
            workers=1,
        )
        # Blocked worker does not count as "ok" -> quorum of 1 fails -> exit 1
        self.assertEqual(completed.returncode, 1)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["valid_results"], 0)
        worker = packet["workers"][0]
        self.assertEqual(worker["status"], "blocked")
        self.assertEqual(worker["result"]["outcome"], "blocked")

    def test_opencode_failed_outcome_retained_in_evidence_but_not_counted(self) -> None:
        completed, packet = self.run_fanout(
            "failed",
            harness="opencode",
            workers=1,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["valid_results"], 0)
        worker = packet["workers"][0]
        self.assertEqual(worker["status"], "failed")
        self.assertEqual(worker["result"]["outcome"], "failed")

    def test_opencode_malformed_receipt_or_invalid_payload_rejected(self) -> None:
        for bad_mode in ("malformed", "invalid", "bad_payload"):
            with self.subTest(mode=bad_mode):
                completed, packet = self.run_fanout(bad_mode, harness="opencode")
                self.assertEqual(completed.returncode, 1)
                self.assertIsNotNone(packet)
                self.assertEqual(packet["valid_results"], 0)
                worker = packet["workers"][0]
                self.assertIn(worker["status"], {"invalid_result", "malformed_output"})

    def test_opencode_nonzero_helper_exit_recorded(self) -> None:
        completed, packet = self.run_fanout("nonzero", harness="opencode")
        self.assertEqual(completed.returncode, 1)
        self.assertIsNotNone(packet)
        worker = packet["workers"][0]
        self.assertEqual(worker["status"], "nonzero_exit")


class TestQuorumThresholding(BaseFanoutTestCase):
    """Test K-of-N quorum evaluation, exit code mapping, and stdout summary emission."""

    def test_all_workers_succeed_satisfies_default_quorum(self) -> None:
        completed, packet = self.run_fanout("success", workers=3, concurrency=3)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["min_results"], 3)
        self.assertEqual(packet["valid_results"], 3)
        # Stdout must contain JSON summary
        summary = json.loads(completed.stdout.strip())
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["valid_results"], 3)
        self.assertEqual(summary["requested_workers"], 3)

    def test_partial_success_satisfies_explicit_lower_quorum(self) -> None:
        # 2 workers: worker-0001 succeeds, worker-0002 fails with nonzero exit
        # min_results=1 -> satisfied -> exit code 0
        completed, packet = self.run_fanout(
            "partial",
            workers=2,
            concurrency=2,
            min_results=1,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["valid_results"], 1)
        self.assertEqual(packet["min_results"], 1)
        self.assertEqual(
            [w["status"] for w in packet["workers"]],
            ["ok", "nonzero_exit"],
        )
        summary = json.loads(completed.stdout.strip())
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["valid_results"], 1)

    def test_partial_success_fails_strict_default_quorum(self) -> None:
        # Default min_results=2 -> only 1 valid result -> exit code 1
        completed, packet = self.run_fanout(
            "partial",
            workers=2,
            concurrency=2,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["valid_results"], 1)
        self.assertEqual(packet["min_results"], 2)
        summary = json.loads(completed.stdout.strip())
        self.assertEqual(summary["status"], "insufficient_results")
        self.assertEqual(summary["valid_results"], 1)


if __name__ == "__main__":
    unittest.main()
