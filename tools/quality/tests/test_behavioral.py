"""Run real unittest/CLI behavior through lifecycle events, without a check command."""

import json
import sys

from support import Repository


class BehavioralHooks(Repository):
    def setUp(self):
        super().setUp()
        self.program()
        (self.root / "expected.txt").write_text("ready")
        config = self.config()
        config["tools"] = {
            "python": {
                "command": [sys.executable, "-B"],
                "version_args": ["--version"],
                "version": sys.version.split()[0],
                "install": [],
            }
        }
        config["checks"] = []
        for stage, argument in (("fast", ""), ("full", "--detail")):
            directory = self.root / stage
            directory.mkdir()
            (directory / "test_cli.py").write_text(
                "import subprocess, sys, unittest\nfrom pathlib import Path\n"
                "class Behavior(unittest.TestCase):\n"
                " def test_cli(self):\n"
                f"  with Path('executions').open('a') as log: log.write('{stage}\\n')\n"
                f"  result = subprocess.run([sys.executable, 'src/example.py', '{argument}'], "
                "capture_output=True, text=True, check=True)\n"
                "  expected = "
                + ("'detail'" if argument else "Path('expected.txt').read_text()")
                + "\n"
                "  self.assertEqual(result.stdout.strip(), expected)\n"
            )
            config["checks"].append(
                {
                    "name": stage + " behavior",
                    "kind": "test",
                    "tool": "python",
                    "args": ["-m", "unittest", "discover", "-s", stage, "-v"],
                    "patterns": ["src/*.py"],
                    "files": False,
                    "scope": "project",
                    "stage": stage,
                    "failure_codes": [1],
                    "inputs": [stage + "/*", "expected.txt"]
                    if stage == "fast"
                    else [stage + "/*"],
                }
            )
        self.write_config(config)

    def program(self, ready="ready", detail="detail"):
        self.source.write_text(
            f"import sys\nprint({detail!r} if '--detail' in sys.argv else {ready!r})\n"
        )

    def records(self):
        path = next((self.root / "state").glob("*.jsonl"))
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_behavioral_regression_and_repair_via_hooks(self):
        self.hook("UserPromptSubmit")
        self.assertFalse((self.root / "executions").exists())
        self.program(ready="broken")
        output = self.hook("PostToolUse")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("FAIL fast behavior", output)
        self.assertIn("AssertionError", output)
        self.assertEqual((self.root / "executions").read_text(), "fast\n")
        self.assertEqual(self.hook("Stop")["decision"], "block")
        self.program(ready="ready", detail="detail")
        # Keep a real edit relative to the initial baseline after repair.
        self.source.write_text(self.source.read_text() + "# repaired\n")
        self.assertIn(
            "PASS", self.hook("PostToolUse")["hookSpecificOutput"]["additionalContext"]
        )
        self.assertEqual(self.hook("Stop", stop_hook_active=True), {})
        self.assertEqual(self.records()[-1]["outcome"], "pass")
        self.assertEqual(self.records()[-1]["cached_checks"], 1)
        self.assertEqual(self.records()[-1]["stage"], "full")

    def test_fast_success_and_steering_prompt_cannot_skip_acceptance(self):
        self.hook("UserPromptSubmit")
        self.program(detail="broken")
        self.assertIn(
            "PASS fast behavior",
            self.hook("PostToolUse")["hookSpecificOutput"]["additionalContext"],
        )
        self.hook("UserPromptSubmit")
        result = self.hook("Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("FAIL full behavior", result["reason"])
        self.assertEqual((self.root / "executions").read_text(), "fast\nfull\n")

    def test_initial_snapshot_does_not_hide_existing_test_failures(self):
        self.program(detail="broken before the prompt")
        self.hook("UserPromptSubmit")
        result = self.hook("Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("FAIL full behavior", result["reason"])
        self.assertIn("AssertionError", result["reason"])

    def test_dependency_and_test_edits_invalidate_cached_results(self):
        self.hook("UserPromptSubmit")
        self.program(ready="updated")
        (self.root / "expected.txt").write_text("updated")
        self.hook("PostToolUse")
        self.assertEqual(self.hook("Stop"), {})
        self.hook("UserPromptSubmit")
        (self.root / "expected.txt").write_text("different")
        result = self.hook("PostToolUse")
        self.assertIn(
            "FAIL fast behavior", result["hookSpecificOutput"]["additionalContext"]
        )
        (self.root / "expected.txt").write_text("updated")
        test = self.root / "full/test_cli.py"
        test.write_text(
            test.read_text().replace("expected = 'detail'", "expected = 'different'")
        )
        result = self.hook("Stop")
        self.assertIn("FAIL full behavior", result["reason"])
