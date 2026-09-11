"""Project-specific setup and the distinction between checks and acceptance."""

import json
import subprocess

from support import Repository


class ProjectVerification(Repository):
    def test_unconfigured_git_project_gets_setup_first_without_writes(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        files = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        result = self.hook("UserPromptSubmit", cwd=str(self.root / "src"))
        message = result["systemMessage"]
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
        result = self.hook("UserPromptSubmit", cwd=str(nested))
        self.assertIn(str(nested.resolve()), result["systemMessage"])
        self.assertIn("Project verification setup required", result["systemMessage"])

    def test_existing_config_needs_definition_but_still_supports_tooling(self):
        config = self.config()
        del config["verification"]
        self.write_config(config)
        original = (self.root / "quality.json").read_bytes()
        self.assertIn(
            "Project verification setup required",
            self.hook("UserPromptSubmit")["systemMessage"],
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
            "Fixture lint is sufficient", self.hook("UserPromptSubmit")["systemMessage"]
        )
        self.assertEqual(self.hook("Stop", stop_hook_active=True), {})

    def test_definition_is_validated_without_a_test_quota(self):
        config = self.config()
        for value in (
            None,
            {},
            {"green": " ", "manual": []},
            {"green": "ok", "manual": [""]},
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
        prompt = self.hook("UserPromptSubmit")["systemMessage"]
        self.assertIn("changed controls", prompt)
        result = self.hook("Stop")
        self.assertIn("Overall green still requires", result["systemMessage"])
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

    def test_removing_configuration_cannot_bypass_stop(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.config()
        self.hook("UserPromptSubmit")
        (self.root / "quality.json").unlink()
        self.assertEqual(self.hook("Stop")["decision"], "block")
