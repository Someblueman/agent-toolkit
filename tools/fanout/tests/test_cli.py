"""Tier 1 & Tier 2 tests: CLI argument parsing, validation, and exit codes."""

from __future__ import annotations

import json
import os
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
        load_fanout_module,
    )
except ImportError:
    from fixtures import (
        BaseFanoutTestCase,
        FANOUT_BIN,
        load_fanout_module,
    )


class TestCliFlagsAndHelp(BaseFanoutTestCase):
    """Test CLI help flags and basic invocation."""

    def test_help_flag_displays_usage_and_exits_zero(self) -> None:
        for flag in ("-h", "--help"):
            with self.subTest(flag=flag):
                result = subprocess.run(
                    [sys.executable, str(FANOUT_BIN), flag],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0)
                self.assertIn("usage:", result.stdout.lower())
                self.assertIn("--harness", result.stdout)
                self.assertIn("--workers", result.stdout)
                self.assertIn("--concurrency", result.stdout)
                self.assertIn("--output", result.stdout)

    def test_missing_all_arguments_exits_code_two(self) -> None:
        result = subprocess.run(
            [sys.executable, str(FANOUT_BIN)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr.lower())

    def test_missing_output_flag_exits_code_two(self) -> None:
        result = subprocess.run(
            [sys.executable, str(FANOUT_BIN), str(self.prompt)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("required", result.stderr.lower())
        self.assertIn("--output", result.stderr.lower())

    def test_missing_prompt_file_positional_exits_code_two(self) -> None:
        output_dir = self.root / "out"
        result = subprocess.run(
            [sys.executable, str(FANOUT_BIN), "--output", str(output_dir)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 2)


class TestCliValidation(BaseFanoutTestCase):
    """Test input validation, parameter bounds checking, and error diagnostics."""

    def test_nonexistent_prompt_file_exits_code_two(self) -> None:
        fake_prompt = self.root / "nonexistent_prompt.md"
        output_dir = self.root / "out"
        completed, _ = self.run_fanout(
            prompt_file=fake_prompt,
            output_dir=output_dir,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("prompt file does not exist", completed.stderr.lower())

    def test_nonexistent_working_directory_exits_code_two(self) -> None:
        nonexistent_dir = self.root / "missing_dir"
        output_dir = self.root / "out"
        completed, _ = self.run_fanout(
            working_directory=nonexistent_dir,
            output_dir=output_dir,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("working directory does not exist", completed.stderr.lower())

    def test_non_empty_output_directory_exits_code_two(self) -> None:
        output_dir = self.root / "non_empty_dir"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "pre_existing_file.txt").write_text("existing data", encoding="utf-8")

        completed, _ = self.run_fanout(output_dir=output_dir)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("output directory is not empty", completed.stderr.lower())

    def test_workers_out_of_bounds(self) -> None:
        for invalid_workers in (0, 51, -1):
            with self.subTest(workers=invalid_workers):
                completed, _ = self.run_fanout(workers=invalid_workers)
                self.assertEqual(completed.returncode, 2)
                self.assertIn("workers must be between 1 and 50", completed.stderr)

    def test_concurrency_default_bounded_by_workers(self) -> None:
        """Verify that invoking --workers 1, 2, 3, 8 without explicit --concurrency parses and validates without error, defaulting to min(4, workers)."""
        fanout = load_fanout_module()
        prompt_path = self.prompt
        output_dir = self.root / "test_out_default_concurrency"

        for workers, expected_concurrency in [(1, 1), (2, 2), (3, 3), (8, 4)]:
            with self.subTest(workers=workers, expected_concurrency=expected_concurrency):
                test_args = [
                    str(prompt_path),
                    "--output",
                    str(output_dir),
                    "--workers",
                    str(workers),
                    "--agy",
                    str(self.fake_agy),
                ]
                orig_argv = sys.argv
                try:
                    sys.argv = ["fanout"] + test_args
                    parsed = fanout.parse_args()
                    self.assertIsNone(parsed.concurrency)
                    fanout.validate_args(parsed)
                    self.assertEqual(parsed.concurrency, expected_concurrency)
                finally:
                    sys.argv = orig_argv

    def test_cli_invocation_with_default_concurrency(self) -> None:
        """Test full CLI subprocess invocations with --workers 1, 2, 3, 8 without --concurrency succeed and record min(4, workers)."""
        for workers, expected_concurrency in [(1, 1), (2, 2), (3, 3), (8, 4)]:
            with self.subTest(workers=workers, expected_concurrency=expected_concurrency):
                out = self.root / f"cli_default_conc_{workers}"
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(FANOUT_BIN),
                        str(self.prompt),
                        "--output",
                        str(out),
                        "--workers",
                        str(workers),
                        "--agy",
                        str(self.fake_agy),
                    ],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(completed.returncode, 0, f"Failed for workers={workers}: {completed.stderr}")
                packet_path = out / "packet.json"
                self.assertTrue(packet_path.is_file())
                packet = json.loads(packet_path.read_text(encoding="utf-8"))
                self.assertEqual(packet["concurrency"], expected_concurrency)
                self.assertEqual(packet["requested_workers"], workers)

    def test_concurrency_out_of_bounds(self) -> None:
        # Concurrency > workers
        completed, _ = self.run_fanout(workers=2, concurrency=3)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("concurrency must be between 1 and --workers", completed.stderr)

        # Concurrency < 1
        completed, _ = self.run_fanout(workers=2, concurrency=0)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("concurrency must be between 1 and --workers", completed.stderr)

    def test_min_results_out_of_bounds(self) -> None:
        # min_results > workers
        completed, _ = self.run_fanout(workers=3, min_results=4)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("min-results must be between 1 and --workers", completed.stderr)

        # min_results < 1
        completed, _ = self.run_fanout(workers=3, min_results=0)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("min-results must be between 1 and --workers", completed.stderr)

    def test_timeout_seconds_out_of_bounds(self) -> None:
        for invalid_timeout in (1.0, 0.5, 0.0, -5.0):
            with self.subTest(timeout=invalid_timeout):
                completed, _ = self.run_fanout(timeout=invalid_timeout)
                self.assertEqual(completed.returncode, 2)
                self.assertIn("timeout-seconds must be greater than 1", completed.stderr)

    def test_max_output_bytes_out_of_bounds(self) -> None:
        for invalid_max in (1023, 500, 0, -100):
            with self.subTest(max_output=invalid_max):
                completed, _ = self.run_fanout(max_output=invalid_max)
                self.assertEqual(completed.returncode, 2)
                self.assertIn("max-output-bytes must be at least 1024", completed.stderr)

    def test_empty_agent_string_validation(self) -> None:
        for empty_agent in ("", "   "):
            with self.subTest(agent=repr(empty_agent)):
                completed, _ = self.run_fanout(
                    harness="opencode",
                    agent=empty_agent,
                )
                self.assertEqual(completed.returncode, 2)
                self.assertIn("agent must not be empty", completed.stderr)

    def test_invalid_harness_choice_rejected(self) -> None:
        output_dir = self.root / "out"
        completed, _ = self.run_fanout(
            harness="invalid_harness",
            output_dir=output_dir,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("invalid choice", completed.stderr.lower())

    def test_agy_retries_forbidden_on_opencode(self) -> None:
        output_dir = self.root / "out"
        completed, _ = self.run_fanout(
            harness="opencode",
            extra_args=["--agy-retries", "1"],
            output_dir=output_dir,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--agy-retries is only valid with --harness agy", completed.stderr)

    def test_unresolvable_executable_exits_code_two(self) -> None:
        output_dir = self.root / "out"
        # Invalid agy executable
        completed, _ = self.run_fanout(
            harness="agy",
            extra_args=["--agy", str(self.root / "missing-agy-exe")],
            output_dir=output_dir,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("executable not found", completed.stderr.lower())


class TestCliExitCodes(BaseFanoutTestCase):
    """Test exit code contracts across success, quorum failure, and CLI errors."""

    def test_exit_code_zero_on_successful_quorum(self) -> None:
        completed, packet = self.run_fanout("success", workers=2, concurrency=2)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["valid_results"], 2)

    def test_exit_code_one_when_quorum_not_met(self) -> None:
        completed, packet = self.run_fanout("nonzero", workers=2, concurrency=2)
        self.assertEqual(completed.returncode, 1)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["valid_results"], 0)

    def test_exit_code_two_on_cli_arg_error(self) -> None:
        completed, _ = self.run_fanout(workers=100)
        self.assertEqual(completed.returncode, 2)


if __name__ == "__main__":
    unittest.main()
