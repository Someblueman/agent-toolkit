"""Cached hook commands cannot reactivate an opted-out repository or event."""

import json

from support import Repository


class HookActivation(Repository):
    def test_configured_unregistered_project_is_entirely_inert(self):
        self.config("raise SystemExit(1)", register=False)
        for content in ((self.root / "quality.json").read_text(), "invalid JSON"):
            (self.root / "quality.json").write_text(content)
            for event in ("UserPromptSubmit", "PostToolUse", "Stop"):
                self.assertEqual(self.hook(event), {})
            self.assertFalse((self.root / "state").exists())

    def test_removing_only_stop_preserves_other_quality_events(self):
        self.config("raise SystemExit(1)")
        hooks = self.root / ".codex/hooks.json"
        data = json.loads(hooks.read_text())
        data["hooks"].pop("Stop")
        hooks.write_text(json.dumps(data))
        self.assertEqual(self.hook("Stop"), {})
        self.assertFalse((self.root / "state").exists())
        self.assertIn("hookSpecificOutput", self.hook("UserPromptSubmit"))
        self.source.write_text("changed = 2\n")
        self.assertIn("FAIL", str(self.hook("PostToolUse")))
        self.assertEqual(self.hook("Stop"), {})
        self.assertEqual(self.hook("Stop", stop_hook_active=True), {})

    def test_unregistration_after_failure_does_not_run_or_write_state(self):
        self.config("raise SystemExit(1)")
        self.assertEqual(self.hook("Stop")["decision"], "block")
        (self.root / ".codex/hooks.json").write_text('{"hooks": {}}')
        state = {p.name: p.read_bytes() for p in (self.root / "state").iterdir()}
        (self.root / "linter.py").unlink()
        for event in ("UserPromptSubmit", "PostToolUse", "Stop"):
            self.assertEqual(self.hook(event), {})
        self.assertEqual(
            {p.name: p.read_bytes() for p in (self.root / "state").iterdir()}, state
        )

    def test_unrelated_stop_hook_does_not_register_quality(self):
        self.config("raise SystemExit(1)", register=False)
        path = self.root / ".codex/hooks.json"
        path.parent.mkdir()
        path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": [
                            {
                                "hooks": [
                                    {"type": "command", "command": "echo other-hook"}
                                ]
                            }
                        ]
                    }
                }
            )
        )
        self.assertEqual(self.hook("Stop"), {})
        self.assertFalse((self.root / "state").exists())
