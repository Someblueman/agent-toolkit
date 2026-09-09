import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from support import HOOK, Repository


class WorktreeTests(Repository):
    def invoke(self, root, event):
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(
                {
                    "cwd": str(root),
                    "session_id": "shared-session",
                    "hook_event_name": event,
                }
            ),
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
            env=dict(os.environ, QUALITY_HOOK_STATE_DIR=str(self.root / "state")),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_linked_worktree_uses_own_baseline_cache_lock_and_tools(self):
        config = self.config(
            "from pathlib import Path; Path('calls').open('a').write('checked\\n')"
        )
        config["tools"]["native"]["command"][-1] = "{root}/linter.py"
        self.write_config(config)
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        worktree = Path(other.name) / "linked"
        for args in (
            ["init", "-q"],
            ["add", "src", "linter.py", "quality.json"],
            [
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
            ["worktree", "add", "--detach", str(worktree)],
        ):
            subprocess.run(
                ["git", "-C", str(self.root), *args], check=True, capture_output=True
            )
        self.assertTrue((worktree / ".git").is_file())
        self.invoke(self.root, "UserPromptSubmit")
        self.invoke(worktree, "UserPromptSubmit")
        self.source.write_text("value = 2\n")
        (worktree / "src/example.py").write_text("value = 2\n")
        lock_path = (
            self.root
            / "state"
            / (hashlib.sha256(str(self.root.resolve()).encode()).hexdigest() + ".lock")
        )
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            busy = self.invoke(self.root, "Stop")
            self.assertIn("already running", busy["systemMessage"])
            self.assertEqual(self.invoke(worktree, "Stop"), {})
            self.assertFalse((self.root / "calls").exists())
        self.assertEqual(self.invoke(self.root, "Stop"), {})
        self.assertEqual((self.root / "calls").read_text(), "checked\n")
        self.assertEqual((worktree / "calls").read_text(), "checked\n")
        self.assertEqual(len(list((self.root / "state").glob("*.checks.json"))), 2)
        self.invoke(worktree, "UserPromptSubmit")
        (worktree / "linter.py").unlink()
        (worktree / "src/example.py").write_text("value = 3\n")
        missing = self.invoke(worktree, "Stop")
        self.assertIn("not a pass", missing["systemMessage"])
        self.assertEqual((self.root / "calls").read_text(), "checked\n")
