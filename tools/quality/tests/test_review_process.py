"""Time bounds and interruption cleanup for the native reviewer process group."""

import json
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
from quality_lib.work_review import run_review
from support import HOOK
from test_work_review import ReviewRepository


class ReviewProcess(ReviewRepository):
    def test_interrupted_hook_does_not_repeat_review(self):
        self.reviewer(
            "pathlib.Path('bin/started').touch(); import time; time.sleep(60)"
        )
        self.changed()
        process = subprocess.Popen(
            [sys.executable, str(HOOK)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=dict(os.environ, QUALITY_HOOK_STATE_DIR=str(self.root / "state")),
        )
        self.addCleanup(lambda: process.poll() is None and process.kill())
        process.stdin.write(
            json.dumps(
                {
                    "cwd": str(self.root),
                    "session_id": "test-session",
                    "hook_event_name": "Stop",
                }
            )
        )
        process.stdin.close()
        deadline = time.monotonic() + 5
        while not (self.bin / "started").exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue((self.bin / "started").exists())
        process.terminate()
        process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()
        self.assertEqual(process.returncode, 128 + signal.SIGTERM)
        result = self.hook("Stop", stop_hook_active=True)
        self.assertNotIn("decision", result)
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)


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
