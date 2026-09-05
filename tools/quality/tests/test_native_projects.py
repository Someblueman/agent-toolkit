"""Native package-scoped checks; enable via QUALITY_NATIVE."""

import os
import subprocess
import unittest

from support import Repository

ENABLED = os.environ.get("QUALITY_NATIVE", "").split(",")


class NativeProjectTests(Repository):
    def setup_profile(self, name):
        result = self.cli("setup", "--profile", name, "--source", "src")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless("rust" in ENABLED, "set QUALITY_NATIVE=rust")
    def test_rust_clippy_and_format(self):
        self.source.unlink()
        self.source = self.root / "src/lib.rs"
        self.source.write_text("pub fn answer() -> i32 {\n    42\n}\n")
        (self.root / "Cargo.toml").write_text(
            '[package]\nname="quality-probe"\nversion="0.1.0"\nedition="2021"\n'
        )
        subprocess.run(
            ["cargo", "generate-lockfile", "--offline"],
            cwd=self.root,
            capture_output=True,
            check=True,
        )
        self.setup_profile("rust")
        result = self.cli("check")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.source.write_text("pub fn answer() -> bool {\n    1 == 1\n}\n")
        self.assertEqual(self.cli("check").returncode, 1)

    @unittest.skipUnless("go" in ENABLED, "set QUALITY_NATIVE=go")
    def test_go_preserves_configuration_and_limits_complexity(self):
        self.source.unlink()
        self.source = self.root / "src/app.go"
        self.source.write_text("package probe\nfunc Answer() int { return 42 }\n")
        (self.root / "go.mod").write_text("module quality-probe\n\ngo 1.25.0\n")
        original = 'version: "2"\nlinters:\n  default: none\n  enable: [govet]\n'
        (self.root / ".golangci.yml").write_text(original)
        self.setup_profile("go")
        merged = (self.root / ".golangci.yml").read_text()
        self.assertIn("govet", merged)
        self.assertIn("min-complexity: 10", merged)
        result = self.cli("check")
        self.assertEqual(result.returncode, 0, result.stdout)
        for branches, expected in ((9, 0), (10, 1)):
            self.source.write_text(
                "package probe\nfunc Choose(x int) int {\n"
                + "".join(f"if x == {n} {{return {n}}}\n" for n in range(branches))
                + "return -1\n}\n"
            )
            result = self.cli("check")
            self.assertEqual(result.returncode, expected, result.stdout)
            if expected:
                self.assertIn("gocyclo", result.stdout)

    @unittest.skipUnless("haskell" in ENABLED, "set QUALITY_NATIVE=haskell")
    def test_haskell_existing_hlint(self):
        self.source.unlink()
        self.source = self.root / "src/Main.hs"
        self.source.write_text(
            'module Main where\nmain :: IO ()\nmain = putStrLn "hello"\n'
        )
        # Reuse the installed exact native tool; provisioning recipe remains separately documented.
        from quality_lib.profiles import build

        config = build(self.root, "haskell", roots=["src"])
        config["tools"]["native"]["command"] = ["hlint"]
        config["tools"]["native"]["install"] = []
        self.write_config(config)
        result = self.cli("setup")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.cli("check").returncode, 0)
        self.source.write_text(
            'module Main where\nisEmpty xs = length xs == 0\nmain = putStrLn "hello"\n'
        )
        self.assertEqual(self.cli("check").returncode, 1)

    @unittest.skipUnless("eslint" in ENABLED, "set QUALITY_NATIVE=eslint")
    def test_eslint_existing_config(self):
        self.source.unlink()
        self.source = self.root / "src/app.js"
        self.source.write_text("export const value = 1;\n")
        (self.root / "eslint.config.mjs").write_text(
            'export default [{rules: {"no-debugger": "error"}}];\n'
        )
        self.setup_profile("eslint")
        self.assertEqual(self.cli("check").returncode, 0)
        self.source.write_text("debugger;\n")
        result = self.cli("check")
        self.assertEqual(result.returncode, 1, result.stdout)
