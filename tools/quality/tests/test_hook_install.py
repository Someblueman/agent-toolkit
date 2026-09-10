"""Installation, reuse and failure boundaries in isolated Codex destinations."""

import json
import shlex
import sys

from support import Repository


class HookInstallation(Repository):
    def test_combined_dry_run_and_repeat_preserve_policy_and_hooks(self):
        config = self.config()
        self.assertEqual(self.cli("setup", "--codex", "--dry-run").returncode, 0)
        self.assertFalse((self.root / ".quality").exists())
        self.assertFalse((self.root / ".codex").exists())
        for _ in range(2):
            result = self.cli("setup", "--codex")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads((self.root / "quality.json").read_text()), config)
        hooks = json.loads((self.root / ".codex/hooks.json").read_text())["hooks"]
        self.assertTrue(all(len(groups) == 1 for groups in hooks.values()))

    def test_global_install_without_project_config_is_repeatable_and_reused(self):
        user = self.root / "codex-home"
        user.mkdir()
        path = user / "hooks.json"
        existing = {
            "hooks": {
                "Stop": [{"hooks": [{"type": "command", "command": "echo existing"}]}]
            }
        }
        path.write_text(json.dumps(existing))
        self.assertEqual(
            self.cli("install-codex", "--global", "--dry-run").returncode, 0
        )
        self.assertEqual(json.loads(path.read_text()), existing)
        self.assertFalse((self.root / "quality.json").exists())
        for _ in range(2):
            result = self.cli("install-codex", "--global")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        installed = path.read_bytes()
        data = json.loads(installed)
        self.assertEqual(data["hooks"]["Stop"][0], existing["hooks"]["Stop"][0])
        self.assertEqual(len(data["hooks"]["Stop"]), 2)
        self.config()
        result = self.cli("setup", "--codex")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Reusing configured user hooks", result.stdout)
        self.assertFalse((self.root / ".codex").exists())
        self.assertEqual(path.read_bytes(), installed)

    def test_global_interpreter_can_differ_from_project_interpreter(self):
        self.cli("install-codex", "--global")
        path = self.root / "codex-home/hooks.json"
        data = json.loads(path.read_text())
        alias = self.root / "codex-home/python alias"
        alias.symlink_to(sys.executable)
        for groups in data["hooks"].values():
            command = shlex.split(groups[0]["hooks"][0]["command"])
            command[0] = str(alias)
            groups[0]["hooks"][0]["command"] = shlex.join(command)
        path.write_text(json.dumps(data))
        self.config()
        result = self.cli("setup", "--codex")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / ".codex").exists())

    def test_conflicting_global_registration_prevents_provisioning(self):
        self.cli("install-codex", "--global")
        path = self.root / "codex-home/hooks.json"
        old = path.read_text().replace("quality.py", "different/quality.py")
        path.write_text(old)
        result = self.cli("setup", "--profile", "python", "--source", "src", "--codex")
        self.assertEqual(result.returncode, 2)
        self.assertIn("review before replacing", result.stdout)
        self.assertFalse((self.root / "quality.json").exists())
        self.assertFalse((self.root / ".quality").exists())
        self.assertEqual(path.read_text(), old)

    def test_global_registration_requires_a_working_python_interpreter(self):
        self.assertEqual(self.cli("install-codex", "--global").returncode, 0)
        path = self.root / "codex-home/hooks.json"
        data = json.loads(path.read_text())
        hook = data["hooks"]["Stop"][0]["hooks"][0]
        command = shlex.split(hook["command"])
        hook["command"] = shlex.join(["/bin/echo", command[1]])
        path.write_text(json.dumps(data))
        result = self.cli("setup", "--profile", "python", "--codex")
        self.assertEqual(result.returncode, 2)
        self.assertIn("review before replacing", result.stdout)
        self.assertFalse((self.root / "quality.json").exists())

    def test_failed_provisioning_does_not_register_hooks(self):
        config = self.config()
        config["tools"]["native"]["command"] = ["/missing"]
        self.write_config(config)
        self.assertEqual(self.cli("setup", "--codex").returncode, 2)
        self.assertFalse((self.root / ".codex").exists())

    def test_partial_global_registration_only_installs_missing_events(self):
        self.cli("install-codex", "--global")
        path = self.root / "codex-home/hooks.json"
        data = json.loads(path.read_text())
        del data["hooks"]["Stop"]
        path.write_text(json.dumps(data))
        self.config()
        self.assertEqual(self.cli("setup", "--codex").returncode, 0)
        local = json.loads((self.root / ".codex/hooks.json").read_text())
        self.assertEqual(list(local["hooks"]), ["Stop"])
