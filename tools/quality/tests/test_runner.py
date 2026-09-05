import sys

from quality_lib.config import SetupError, load
from quality_lib.runner import run
from support import Repository


class RunnerTests(Repository):
    def test_pass_and_findings(self):
        self.config()
        self.assertEqual(self.cli("check").returncode, 0)
        self.config("raise SystemExit(1)")
        result = self.cli("check")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL", result.stdout)

    def test_missing_version_and_tool_errors(self):
        config = self.config()
        config["tools"]["native"]["version"] = "1.0"
        self.write_config(config)
        self.assertEqual(self.cli("doctor").returncode, 2)
        config["tools"]["native"]["command"] = ["/no/such/tool"]
        self.write_config(config)
        self.assertEqual(self.cli("check").returncode, 2)
        self.config("raise SystemExit(2)")
        self.assertEqual(self.cli("check").returncode, 2)

    def test_no_files_and_malformed_config_fail(self):
        self.config()
        self.source.unlink()
        self.assertEqual(self.cli("doctor").returncode, 2)
        (self.root / "quality.json").write_text('{"version": 1}')
        self.assertEqual(self.cli("check").returncode, 2)

    def test_sizes_boundary_and_advisory(self):
        config = self.config()
        config["size"]["mode"] = "error"
        self.write_config(config)
        self.source.write_bytes(b"x\r\n" * 500)
        self.assertEqual(self.cli("check").returncode, 0)
        self.source.write_bytes(b"x\r\n" * 500 + b"last")
        self.assertEqual(self.cli("check").returncode, 1)
        config["size"]["mode"] = "review"
        self.write_config(config)
        result = self.cli("check")
        self.assertEqual(result.returncode, 0)
        self.assertIn("501 physical lines", result.stdout)

    def test_full_includes_fast(self):
        config = self.config("raise SystemExit(1)")
        config["checks"][0]["stage"] = "full"
        self.write_config(config)
        self.assertEqual(self.cli("check", "--fast").returncode, 0)
        self.assertEqual(self.cli("check").returncode, 1)

    def test_timeout(self):
        with self.assertRaisesRegex(SetupError, "Timed out"):
            run(self.root, [sys.executable, "-c", "import time; time.sleep(10)"], 0.05)

    def test_source_edit_during_check_is_not_pass(self):
        self.config(
            "from pathlib import Path; Path('src/example.py').write_text('changed')"
        )
        result = self.cli("check")
        self.assertEqual(result.returncode, 2)
        self.assertIn("changed during checks", result.stdout)

    def test_symlink_root_rejected(self):
        config = self.config()
        (self.root / "linked").symlink_to(self.root / "src", target_is_directory=True)
        config["roots"] = ["linked"]
        self.write_config(config)
        self.assertEqual(self.cli("check").returncode, 2)

    def test_command_arguments_are_not_shell_expanded(self):
        code, text = run(
            self.root,
            [
                sys.executable,
                "-c",
                "import sys; print(sys.argv[1])",
                "$(touch injected)",
            ],
        )
        self.assertEqual(code, 0)
        self.assertIn("$(touch injected)", text)
        self.assertFalse((self.root / "injected").exists())

    def test_unknown_config_field(self):
        config = self.config()
        config["typo"] = True
        self.write_config(config)
        with self.assertRaises(SetupError):
            load(self.root)

    def test_unconfigured_language_is_not_silently_skipped(self):
        self.config()
        (self.root / "src/another.rs").write_text("fn main() {}\n")
        result = self.cli("doctor")
        self.assertEqual(result.returncode, 2)
        self.assertIn("another.rs", result.stdout)
