"""Lifecycle integration through real hook and reviewer subprocess boundaries."""

import json
import os
import sys
import time
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

    def visible(self, *args):
        with patch.dict(os.environ, self.review_environment()):
            return self.cli("review", *args)

    def review_environment(self):
        return {
            "CODEX_THREAD_ID": "test-session",
            "QUALITY_HOOK_STATE_DIR": str(self.root / "state"),
        }


class WorkReview(ReviewRepository):
    def test_stop_never_launches_and_assessment_requires_current_report(self):
        self.changed()
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "first change")
        self.hook("UserPromptSubmit", prompt="Also update documentation")
        (self.root / "README.md").write_text("new docs\n")
        self.hook("PostToolUse")
        started = time.monotonic()
        result = self.hook("Stop")
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(result["decision"], "block")
        self.assertIn("Run visibly", result["reason"])
        self.assertFalse(self.calls.exists())
        self.assertEqual(self.visible("--accept", "premature").returncode, 2)
        result = self.visible()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        args = json.loads(self.calls.read_text())
        self.assertIn("gpt-5.6-luna", args)
        self.assertIn('model_reasoning_effort="max"', args)
        self.assertEqual(args[args.index("--sandbox") + 1], "read-only")
        prompt = next((self.root / "state").glob("*.review/prompt.txt")).read_text()
        self.assertIn("Change the implementation", prompt)
        self.assertIn("Also update documentation", prompt)
        self.assertIn(
            "not accepted", self.hook("Stop", stop_hook_active=True)["systemMessage"]
        )
        self.assertEqual(
            self.visible("--accept", "Fixture report assessed").returncode, 0
        )
        self.assertEqual(self.hook("Stop", stop_hook_active=True), {})
        self.assertEqual(self.hook("Stop"), {})
        self.assertEqual(self.visible().returncode, 0)
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)
        self.source.write_text("fixed = 3\n")
        self.assertEqual(self.hook("Stop")["decision"], "block")
        self.assertEqual(self.visible("--accept", "stale").returncode, 2)
        self.assertEqual(
            self.visible("--accept", "stale", "--same-scope").returncode, 2
        )
        self.assertEqual(self.visible().returncode, 0)
        self.assertEqual(self.visible("--accept", "New report assessed").returncode, 0)
        self.assertEqual(self.hook("Stop"), {})
        self.assertEqual(len(self.calls.read_text().splitlines()), 2)

    def test_read_only_work_and_disabled_configuration_do_not_launch(self):
        self.hook("UserPromptSubmit")
        self.assertEqual(self.hook("Stop"), {})
        self.assertFalse(self.calls.exists())
        self.config()  # Rewrites configuration without review enabled.
        self.changed()
        self.assertEqual(self.hook("Stop"), {})
        self.assertFalse(self.calls.exists())

    def test_accepted_review_does_not_override_native_failures(self):
        self.changed()
        (self.root / "linter.py").write_text(
            (self.root / "linter.py")
            .read_text()
            .replace("SystemExit(0)", "SystemExit(1)")
        )
        self.assertEqual(self.visible().returncode, 0)
        self.assertEqual(self.visible("--accept", "Fixture assessed").returncode, 0)
        result = self.hook("Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("verification failed", result["reason"])

    def test_failure_staleness_and_report_tampering_block_acceptance(self):
        for extra, expected in (
            ("raise SystemExit(2)", "incomplete"),
            ("pathlib.Path('README.md').write_text('concurrent edit')", "stale"),
        ):
            with self.subTest(expected=expected):
                self.reviewer(extra)
                self.changed()
                result = self.visible()
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn(expected, result.stdout)
                self.assertEqual(self.visible("--accept", "invalid").returncode, 2)
                self.assertIn(
                    "not accepted", str(self.hook("Stop", stop_hook_active=True))
                )
        self.reviewer()
        self.assertEqual(self.visible().returncode, 0)
        report = next((self.root / "state").glob("*.review/report.md"))
        report.write_text("replacement")
        self.assertEqual(self.visible("--accept", "tampered").returncode, 2)
        self.assertIn("not accepted", str(self.hook("Stop")))

    def test_session_identity_and_missing_opening_snapshot(self):
        self.assertIn("No opening review snapshot", self.visible().stdout)
        self.changed()
        result = self.visible("--session", "another-task")
        self.assertEqual(result.returncode, 2)
        self.assertIn("differs", result.stdout)
        self.assertFalse(self.calls.exists())
        self.assertEqual(self.visible("--same-scope").returncode, 2)

    def test_unavailable_review_continues_once_without_false_acceptance(self):
        self.changed()
        self.assertEqual(self.hook("Stop")["decision"], "block")
        for fields in ({"stop_hook_active": True}, {}, {}):
            result = self.hook("Stop", **fields)
            self.assertNotIn("decision", result)
            self.assertIn("incomplete and not accepted", result["systemMessage"])
        self.assertFalse(self.calls.exists())
        self.assertEqual(self.visible("--accept", "No report").returncode, 2)
        records = next((self.root / "state").glob("*.jsonl")).read_text().splitlines()
        self.assertEqual(json.loads(records[-1])["outcome"], "review_incomplete")
