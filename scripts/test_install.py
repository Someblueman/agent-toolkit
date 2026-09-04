"""Exercise the actual installer CLI against an isolated source and destination."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="toolkit-install-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo with ' quote"
        self.home = self.root / "codex with ' quote"
        self.repo.mkdir()
        shutil.copytree(
            Path(__file__).parent,
            self.repo / "scripts",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        self.write("configs/codex/AGENTS.md", "policy\n")
        self.write("configs/codex/skills.txt", "example\n")
        self.write("configs/codex/skills/example/openai.yaml", "interface: {}\n")
        self.write("skills/example/SKILL.md", "example\n")
        self.write("skills/pragmatic-engineering/scripts/check_anti_bloat.py", "pass\n")

    def write(self, name, content):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def run_cli(self, *args, code=0):
        result = subprocess.run(
            ["bash", str(self.repo / "scripts/install.sh"), "codex", *args],
            env={**os.environ, "CODEX_HOME": str(self.home)},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def test_install_repeat_and_source_refresh_include_adapter(self):
        self.run_cli()
        metadata = self.home / "skills/example/agents/openai.yaml"
        before = metadata.stat().st_mtime_ns
        self.run_cli()
        self.run_cli("--check")
        self.assertEqual(metadata.stat().st_mtime_ns, before)
        self.write(
            "configs/codex/skills/example/openai.yaml", "interface: {name: changed}\n"
        )
        self.run_cli("--check", code=1)
        self.run_cli()
        self.assertIn("changed", metadata.read_text())

    def test_local_edit_requires_force(self):
        self.run_cli()
        skill = self.home / "skills/example/SKILL.md"
        skill.write_text("local change\n")
        self.run_cli(code=1)
        self.assertEqual(skill.read_text(), "local change\n")
        self.run_cli("--check", code=1)
        self.run_cli("--force")
        self.assertEqual(skill.read_text(), "example\n")

    def test_prune_preserves_unmanaged_and_edited_managed_content(self):
        self.run_cli()
        unrelated = self.home / "skills/unrelated"
        unrelated.mkdir()
        (unrelated / "SKILL.md").write_text("external")
        self.write("configs/codex/skills.txt", "")
        skill = self.home / "skills/example/SKILL.md"
        skill.write_text("local edit")
        self.run_cli("--prune", code=1)
        self.assertTrue(skill.exists())
        self.run_cli("--prune", "--force")
        self.assertFalse(skill.parent.exists())
        self.assertTrue(unrelated.exists())

    def test_readonly_modes_and_missing_source_do_not_install(self):
        self.run_cli("--dry-run")
        self.assertFalse(self.home.exists())
        self.run_cli("--check", code=1)
        self.assertFalse(self.home.exists())
        self.write("configs/codex/skills.txt", "missing\n")
        self.run_cli(code=1)
        self.assertFalse(self.home.exists())

    def test_unmodified_retired_skill_is_pruned_without_force(self):
        self.run_cli()
        self.write("configs/codex/skills.txt", "")
        self.run_cli("--prune", "--dry-run")
        self.assertTrue((self.home / "skills/example").exists())
        self.run_cli("--prune")
        self.assertFalse((self.home / "skills/example").exists())
        self.run_cli("--check")

    def test_omp_links_and_copied_config_remain_repeatable(self):
        self.write("configs/omp/config.yml", "example: true\n")
        (self.repo / "agents").mkdir()
        destination = self.root / "omp"
        for _ in range(2):
            result = subprocess.run(
                ["bash", str(self.repo / "scripts/install.sh"), "omp"],
                env={**os.environ, "OMP_AGENT_DIR": str(destination)},
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            (destination / "skills").resolve(), (self.repo / "skills").resolve()
        )
        self.assertFalse((destination / "config.yml").is_symlink())
        self.assertEqual((destination / "config.yml").read_text(), "example: true\n")

    def test_invalid_state_and_linked_parent_cannot_redirect_pruning(self):
        self.run_cli()
        state = self.home / ".agent-toolkit-install.json"
        original = state.read_text()
        state.write_text('{"version": 1, "managed": {"skills/../outside": "hash"}}')
        self.run_cli("--prune", "--force", code=1)
        state.write_text(original)
        shutil.rmtree(self.home / "skills")
        outside = self.root / "outside"
        outside.mkdir()
        (self.home / "skills").symlink_to(outside)
        self.run_cli("--force", code=1)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
