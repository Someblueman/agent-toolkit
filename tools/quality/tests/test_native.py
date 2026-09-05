"""Opt-in tests that provision real tools: QUALITY_NATIVE=python,biome,shell,c-cpp."""

import json
import os
import subprocess
import unittest

from support import Repository

ENABLED = os.environ.get("QUALITY_NATIVE", "").split(",")


class NativeTests(Repository):
    def setup_profile(self, profile, source, text):
        self.source.unlink()
        self.source = self.root / "src" / source
        self.source.write_text(text)
        result = self.cli("setup", "--profile", profile, "--source", "src")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.cli("doctor").returncode, 0)

    @unittest.skipUnless("python" in ENABLED, "set QUALITY_NATIVE=python")
    def test_python_real_complexity_and_hook(self):
        self.setup_profile("python", "app.py", "value = 1\n")
        self.assertEqual(self.cli("check").returncode, 0)
        self.hook("UserPromptSubmit")
        for branches, expected in ((9, 0), (10, 1)):
            self.source.write_text(
                "def choose(x):\n"
                + "".join(
                    f"    if x == {i}:\n        return {i}\n" for i in range(branches)
                )
                + "    return -1\n"
            )
            result = self.cli("check")
            self.assertEqual(result.returncode, expected, result.stdout)
        result = self.hook("Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("C901", result["reason"])
        self.source.write_text("value = 1\n")
        self.assertEqual(self.hook("Stop", stop_hook_active=True), {})
        self.source.write_text("def broken(:\n")
        self.assertNotEqual(self.cli("check").returncode, 0)

    @unittest.skipUnless("biome" in ENABLED, "set QUALITY_NATIVE=biome")
    def test_biome_real_complexity_and_preserved_configuration(self):
        original = {
            "linter": {
                "rules": {
                    "complexity": {
                        "noExcessiveCognitiveComplexity": {
                            "level": "warn",
                            "options": {"maxAllowedComplexity": 99},
                        }
                    }
                }
            }
        }
        path = self.root / "biome.json"
        path.write_text(json.dumps(original))
        self.setup_profile("biome", "app.js", "console.log(1);\n")
        self.assertEqual(json.loads(path.read_text()), original)
        for extra, expected in (("", 0), ("if (x === 9) return 2;", 1)):
            self.source.write_text(
                "export function choose(x) { "
                + "if(x) {" * 5
                + "return 1;"
                + "}" * 5
                + extra
                + "return 0; }"
            )
            tool = self.root / "node_modules/.bin/biome"
            subprocess.run(
                [str(tool), "format", "--write", str(self.source)],
                check=True,
                capture_output=True,
            )
            result = self.cli("check")
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
            if expected:
                self.assertIn("noExcessiveCognitiveComplexity", result.stdout)

    @unittest.skipUnless("shell" in ENABLED, "set QUALITY_NATIVE=shell")
    def test_shell_real_lint(self):
        self.setup_profile("shell", "app.sh", '#!/bin/sh\nprintf "%s\\n" "$HOME"\n')
        self.assertEqual(self.cli("check").returncode, 0)
        self.source.write_text("#!/bin/sh\nrm $file\n")
        result = self.cli("check")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("SC2086", result.stdout)

    @unittest.skipUnless("c-cpp" in ENABLED, "set QUALITY_NATIVE=c-cpp")
    def test_clang_real_complexity(self):
        (self.root / "build").mkdir()
        (self.root / "build/compile_commands.json").write_text(
            json.dumps(
                [
                    {
                        "directory": str(self.root),
                        "file": str(self.root / "src/app.c"),
                        "arguments": ["clang", "-c", str(self.root / "src/app.c")],
                    }
                ]
            )
        )
        self.setup_profile("c-cpp", "app.c", "int main(void) { return 0; }\n")
        self.assertEqual(self.cli("check").returncode, 0)
        for extra, expected in (("", 0), ("if (x == 9) return 2;", 1)):
            self.source.write_text(
                "int choose(int x) {"
                + "if(x) {" * 5
                + "return 1;"
                + "}" * 5
                + extra
                + "return 0;}\n"
            )
            result = self.cli("check")
            self.assertEqual(result.returncode, expected, result.stdout)
