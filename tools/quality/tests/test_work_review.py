"""Lifecycle integration through real hook and reviewer subprocess boundaries."""

import json
import os
import sys
from unittest.mock import patch

from quality_lib.review_scope import git
from support import HOOK, Repository


class ReviewRepository(Repository):
    def setUp(self):
        super().setUp()
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "Probe")
        git(self.root, "config", "user.email", "probe@example.invalid")
        (self.root / ".gitignore").write_text("state/\nbin/\ncodex-home/\n")
        config = self.config()
        config["verification"]["review"] = True
        self.write_config(config)
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "baseline")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.bin / "calls.jsonl"
        self.environment = patch.dict(
            os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"]
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.reviewer()

    def reviewer(self, extra=""):
        executable = self.bin / "codex"
        executable.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, subprocess, sys\n"
            f"calls = pathlib.Path({str(self.calls)!r})\n"
            "with calls.open('a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')\n"
            "assert os.environ['QUALITY_REVIEW_CHILD'] == '1'\n"
            "prompt = sys.stdin.read()\n"
            "assert 'Exact diff command:' in prompt\n"
            f"child = subprocess.run([{sys.executable!r}, {str(HOOK)!r}], input=json.dumps(dict(cwd=os.getcwd(),session_id='child',hook_event_name='Stop')), text=True, capture_output=True, check=True)\n"
            "assert json.loads(child.stdout) == {}\n" + extra + "\n"
            "pathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text('P2: concrete review finding')\n"
        )
        executable.chmod(0o755)

    def changed(self):
        self.hook("UserPromptSubmit", prompt="Change the implementation")
        self.source.write_text("value = 2\n")


class WorkReview(ReviewRepository):
    def test_one_review_after_green_covers_commits_and_preserves_steering(self):
        self.changed()
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "first change")
        self.hook("UserPromptSubmit", prompt="Also update documentation")
        (self.root / "README.md").write_text("new docs\n")
        self.hook(
            "PostToolUse"
        )  # Completion must review even when all checks are cached.
        result = self.hook("Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("review completed", result["reason"])
        args = json.loads(self.calls.read_text())
        self.assertIn("gpt-5.6-luna", args)
        self.assertIn('model_reasoning_effort="max"', args)
        self.assertEqual(args[args.index("--sandbox") + 1], "read-only")
        prompt = next((self.root / "state").glob("*.review/prompt.txt")).read_text()
        self.assertIn("Change the implementation", prompt)
        self.assertIn("Also update documentation", prompt)
        self.source.write_text("fixed = 3\n")
        self.assertNotIn("decision", self.hook("Stop", stop_hook_active=True))
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)
        self.changed()
        self.hook("Stop")
        self.assertEqual(len(self.calls.read_text().splitlines()), 2)

    def test_read_only_work_and_disabled_configuration_do_not_launch(self):
        self.hook("UserPromptSubmit")
        self.assertEqual(self.hook("Stop"), {})
        self.assertFalse(self.calls.exists())
        config = self.config()
        self.assertNotIn("review", config["verification"])
        self.changed()
        self.assertEqual(self.hook("Stop"), {})
        self.assertFalse(self.calls.exists())

    def test_failed_checks_delay_review_until_repaired(self):
        self.changed()
        (self.root / "linter.py").write_text(
            (self.root / "linter.py")
            .read_text()
            .replace("SystemExit(0)", "SystemExit(1)")
        )
        self.assertEqual(self.hook("Stop")["decision"], "block")
        self.assertFalse(self.calls.exists())
        (self.root / "linter.py").write_text(
            (self.root / "linter.py")
            .read_text()
            .replace("SystemExit(1)", "SystemExit(0)")
        )
        self.assertIn(
            "review completed", self.hook("Stop", stop_hook_active=True)["reason"]
        )

    def test_reviewer_failure_and_stale_result_are_not_passes(self):
        for extra, expected in (
            ("raise SystemExit(2)", "incomplete (not a pass)"),
            ("pathlib.Path('README.md').write_text('concurrent edit')", "stale:"),
        ):
            with self.subTest(expected=expected):
                self.reviewer(extra)
                self.changed()
                result = self.hook("Stop")
                self.assertEqual(result["decision"], "block")
                self.assertIn(expected, result["reason"])
                self.hook("Stop", stop_hook_active=True)
                self.source.write_text("next = 9\n")
        self.assertEqual(len(self.calls.read_text().splitlines()), 2)
