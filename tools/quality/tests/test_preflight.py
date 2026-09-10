"""Availability and coverage diagnostics run automatically before editing."""

import sys

from support import Repository


class PreflightTests(Repository):
    def test_prompt_checks_tools_once_and_rechecks_configuration(self):
        config = self.config("raise AssertionError('must not run tests at preflight')")
        script = self.root / "linter.py"
        script.write_text(
            script.read_text().replace(
                " print('lint 1.0.0')",
                " from pathlib import Path\n"
                " with Path('versions').open('a') as log: log.write('version\\n')\n"
                " print('lint 1.0.0')",
            )
        )
        message = self.hook("UserPromptSubmit")["systemMessage"]
        self.assertIn("No automated behavioral check declared", message)
        self.assertEqual(self.hook("UserPromptSubmit"), {})
        self.assertEqual((self.root / "versions").read_text(), "version\n")
        config["checks"][0]["kind"] = "test"
        self.write_config(config)
        message = self.hook("UserPromptSubmit")["systemMessage"]
        self.assertNotIn("No automated behavioral check declared", message)
        self.assertEqual((self.root / "versions").read_text(), "version\nversion\n")

    def test_removed_tool_is_reported_without_source_edits(self):
        self.config()
        self.hook("UserPromptSubmit")
        (self.root / "linter.py").unlink()
        result = self.hook("PostToolUse")
        self.assertIn("not a pass", result["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.hook("Stop")["decision"], "block")

    def test_manual_tests_are_explicitly_excluded_from_automatic_coverage(self):
        config = self.config()
        config["tools"]["manual"] = dict(
            config["tools"]["native"], command=["/missing"]
        )
        config["checks"].append(
            dict(
                config["checks"][0],
                name="manual acceptance",
                stage="manual",
                kind="test",
                tool="manual",
            )
        )
        self.write_config(config)
        result = self.hook("UserPromptSubmit")["systemMessage"]
        self.assertIn("manual (excluded from hooks): manual acceptance (test)", result)
        self.assertIn("No automated behavioral check declared", result)
        self.source.write_text("value = 2\n")
        self.assertEqual(self.hook("Stop"), {})
        self.assertEqual(self.cli("doctor").returncode, 2)

    def test_invalid_configuration_blocks_completion_once(self):
        self.config()
        self.hook("UserPromptSubmit")
        (self.root / "quality.json").write_text("{")
        self.assertEqual(self.hook("Stop")["decision"], "block")
        result = self.hook("Stop", stop_hook_active=True)
        self.assertNotIn("decision", result)
        self.assertIn("report the blocker", result["systemMessage"])

    def test_check_kind_is_optional_but_validated(self):
        config = self.config()
        config["checks"][0].pop("kind")
        self.write_config(config)
        self.assertEqual(self.cli("doctor").returncode, 0)
        config["checks"][0]["kind"] = "typo"
        self.write_config(config)
        self.assertEqual(self.cli("doctor").returncode, 2)

    def test_tool_losing_execute_permission_is_unavailable_without_edits(self):
        config = self.config()
        script = self.root / "linter.py"
        script.write_text(f"#!{sys.executable}\n" + script.read_text())
        script.chmod(0o755)
        config["tools"]["native"]["command"] = [str(script)]
        self.write_config(config)
        self.hook("UserPromptSubmit")
        script.chmod(0o644)
        result = self.hook("Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("Cannot launch", result["reason"])

    def test_executable_dependency_change_triggers_behavioral_check(self):
        config = self.config("raise SystemExit(1)")
        config["checks"][0]["inputs"] = ["helper.sh"]
        self.write_config(config)
        helper = self.root / "helper.sh"
        helper.write_text("#!/bin/sh\nexit 0\n")
        helper.chmod(0o644)
        self.hook("UserPromptSubmit")
        helper.chmod(0o755)
        result = self.hook("PostToolUse")
        self.assertIn("FAIL", result["hookSpecificOutput"]["additionalContext"])

    def test_new_sources_refresh_declared_coverage(self):
        config = self.config()
        config["checks"].append(
            dict(
                config["checks"][0],
                name="behavior",
                kind="test",
                stage="full",
                patterns=["src/example.py"],
            )
        )
        self.write_config(config)
        initial = self.hook("UserPromptSubmit")["systemMessage"]
        self.assertNotIn("No automated behavioral check declared", initial)
        (self.root / "src/new.py").write_text("value = 2\n")
        result = self.hook("PostToolUse")["hookSpecificOutput"]["additionalContext"]
        self.assertIn(
            "No automated behavioral check declared for 1 files: src/new.py", result
        )
