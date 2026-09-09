import json

from quality_lib.incremental import select, snapshot
from quality_lib.profiles import PATTERNS
from support import Repository, build


class IncrementalTests(Repository):
    def test_profiles_select_files_or_native_project_scope(self):
        for profile, patterns in PATTERNS.items():
            with self.subTest(profile=profile):
                config = build(self.root, profile)
                suffix = patterns[0][1:]
                old = {
                    "files": {"a" + suffix: "old", "b" + suffix: "same"},
                    "inputs": {},
                    "policy": "same",
                }
                now = dict(old, files={"a" + suffix: "new", "b" + suffix: "same"})
                for spec in config["checks"]:
                    expected = ["a" + suffix]
                    if not spec["files"]:
                        expected.append("b" + suffix)
                    self.assertEqual(select(spec, old, now), expected)

    def test_header_deletion_and_input_changes_invalidate_scope(self):
        spec = build(self.root, "c-cpp")["checks"][0]
        old = {
            "files": {"a.c": "one", "b.c": "two", "x.h": "old"},
            "inputs": {},
            "policy": "same",
        }
        for now in (
            dict(old, files={**old["files"], "x.h": "new"}),
            dict(old, files={"a.c": "one", "b.c": "two"}),
            dict(old, inputs={"Makefile": "changed"}),
        ):
            self.assertEqual(select(spec, old, now), ["a.c", "b.c"])

    def test_nested_config_outside_roots_and_checker_changes_are_seen(self):
        config = self.config()
        baseline = snapshot(self.root.resolve(), config)
        (self.root / "package").mkdir()
        native = self.root / "package/pyproject.toml"
        native.write_text("[tool.ruff]\n")
        changed = snapshot(self.root.resolve(), config)
        name = config["checks"][0]["name"]
        self.assertNotEqual(baseline[name]["inputs"], changed[name]["inputs"])
        script = self.root / "linter.py"
        script.write_text(script.read_text() + "# new checker\n")
        self.assertNotEqual(
            changed[name]["policy"],
            snapshot(self.root.resolve(), config)[name]["policy"],
        )

    def test_only_changed_file_runs_and_stop_reuses_success(self):
        self.config(
            "from pathlib import Path; Path('calls').open('a').write(repr(sys.argv[1:]) + '\\n')"
        )
        other = self.root / "src/other.py"
        other.write_text("other = 1\n")
        self.hook("UserPromptSubmit")
        self.source.write_text("value = 2\n")
        self.hook("PostToolUse")
        self.assertEqual(self.hook("Stop"), {})
        self.assertEqual((self.root / "calls").read_text(), "['./src/example.py']\n")
        records = [
            json.loads(line)
            for line in next((self.root / "state").glob("*.jsonl"))
            .read_text()
            .splitlines()
        ]
        self.assertEqual(records[-1]["cached_checks"], 1)
        self.hook("UserPromptSubmit")
        other.write_text("other = 2\n")
        self.hook("Stop")
        self.assertEqual(
            (self.root / "calls").read_text().splitlines()[-1], "['./src/other.py']"
        )

    def test_new_deleted_and_config_files_recheck(self):
        self.config(
            "from pathlib import Path; Path('calls').open('a').write(repr(sys.argv[1:]) + '\\n')"
        )
        self.hook("UserPromptSubmit")
        other = self.root / "src/other.py"
        other.write_text("other = 1\n")
        self.hook("Stop")
        self.assertEqual(
            (self.root / "calls").read_text().splitlines()[-1], "['./src/other.py']"
        )
        self.hook("UserPromptSubmit")
        other.unlink()
        self.hook("Stop")
        self.assertEqual(
            (self.root / "calls").read_text().splitlines()[-1], "['./src/example.py']"
        )
        self.hook("UserPromptSubmit")
        (self.root / "pyproject.toml").write_text("[tool.ruff]\n")
        self.hook("Stop")
        self.assertEqual(len((self.root / "calls").read_text().splitlines()), 3)

    def test_manual_check_remains_explicit(self):
        config = self.config()
        config["checks"].append(
            dict(
                config["checks"][0],
                name="slow analysis",
                stage="manual",
                args=["--slow"],
            )
        )
        self.write_config(config)
        (self.root / "linter.py").write_text(
            "import sys\nprint('lint 1.0.0')\nraise SystemExit(int('--slow' in sys.argv))\n"
        )
        self.hook("UserPromptSubmit")
        self.source.write_text("value = 2\n")
        self.assertEqual(self.hook("Stop"), {})
        self.assertEqual(self.cli("check").returncode, 1)

    def test_unaffected_language_does_not_require_its_tool(self):
        config = self.config()
        config["tools"]["unavailable"] = dict(
            config["tools"]["native"], command=["/missing-shellcheck"]
        )
        config["checks"].append(
            dict(
                config["checks"][0], name="shell", tool="unavailable", patterns=["*.sh"]
            )
        )
        self.write_config(config)
        (self.root / "src/other.sh").write_text("#!/bin/sh\nexit 0\n")
        self.hook("UserPromptSubmit")
        self.source.write_text("value = 2\n")
        self.assertEqual(self.hook("Stop"), {})

    def test_explicit_check_detects_native_input_change_outside_roots(self):
        self.config(
            "from pathlib import Path; Path('pyproject.toml').write_text('[tool.ruff]\\n')"
        )
        result = self.cli("check")
        self.assertEqual(result.returncode, 2)
        self.assertIn("changed", result.stdout + result.stderr)
