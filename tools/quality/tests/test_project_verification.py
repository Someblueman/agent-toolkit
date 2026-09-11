"""Project-specific setup and the distinction between checks and acceptance."""

import json
import subprocess

from support import Repository


class ProjectVerification(Repository):
    def test_only_explicitly_registered_git_project_gets_setup_prompt(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.assertEqual(self.hook("UserPromptSubmit"), {})
        self.assertEqual(self.hook("Stop"), {})
        self.assertFalse((self.root / "state").exists())
        self.assertEqual(self.cli("install-codex").returncode, 0)
        files = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        result = self.hook("UserPromptSubmit", cwd=str(self.root / "src"))
        message = result["hookSpecificOutput"]["additionalContext"]
        self.assertIn(str(self.root.resolve()), message)
        self.assertIn("first task", message)
        self.assertIn("verification.green", message)
        self.assertIn("Do not add tests", message)
        self.assertIn("For read-only requests", message)
        self.assertEqual(self.hook("PostToolUse"), {})
        self.assertEqual(self.hook("Stop")["decision"], "block")
        result = self.hook("Stop", stop_hook_active=True)
        self.assertNotIn("decision", result)
        self.assertIn("report the blocker", result["systemMessage"])
        remaining = sorted(
            str(p.relative_to(self.root))
            for p in self.root.rglob("*")
            if "state" not in p.relative_to(self.root).parts
        )
        self.assertEqual(files, remaining)

    def test_nested_repository_does_not_inherit_parent_verification(self):
        self.config()
        nested = self.root / "src/nested"
        nested.mkdir()
        subprocess.run(["git", "init", "-q", str(nested)], check=True)
        self.assertEqual(self.hook("UserPromptSubmit", cwd=str(nested)), {})
        self.assertEqual(self.cli("--root", str(nested), "install-codex").returncode, 0)
        result = self.hook("UserPromptSubmit", cwd=str(nested))
        self.assertIn(
            str(nested.resolve()), result["hookSpecificOutput"]["additionalContext"]
        )
        self.assertIn(
            "Project verification setup required",
            result["hookSpecificOutput"]["additionalContext"],
        )

    def test_existing_config_needs_definition_but_still_supports_tooling(self):
        config = self.config()
        del config["verification"]
        self.write_config(config)
        original = (self.root / "quality.json").read_bytes()
        self.assertIn(
            "Project verification setup required",
            self.hook("UserPromptSubmit")["hookSpecificOutput"]["additionalContext"],
        )
        self.assertEqual(self.hook("Stop")["decision"], "block")
        self.assertEqual(self.cli("doctor").returncode, 0)
        self.assertEqual(self.cli("check").returncode, 0)
        self.assertEqual((self.root / "quality.json").read_bytes(), original)
        config["verification"] = {
            "green": "Fixture lint is sufficient here.",
            "manual": [],
        }
        self.write_config(config)
        self.assertIn(
            "Fixture lint is sufficient",
            self.hook("UserPromptSubmit")["hookSpecificOutput"]["additionalContext"],
        )
        self.assertEqual(self.hook("Stop", stop_hook_active=True), {})

    def test_definition_is_validated_without_a_test_quota(self):
        config = self.config()
        for value in (
            None,
            {},
            {"green": " ", "manual": []},
            {"green": "ok", "manual": [""]},
            {"green": "ok", "manual": [], "review": "yes"},
        ):
            with self.subTest(value=value):
                config["verification"] = value
                self.write_config(config)
                self.assertEqual(self.cli("doctor").returncode, 2)
        config["verification"] = {
            "green": "The fixture's syntax rules pass.",
            "manual": [],
        }
        self.write_config(config)
        # Explicitly chosen lint checks do not demand arbitrary test creation.
        self.assertEqual(self.hook("Stop"), {})

    def test_manual_evidence_is_not_reported_as_automatically_green(self):
        config = self.config()
        config["verification"] = {
            "green": "The game builds and its changed controls work in the browser.",
            "manual": [
                "Play the changed controls in the browser and record the result."
            ],
        }
        self.write_config(config)
        prompt = self.hook("UserPromptSubmit")["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertIn("changed controls", prompt)
        result = self.hook("Stop")
        self.assertIn(
            "completion is not assessed by this hook", result["systemMessage"]
        )
        self.assertIn("Play the changed controls", result["systemMessage"])
        records = [
            json.loads(line)
            for line in next((self.root / "state").glob("*.jsonl"))
            .read_text()
            .splitlines()
        ]
        self.assertEqual(records[-1]["outcome"], "manual_required")
        config["checks"][0]["stage"] = "manual"
        self.write_config(config)
        self.assertIn("none configured", self.hook("Stop")["systemMessage"])
        config["checks"][0]["stage"] = "fast"
        config["verification"]["manual"] = []
        self.write_config(config)
        self.assertEqual(self.hook("Stop"), {})

    def test_manual_reminder_is_quiet_until_sources_or_criteria_change(self):
        config = self.config()
        config["verification"]["manual"] = ["Inspect the changed behavior."]
        self.write_config(config)
        self.hook("UserPromptSubmit")
        first = self.hook("Stop")
        self.assertNotIn("decision", first)
        self.assertIn("Inspect the changed behavior", first["systemMessage"])
        self.assertEqual(self.hook("Stop", stop_hook_active=True), {})
        self.assertEqual(
            self.hook("UserPromptSubmit", prompt="Why is the campaign blocked?"), {}
        )
        self.assertEqual(self.hook("Stop"), {})
        records = next((self.root / "state").glob("*.jsonl")).read_text().splitlines()
        self.assertEqual(json.loads(records[-1])["outcome"], "manual_required")
        self.source.write_text("value = 2\n")
        self.assertIn(
            "Inspect the changed behavior", self.hook("Stop")["systemMessage"]
        )
        self.assertEqual(self.hook("Stop"), {})
        config["verification"]["manual"] = ["Inspect the new acceptance criterion."]
        self.write_config(config)
        self.assertIn("new acceptance criterion", self.hook("Stop")["systemMessage"])
        config["checks"][0]["stage"] = "manual"
        self.write_config(config)
        self.hook("Stop")
        self.assertEqual(self.hook("Stop"), {})
        self.source.write_text("value = 3\n")
        self.assertIn("new acceptance criterion", self.hook("Stop")["systemMessage"])

    def test_removing_configuration_cannot_bypass_stop(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.config()
        self.assertEqual(self.cli("install-codex").returncode, 0)
        self.hook("UserPromptSubmit")
        (self.root / "quality.json").unlink()
        self.assertEqual(self.hook("Stop")["decision"], "block")
