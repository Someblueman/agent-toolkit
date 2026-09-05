import json

from support import Repository


class HookTests(Repository):
    def test_read_only_turn_is_inert(self):
        self.config("raise SystemExit(1)")
        self.assertEqual(self.hook("UserPromptSubmit"), {})
        self.assertEqual(self.hook("Stop"), {})

    def test_failure_continues_once_then_reports(self):
        self.config("raise SystemExit(1)")
        self.hook("UserPromptSubmit")
        self.source.write_text("changed = 2\n")
        post = self.hook("PostToolUse")
        self.assertIn("FAIL", post["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.hook("PostToolUse"), {})
        self.assertEqual(self.hook("Stop")["decision"], "block")
        self.hook(
            "UserPromptSubmit"
        )  # Automatic continuation must not erase pending check.
        final = self.hook("Stop", stop_hook_active=True)
        self.assertNotIn("decision", final)
        self.assertIn("still fail", final["systemMessage"])

    def test_fixed_continuation_passes(self):
        self.config("raise SystemExit(1)")
        self.hook("UserPromptSubmit")
        self.source.write_text("changed = 2\n")
        self.assertEqual(self.hook("Stop")["decision"], "block")
        self.config()
        self.assertEqual(self.hook("Stop", stop_hook_active=True), {})

    def test_missing_tool_does_not_trigger_repair_loop(self):
        config = self.config()
        self.hook("UserPromptSubmit")
        config["tools"]["native"]["command"] = ["/missing"]
        self.write_config(config)
        result = self.hook("Stop")
        self.assertNotIn("decision", result)
        self.assertIn("not a pass", result["systemMessage"])

    def test_no_config_is_inert(self):
        self.assertEqual(self.hook("Stop"), {})

    def test_install_preserves_hooks_and_is_idempotent(self):
        self.config()
        destination = self.root / ".codex"
        destination.mkdir()
        path = destination / "hooks.json"
        original = {
            "hooks": {
                "Stop": [{"hooks": [{"type": "command", "command": "echo existing"}]}]
            }
        }
        path.write_text(json.dumps(original))
        self.assertEqual(self.cli("install-codex", "--dry-run").returncode, 0)
        self.assertEqual(json.loads(path.read_text()), original)
        self.assertEqual(self.cli("install-codex").returncode, 0)
        installed = path.read_text()
        self.assertEqual(len(json.loads(installed)["hooks"]["Stop"]), 2)
        self.assertEqual(self.cli("install-codex").returncode, 0)
        self.assertEqual(path.read_text(), installed)

    def test_conflicting_adapter_is_not_replaced(self):
        self.config()
        self.cli("install-codex")
        path = self.root / ".codex/hooks.json"
        old = path.read_text().replace("quality.py", "different/quality.py")
        path.write_text(old)
        self.assertEqual(self.cli("install-codex").returncode, 2)
        self.assertEqual(path.read_text(), old)
