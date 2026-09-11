import json

from support import Repository


class HookTests(Repository):
    def test_unverified_initial_snapshot_is_checked_at_stop(self):
        self.config("raise SystemExit(1)")
        self.assertIn(
            "Verification preflight", self.hook("UserPromptSubmit")["systemMessage"]
        )
        self.assertEqual(self.hook("Stop")["decision"], "block")

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
        # Unresolved failures must not become an unchanged/passing baseline.
        self.assertIn("still fail", self.hook("Stop")["systemMessage"])

    def test_fixed_continuation_passes(self):
        self.config("raise SystemExit(1)")
        self.hook("UserPromptSubmit")
        self.source.write_text("changed = 2\n")
        self.assertEqual(self.hook("Stop")["decision"], "block")
        self.config()
        self.assertEqual(self.hook("Stop", stop_hook_active=True), {})

    def test_missing_tool_retries_once_then_reports_blocker(self):
        config = self.config()
        self.hook("UserPromptSubmit")
        config["tools"]["native"]["command"] = ["/missing"]
        self.write_config(config)
        result = self.hook("Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("not a pass", result["reason"])
        result = self.hook("Stop", stop_hook_active=True)
        self.assertNotIn("decision", result)
        self.assertIn("report the blocker", result["systemMessage"])

    def test_ordinary_folder_without_git_or_config_is_inert(self):
        self.assertEqual(self.hook("UserPromptSubmit"), {})
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

    def test_outcome_log_records_check_and_bounded_block_without_source(self):
        self.config("raise SystemExit(1)")
        self.hook("UserPromptSubmit")
        self.source.write_text("private_source_marker = 2\n")
        self.hook("PostToolUse")
        self.hook("Stop")
        self.hook("Stop", stop_hook_active=True)
        path = next((self.root / "state").glob("*.jsonl"))
        records = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(
            [r["outcome"] for r in records], ["skipped", "fail", "fail", "fail"]
        )
        self.assertEqual([r["blocked"] for r in records], [False, False, True, False])
        self.assertTrue(all(r["duration_ms"] >= 0 for r in records))
        self.assertNotIn("private_source_marker", path.read_text())
        self.assertNotIn(str(self.root), path.read_text())

    def test_setup_error_is_logged(self):
        self.config()
        self.hook("UserPromptSubmit")
        self.source.write_text("changed = 2\n")
        (self.root / "linter.py").unlink()
        self.hook("Stop")
        path = next((self.root / "state").glob("*.jsonl"))
        self.assertEqual(
            json.loads(path.read_text().splitlines()[-1])["outcome"], "setup_error"
        )

    def test_snapshot_change_reports_retry_and_does_not_cache_success(self):
        self.config(
            "from pathlib import Path; Path('src/example.py').write_text('mutated')"
        )
        self.hook("UserPromptSubmit")
        self.source.write_text("changed = 3\n")
        result = self.hook("PostToolUse")
        text = result["hookSpecificOutput"]["additionalContext"]
        self.assertIn("snapshot changed; retry", text)
        self.assertNotIn("setup required", text)
        path = next((self.root / "state").glob("*.jsonl"))
        self.assertEqual(
            json.loads(path.read_text().splitlines()[-1])["outcome"], "snapshot_changed"
        )
        self.config()
        self.assertIn(
            "PASS", self.hook("PostToolUse")["hookSpecificOutput"]["additionalContext"]
        )

    def test_unstable_completion_requests_retry_then_reports_blocker(self):
        self.config(
            "from pathlib import Path; p = Path('src/example.py'); "
            "p.write_text(p.read_text() + '# changed\\n')"
        )
        self.hook("UserPromptSubmit")
        self.source.write_text("value = 2\n")
        result = self.hook("Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("snapshot changed", result["reason"])
        result = self.hook("Stop", stop_hook_active=True)
        self.assertNotIn("decision", result)
        self.assertIn("report the blocker", result["systemMessage"])
