"""Explicit project activation and removal of the former global registration."""

import json
import shlex
import sys

from quality_lib.codex_hooks import EVENTS, hook_entry
from support import ROOT, Repository


class HookInstallation(Repository):
    def test_combined_dry_run_and_repeat_preserve_policy_and_hooks(self):
        config = self.config(register=False)
        self.assertEqual(self.cli("setup", "--codex", "--dry-run").returncode, 0)
        self.assertFalse((self.root / ".quality").exists())
        self.assertFalse((self.root / ".codex").exists())
        for _ in range(2):
            result = self.cli("setup", "--codex")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads((self.root / "quality.json").read_text()), config)
        hooks = json.loads((self.root / ".codex/hooks.json").read_text())["hooks"]
        self.assertTrue(all(len(groups) == 1 for groups in hooks.values()))
        self.assertFalse((self.root / "codex-home").exists())
        self.assertEqual(self.cli("install-codex", "--global").returncode, 2)

    def global_hooks(self):
        path = self.root / "codex-home/hooks.json"
        path.parent.mkdir()
        data = {"hooks": {event: [hook_entry(event, ROOT)] for event in EVENTS}}
        data["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 300
        path.write_text(json.dumps(data))
        return path, data

    def test_global_migration_preserves_other_hooks_and_is_repeatable(self):
        path, data = self.global_hooks()
        other = {"hooks": [{"type": "command", "command": "echo preserve"}]}
        data["hooks"]["Stop"].append(other)
        path.write_text(json.dumps(data))
        original = path.read_bytes()
        result = self.cli("setup", "--profile", "python", "--source", "src", "--codex")
        self.assertEqual(result.returncode, 2)
        self.assertIn("uninstall-codex --global", result.stdout)
        self.assertFalse((self.root / "quality.json").exists())
        self.assertFalse((self.root / ".quality").exists())
        self.assertEqual(
            self.cli("uninstall-codex", "--global", "--dry-run").returncode, 0
        )
        self.assertEqual(path.read_bytes(), original)
        for _ in range(2):
            self.assertEqual(self.cli("uninstall-codex", "--global").returncode, 0)
            self.assertEqual(json.loads(path.read_text()), {"hooks": {"Stop": [other]}})
        self.config(register=False)
        self.assertEqual(self.cli("setup", "--codex").returncode, 0)
        self.assertTrue((self.root / ".codex/hooks.json").is_file())

    def test_uninstall_refuses_a_custom_global_adapter(self):
        path, _ = self.global_hooks()
        custom = path.read_text().replace("quality.py", "different/quality.py")
        path.write_text(custom)
        self.assertEqual(self.cli("uninstall-codex", "--global").returncode, 2)
        self.assertEqual(path.read_text(), custom)

    def test_project_interpreter_alias_and_old_budget_are_preserved_or_upgraded(self):
        self.config(register=False)
        self.assertEqual(self.cli("install-codex").returncode, 0)
        path = self.root / ".codex/hooks.json"
        data = json.loads(path.read_text())
        alias = self.root / "python alias"
        alias.symlink_to(sys.executable)
        for groups in data["hooks"].values():
            command = shlex.split(groups[0]["hooks"][0]["command"])
            command[0] = str(alias)
            groups[0]["hooks"][0]["command"] = shlex.join(command)
        data["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 300
        path.write_text(json.dumps(data))
        for _ in range(2):
            self.assertEqual(self.cli("install-codex").returncode, 0)
        installed = json.loads(path.read_text())
        self.assertEqual(installed["hooks"]["Stop"][0]["hooks"][0]["timeout"], 1800)
        self.assertEqual(
            installed["hooks"]["PostToolUse"], data["hooks"]["PostToolUse"]
        )
        installed["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 301
        path.write_text(json.dumps(installed))
        self.assertEqual(self.cli("install-codex").returncode, 2)
        self.assertEqual(json.loads(path.read_text()), installed)

    def test_registration_requires_a_working_python_interpreter(self):
        self.config(register=False)
        self.cli("install-codex")
        path = self.root / ".codex/hooks.json"
        data = json.loads(path.read_text())
        hook = data["hooks"]["Stop"][0]["hooks"][0]
        command = shlex.split(hook["command"])
        hook["command"] = shlex.join(["/bin/echo", command[1]])
        path.write_text(json.dumps(data))
        result = self.cli("setup", "--codex")
        self.assertEqual(result.returncode, 2)
        self.assertIn("review before replacing", result.stdout)
        self.assertFalse((self.root / ".quality").exists())

    def test_failed_provisioning_does_not_register_hooks(self):
        config = self.config(register=False)
        config["tools"]["native"]["command"] = ["/missing"]
        self.write_config(config)
        self.assertEqual(self.cli("setup", "--codex").returncode, 2)
        self.assertFalse((self.root / ".codex").exists())
