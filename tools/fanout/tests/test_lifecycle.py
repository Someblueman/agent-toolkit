"""Tier 1, Tier 2 & Tier 3 tests: Process-group isolation, timeouts, signals, retries, and cleanup."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

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


class TestProcessLifecycle(BaseFanoutTestCase):
    """Test process-group creation, isolation, signal propagation, and cascaded cleanup."""

    def test_hung_worker_times_out_and_terminates(self) -> None:
        """Verify that a worker that hangs exceeds timeout_seconds and is terminated."""
        completed, packet = self.run_fanout("hang", timeout=1.1, workers=1, concurrency=1)
        self.assertEqual(completed.returncode, 1)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["valid_results"], 0)
        worker = packet["workers"][0]
        self.assertEqual(worker["status"], "timeout")
        self.assertEqual(worker["attempt_count"], 2)  # Default retries=1: 1 original + 1 retry = 2 attempts
        self.assertEqual(packet["total_retries"], 1)
        self.assertEqual(
            [att["status"] for att in worker["attempts"]],
            ["timeout", "timeout"],
        )

    def test_cancelling_async_worker_terminates_child_process_group(self) -> None:
        """Unit test for asyncio task cancellation terminating the child process group."""
        fanout_mod = load_fanout_module()
        output = self.root / "cancelled_async"
        output.mkdir(parents=True, exist_ok=True)
        pid_path = self.root / "fake-agy.pid"

        async def scenario() -> None:
            semaphore = asyncio.Semaphore(1)
            env_patch = {
                "FAKE_AGY_MODE": "hang",
                "FAKE_AGY_PID_PATH": str(pid_path),
            }
            with mock.patch.dict(os.environ, env_patch):
                task = asyncio.create_task(
                    fanout_mod.run_agy_attempt(
                        worker_id="worker-0001",
                        attempt=1,
                        semaphore=semaphore,
                        agy_path=str(self.fake_agy),
                        model="gemini-3.7-flash-low",
                        base_prompt="Review only.",
                        working_directory=self.root,
                        output=output,
                        timeout_seconds=20.0,
                        max_output_bytes=1024,
                    )
                )
                # Wait for child process to start and write PID
                child_pid = None
                for _ in range(100):
                    if pid_path.exists():
                        try:
                            text = pid_path.read_text().strip()
                            if text:
                                child_pid = int(text)
                                break
                        except (ValueError, OSError):
                            pass
                    await asyncio.sleep(0.02)
                self.assertIsNotNone(child_pid, "fake-agy PID file was not created or empty")

                # Child process is alive
                os.kill(child_pid, 0)

                # Cancel the supervisor task
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

                # Allow grace period for signal delivery and process reaping
                for _ in range(50):
                    try:
                        os.kill(child_pid, 0)
                        await asyncio.sleep(0.05)
                    except ProcessLookupError:
                        break
                else:
                    self.fail(f"Child process {child_pid} was not terminated after task cancellation")

        asyncio.run(scenario())

    def test_parent_sigterm_terminates_child_process_group(self) -> None:
        """E2E test: sending OS SIGTERM to parent fanout CLI terminates child process group."""
        pid_path = self.root / "worker-sigterm.pid"
        output_dir = self.root / "run-parent-sigterm"
        environment = os.environ.copy()
        environment["FAKE_AGY_MODE"] = "hang"
        environment["FAKE_AGY_PID_PATH"] = str(pid_path)

        command = [
            sys.executable,
            str(FANOUT_BIN),
            str(self.prompt),
            "--harness", "agy",
            "--workers", "1",
            "--concurrency", "1",
            "--timeout-seconds", "30",
            "--output", str(output_dir),
            "--agy", str(self.fake_agy),
        ]

        parent_proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )

        try:
            # Wait for fake-agy to write its PID
            child_pid = None
            for _ in range(100):
                if pid_path.exists():
                    try:
                        text = pid_path.read_text().strip()
                        if text:
                            child_pid = int(text)
                            break
                    except Exception:
                        pass
                time.sleep(0.05)

            self.assertIsNotNone(child_pid, "Child worker process PID was not recorded")
            # Child process must be running
            os.kill(child_pid, 0)

            # Send SIGTERM to the parent process
            parent_proc.send_signal(signal.SIGTERM)
            try:
                parent_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                parent_proc.kill()
                parent_proc.wait(timeout=2)
                self.fail("Parent fanout process did not exit within 5s after receiving SIGTERM")

            # Verify child worker process was terminated
            for _ in range(50):
                try:
                    os.kill(child_pid, 0)
                    time.sleep(0.05)
                except ProcessLookupError:
                    break
            else:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self.fail(f"Child process {child_pid} was orphaned after parent received SIGTERM")

        finally:
            if parent_proc.poll() is None:
                parent_proc.kill()
                parent_proc.wait()
            if parent_proc.stdout is not None:
                parent_proc.stdout.close()
            if parent_proc.stderr is not None:
                parent_proc.stderr.close()


class TestBoundedRetries(BaseFanoutTestCase):
    """Test retry policies for transient vs fatal errors across harnesses."""

    def test_transient_timeout_retries_once_and_succeeds(self) -> None:
        completed, packet = self.run_fanout("retry_success", timeout=1.1, workers=1, concurrency=1)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["valid_results"], 1)
        worker = packet["workers"][0]
        self.assertEqual(worker["status"], "ok")
        self.assertEqual(worker["attempt_count"], 2)
        self.assertEqual(
            [attempt["status"] for attempt in worker["attempts"]],
            ["timeout", "ok"],
        )
        worker_dir = self.root / "run-agy-retry_success-1-1" / "worker-0001"
        self.assertTrue((worker_dir / "attempt-1" / "stdout.json").is_file())
        self.assertTrue((worker_dir / "attempt-2" / "stdout.json").is_file())

    def test_transient_nonzero_retries_once_and_fails(self) -> None:
        completed, packet = self.run_fanout("nonzero", retries=1)
        self.assertEqual(completed.returncode, 1)
        self.assertIsNotNone(packet)
        worker = packet["workers"][0]
        self.assertEqual(worker["status"], "nonzero_exit")
        self.assertEqual(worker["attempt_count"], 2)
        self.assertEqual(packet["total_retries"], 1)
        self.assertTrue(all(att["returncode"] == 7 for att in worker["attempts"]))

    def test_retries_disabled_stops_after_first_transient_failure(self) -> None:
        completed, packet = self.run_fanout("nonzero", retries=0)
        self.assertEqual(completed.returncode, 1)
        self.assertIsNotNone(packet)
        worker = packet["workers"][0]
        self.assertEqual(worker["status"], "nonzero_exit")
        self.assertEqual(worker["attempt_count"], 1)
        self.assertEqual(packet["total_retries"], 0)

    def test_fatal_errors_do_not_retry(self) -> None:
        """Deterministic schema/size errors fail immediately without retry."""
        for fatal_mode, expected_status in (
            ("malformed", "malformed_output"),
            ("oversized", "oversized_output"),
        ):
            with self.subTest(mode=fatal_mode):
                completed, packet = self.run_fanout(fatal_mode, retries=1)
                self.assertEqual(completed.returncode, 1)
                self.assertIsNotNone(packet)
                worker = packet["workers"][0]
                self.assertEqual(worker["status"], expected_status)
                self.assertEqual(worker["attempt_count"], 1)
                self.assertEqual(packet["total_retries"], 0)


class TestConcurrencyThrottling(BaseFanoutTestCase):
    """Test that worker concurrency semaphore limits in-flight executions."""

    def test_concurrency_semaphore_limits_in_flight_workers(self) -> None:
        pid_dir = self.root / "concurrency_pids"
        pid_dir.mkdir(parents=True, exist_ok=True)
        completed, packet = self.run_fanout(
            "success",
            workers=4,
            concurrency=2,
            env_vars={"FAKE_AGY_PID_PATH": str(pid_dir)},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIsNotNone(packet)
        self.assertEqual(packet["valid_results"], 4)
        self.assertEqual(packet["concurrency"], 2)
        self.assertEqual(packet["requested_workers"], 4)


if __name__ == "__main__":
    unittest.main()
