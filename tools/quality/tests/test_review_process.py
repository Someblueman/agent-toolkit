"""Real CLI cancellation, timeout, lock ownership and late-result boundaries."""

import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from quality_lib.config import SetupError
from quality_lib.review_process import run_review
from support import CLI
from test_work_review import ReviewRepository


def await_file(path):
    deadline = time.monotonic() + 5
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not path.exists():
        raise AssertionError(f"Process did not reach barrier: {path}")


def stop(process):
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=5)


class ReviewProcess(ReviewRepository):
    def start(self):
        process = subprocess.Popen(
            [sys.executable, str(CLI), "--root", str(self.root), "review"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=dict(os.environ, **self.review_environment()),
        )
        self.addCleanup(stop, process)
        await_file(self.bin / "started")
        return process

    def test_caller_signals_kill_reviewer_and_grandchild_and_release_lock(self):
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGKILL):
            with self.subTest(signal=sig):
                (self.bin / "started").unlink(missing_ok=True)
                self.reviewer(
                    "subprocess.Popen([sys.executable, '-c', "
                    "\"import pathlib,time; pathlib.Path('bin/started').touch(); "
                    "time.sleep(1); pathlib.Path('bin/escaped').touch()\"], start_new_session=True); "
                    "import time; time.sleep(60)"
                )
                self.changed()
                process = self.start()
                process.send_signal(sig)
                output, errors = process.communicate(timeout=5)
                self.assertIn("Review running visibly", output, errors)
                expected = -sig if sig == signal.SIGKILL else 128 + sig
                self.assertEqual(process.returncode, expected, output + errors)
                time.sleep(1.1)
                self.assertFalse((self.bin / "escaped").exists())
                self.assertIn(
                    "not accepted", str(self.hook("Stop", stop_hook_active=True))
                )
                self.assertEqual(self.visible("--accept", "interrupted").returncode, 2)
                self.reviewer()
                result = self.visible()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_changed_requirements_need_review_and_other_checks_can_proceed(self):
        self.reviewer("pathlib.Path('bin/started').touch(); import time; time.sleep(1)")
        self.changed()
        process = self.start()
        self.assertIn("already has a running review", self.visible().stdout)
        result = self.hook("PostToolUse", session_id="another-session")
        self.assertNotIn("busy", str(result))
        self.hook("UserPromptSubmit", prompt="New acceptance requirement")
        output, errors = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, output + errors)
        self.assertIn("Review completed", output)
        self.assertEqual(self.visible("--accept", "old requirement").returncode, 2)
        self.reviewer()
        self.assertEqual(self.visible().returncode, 0)
        self.assertEqual(
            self.visible("--accept", "Current findings assessed").returncode, 0
        )
        self.assertEqual(self.hook("Stop"), {})

    def test_status_message_can_reuse_in_flight_review_with_explicit_assessment(self):
        self.reviewer("pathlib.Path('bin/started').touch(); import time; time.sleep(1)")
        self.changed()
        process = self.start()
        self.hook("UserPromptSubmit", prompt="Is the review still running?")
        output, errors = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, output + errors)
        self.assertEqual(self.visible("--accept", "Assessed findings").returncode, 2)
        result = self.visible(
            "--accept",
            "Findings assessed; the status question changed no requirements",
            "--same-scope",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.hook("Stop"), {})
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)

    def test_caller_death_keeps_review_locked_until_cleanup_finishes(self):
        self.reviewer(
            "pathlib.Path('bin/supervisor').write_text(str(os.getppid())); "
            "pathlib.Path('bin/started').touch(); import time; time.sleep(60)"
        )
        self.changed()
        process = self.start()
        supervisor = int((self.bin / "supervisor").read_text())
        os.kill(supervisor, signal.SIGSTOP)
        try:
            process.kill()
            process.wait(timeout=5)
            self.assertIn("already has a running review", self.visible().stdout)
        finally:
            os.kill(supervisor, signal.SIGCONT)
        self.reviewer()
        deadline = time.monotonic() + 5
        while True:
            result = self.visible()
            if "already has a running review" not in result.stdout:
                break
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.02)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ReviewTimeout(unittest.TestCase):
    def test_timeout_kills_reviewer_and_its_child(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            binary = root / "codex"
            binary.write_text(
                f"#!{sys.executable}\n"
                "import os,pathlib,subprocess,sys,time\n"
                "child=subprocess.Popen([sys.executable,'-c',\"import pathlib,time; time.sleep(1); pathlib.Path('escaped').touch()\"])\n"
                "pathlib.Path('started').touch()\n"
                "time.sleep(60)\n"
            )
            binary.chmod(0o755)
            with (
                patch.dict(
                    os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"]
                ),
                self.assertRaisesRegex(SetupError, "timed out"),
            ):
                run_review(root, root / "report", "review", timeout=0.4)
            self.assertTrue((root / "started").exists())
            time.sleep(1.1)
            self.assertFalse((root / "escaped").exists())
