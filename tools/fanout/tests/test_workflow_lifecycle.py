"""Workflow cancellation kills the worker process group and its descendants."""

import os
import signal
import subprocess
import sys
import textwrap
import time
import unittest

from fixtures import FANOUT_BIN
from workflow_fixture import WorkflowCase, member


class WorkflowLifecycle(WorkflowCase):
    def test_sigterm_cleans_worker_and_child(self):
        self.configure([member("one", "claude")])
        pids = self.root / "pids"
        self.executables["claude"].write_text(
            f"#!{sys.executable}\n"
            + textwrap.dedent(f"""\
            import os, signal, subprocess, sys, time
            from pathlib import Path
            child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
            def stop(signum,frame):
                child.wait(timeout=3)
                sys.exit(0)
            signal.signal(signal.SIGTERM,stop)
            Path({str(pids)!r}).write_text(str(os.getpid())+' '+str(child.pid))
            time.sleep(60)
        """)
        )
        process = subprocess.Popen(
            [
                sys.executable,
                str(FANOUT_BIN),
                str(self.prompt),
                "--workflow",
                "review-plan",
                "--config",
                str(self.config),
                "--working-directory",
                str(self.cwd),
                "--output",
                str(self.output),
                "--claude",
                str(self.executables["claude"]),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 5
            while not pids.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(pids.exists())
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=6)
            self.assertEqual(process.returncode, 2)
            for pid in map(int, pids.read_text().split()):
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


if __name__ == "__main__":
    unittest.main()
