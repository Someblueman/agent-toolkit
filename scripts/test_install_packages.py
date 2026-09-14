"""Verify the current canonical packages through the real installer."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class CanonicalPackages(unittest.TestCase):
    def test_current_packages_install_repeat_and_match(self):
        installer = Path(__file__).resolve().parent / "install.sh"
        with tempfile.TemporaryDirectory(prefix="toolkit-packages-") as destination:
            for options in ([], [], ["--check"]):
                result = subprocess.run(
                    ["bash", str(installer), "codex", *options],
                    env={**os.environ, "CODEX_HOME": destination},
                    text=True,
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            home = Path(destination)
            self.assertEqual(
                (home / "skills/fanout/SKILL.md").read_bytes(),
                (installer.parents[1] / "skills/fanout/SKILL.md").read_bytes(),
            )
            toolkit = Path((home / "agent-toolkit-root.txt").read_text().strip())
            self.assertEqual(toolkit, installer.parents[1])
            result = subprocess.run(
                [str(toolkit / "tools/fanout/bin/fanout"), "--help"],
                cwd=destination,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("--harness", result.stdout)


if __name__ == "__main__":
    unittest.main()
