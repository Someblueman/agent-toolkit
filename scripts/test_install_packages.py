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


if __name__ == "__main__":
    unittest.main()
