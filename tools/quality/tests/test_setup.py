import sys

from quality_lib.config import validate
from quality_lib.profiles import PINS, build, build_many
from support import Repository


class SetupTests(Repository):
    def test_all_profiles_validate(self):
        for profile in PINS:
            with self.subTest(profile=profile):
                validate(build(self.root, profile))

    def test_dry_run_writes_nothing(self):
        result = self.cli("setup", "--profile", "python", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.root / "quality.json").exists())
        self.assertFalse((self.root / ".quality").exists())

    def test_combined_profiles(self):
        config = build_many(self.root, ["python", "shell"], roots=["src"])
        validate(config)
        self.assertEqual(set(config["tools"]), {"python", "shell"})
        self.assertEqual(len(config["checks"]), 3)

    def test_existing_config_is_not_replaced(self):
        self.config()
        previous = (self.root / "quality.json").read_bytes()
        self.assertEqual(self.cli("setup", "--profile", "python").returncode, 2)
        self.assertEqual((self.root / "quality.json").read_bytes(), previous)

    def test_setup_installs_only_when_missing(self):
        config = self.config()
        executable = self.root / "provisioned.py"
        config["tools"]["native"]["command"] = [sys.executable, str(executable)]
        config["tools"]["native"]["install"] = [
            [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; Path('provisioned.py').write_text(\"print('lint 1.0.0')\\n\"); "
                    "Path('installed').write_text('once')"
                ),
            ]
        ]
        self.write_config(config)
        self.assertEqual(self.cli("check").returncode, 2)
        self.assertFalse((self.root / "installed").exists())
        self.assertEqual(self.cli("setup").returncode, 0)
        (self.root / "installed").write_text("preserved")
        self.assertEqual(self.cli("setup").returncode, 0)
        self.assertEqual((self.root / "installed").read_text(), "preserved")

    def test_failed_install_is_not_ready(self):
        config = self.config()
        config["tools"]["native"]["version"] = "2.0.0"
        config["tools"]["native"]["install"] = [
            [sys.executable, "-c", "raise SystemExit(9)"]
        ]
        self.write_config(config)
        self.assertEqual(self.cli("setup").returncode, 2)
        self.assertEqual(self.cli("doctor").returncode, 2)
