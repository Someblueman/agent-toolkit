"""Optional account-backed review qualification through the actual Codex CLI."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from quality_lib.review_scope import git
from support import HOOK, Repository


@unittest.skipUnless(
    "review" in os.environ.get("QUALITY_NATIVE", "").split(","),
    "set QUALITY_NATIVE=review; uses Codex account quota",
)
class NativeReview(Repository):
    def test_native_luna_finds_regression_across_commits_once(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        state = Path(directory.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "Probe")
        git(self.root, "config", "user.email", "probe@example.invalid")
        config = self.config()
        config["verification"].update(
            green="average([]) returns 0 and nonempty averages are correct.",
            review=True,
        )
        self.write_config(config)
        self.source.write_text(
            "def average(values):\n    if not values:\n        return 0\n    return sum(values) / len(values)\n"
        )
        (self.root / "README.md").write_text(
            "average([]) must return 0; average([2, 4]) must return 3.\n"
        )
        (self.root / "AGENTS.md").write_text(
            "Review only this small repository and the exact supplied diff. No memory or external research is needed.\n"
        )
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "baseline")
        (self.root / "preexisting.txt").write_text(
            "User scratch; unchanged by the task.\n"
        )

        def event(name, **fields):
            result = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps(
                    {
                        "cwd": str(self.root),
                        "session_id": "native-review",
                        "hook_event_name": name,
                        **fields,
                    }
                ),
                text=True,
                capture_output=True,
                check=True,
                timeout=1000,
                env=dict(os.environ, QUALITY_HOOK_STATE_DIR=str(state)),
            )
            return json.loads(result.stdout)

        event(
            "UserPromptSubmit",
            prompt="Document and simplify average, preserving its empty-input behavior. Review the complete work across both commits.",
        )
        with (self.root / "README.md").open("a") as readme:
            readme.write("Inputs are lists of numbers.\n")
        git(self.root, "add", "README.md")
        git(self.root, "commit", "-qm", "document inputs")
        self.source.write_text(
            "def average(values):\n    return sum(values) / len(values)\n"
        )
        git(self.root, "add", "src/example.py")
        git(self.root, "commit", "-qm", "simplify average")
        result = event("Stop")
        self.assertEqual(result.get("decision"), "block", result)
        self.assertIn("review completed", result["reason"])
        self.assertRegex(result["reason"].lower(), "empty|zerodivision")
        self.assertNotIn("preexisting.txt", result["reason"])
        artifacts = next(state.glob("*.review"))
        events = (artifacts / "events.jsonl").read_bytes()
        self.source.write_text(
            "def average(values):\n    return sum(values) / len(values) if values else 0\n"
        )
        self.assertNotIn("decision", event("Stop", stop_hook_active=True))
        self.assertEqual((artifacts / "events.jsonl").read_bytes(), events)
