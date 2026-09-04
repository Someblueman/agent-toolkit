#!/usr/bin/env python3
"""
Unit tests for check_anti_bloat.py
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from check_anti_bloat import (
        DEFAULT_MAX_FILE_LOC,
        DEFAULT_MAX_INLINE_TEST_LOC,
        check_file,
        find_rust_inline_test_modules,
        scan_paths,
    )
except ImportError:
    pass


class TestCheckAntiBloat(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_clean_file_passes(self):
        file_path = self.dir_path / "valid.py"
        file_path.write_text("print('hello')\n" * 100)
        violations = check_file(file_path)
        self.assertEqual(violations, [])

    def test_file_loc_ceiling_500_passes(self):
        file_path = self.dir_path / "exact_limit.py"
        file_path.write_text("x = 1\n" * DEFAULT_MAX_FILE_LOC)
        violations = check_file(file_path)
        self.assertEqual(violations, [])

    def test_file_loc_exceeded_reports_review_finding(self):
        file_path = self.dir_path / "oversized.py"
        file_path.write_text("x = 1\n" * 501)
        violations = check_file(file_path)
        self.assertEqual(len(violations), 1)
        self.assertIn("exceeds 500 LOC review threshold", violations[0].message)
        self.assertEqual(violations[0].code, "FILE_LENGTH_EXCEEDED")
        self.assertEqual(violations[0].line_count, 501)

    def test_smoke_in_filename_is_allowed(self):
        file_path = self.dir_path / "run-smoke.mjs"
        file_path.write_text("console.log('smoke test');\n")
        violations = check_file(file_path)
        self.assertEqual(violations, [])

    def test_smoke_in_path_is_allowed(self):
        smoke_dir = self.dir_path / "smoke_tests"
        smoke_dir.mkdir()
        file_path = smoke_dir / "runner.py"
        file_path.write_text("print('run')\n")
        violations = check_file(file_path)
        self.assertEqual(violations, [])

    def test_rust_file_with_external_mod_tests_passes(self):
        file_path = self.dir_path / "lib.rs"
        file_path.write_text(
            "pub fn add(a: i32, b: i32) -> i32 {\n"
            "    a + b\n"
            "}\n\n"
            "#[cfg(test)]\n"
            "mod tests;\n"
        )
        violations = check_file(file_path)
        self.assertEqual(violations, [])

    def test_rust_file_with_small_inline_mod_tests_passes(self):
        file_path = self.dir_path / "lib.rs"
        rust_code = (
            "pub fn add(a: i32, b: i32) -> i32 { a + b }\n\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    use super::*;\n"
            "    #[test]\n"
            "    fn test_add() {\n"
            "        assert_eq!(add(1, 2), 3);\n"
            "    }\n"
            "}\n"
        )
        file_path.write_text(rust_code)
        violations = check_file(file_path)
        self.assertEqual(violations, [])

    def test_rust_file_with_150_loc_inline_mod_tests_passes(self):
        inner_lines = ["        // line\n"] * 146
        rust_code = (
            "pub fn add(a: i32, b: i32) -> i32 { a + b }\n\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            + "".join(inner_lines)
            + "    #[test]\n"
            "    fn test_add() {}\n"
            "}\n"
        )
        file_path = self.dir_path / "lib.rs"
        file_path.write_text(rust_code)
        modules = find_rust_inline_test_modules(rust_code)
        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0]["line_count"], DEFAULT_MAX_INLINE_TEST_LOC)
        violations = check_file(file_path)
        self.assertEqual(violations, [])

    def test_rust_file_with_151_loc_inline_mod_tests_fails(self):
        inner_lines = ["        // line\n"] * 147
        rust_code = (
            "pub fn add(a: i32, b: i32) -> i32 { a + b }\n\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            + "".join(inner_lines)
            + "    #[test]\n"
            "    fn test_add() {}\n"
            "}\n"
        )
        file_path = self.dir_path / "lib.rs"
        file_path.write_text(rust_code)
        violations = check_file(file_path)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].code, "INLINE_TEST_EXCEEDED")
        self.assertIn("exceeds 150 LOC limit", violations[0].message)

    def test_rust_cfg_not_test_is_not_flagged(self):
        rust_code = (
            "#[cfg(not(test))]\n"
            "mod prod_code {\n"
            "    pub fn prod_only() {}\n"
            "}\n\n"
            "#[cfg(not(any(test, feature = \"test\")))]\n"
            "mod other_prod {\n"
            "    pub fn other_only() {}\n"
            "}\n"
        )
        modules = find_rust_inline_test_modules(rust_code)
        self.assertEqual(modules, [])

    def test_rust_struct_and_enum_field_cfg_does_not_leak(self):
        rust_code = (
            "struct MyStruct {\n"
            "    #[cfg(test)]\n"
            "    debug_tag: String,\n"
            "    name: String,\n"
            "}\n\n"
            "enum MyEnum {\n"
            "    #[cfg(test)]\n"
            "    MockVariant,\n"
            "    LiveVariant,\n"
            "}\n\n"
            "mod regular_module {\n"
            "    pub fn run() {}\n"
            "}\n"
        )
        modules = find_rust_inline_test_modules(rust_code)
        self.assertEqual(modules, [])

    def test_rust_multiline_cfg_attribute_line_tracking(self):
        rust_code = (
            "// line 1\n"
            "#[cfg(\n"
            "    all(\n"
            "        test,\n"
            "        feature = \"foo\"\n"
            "    )\n"
            ")]\n"
            "mod custom_fixture {\n"
            "    fn test_it() {}\n"
            "}\n"
        )
        modules = find_rust_inline_test_modules(rust_code)
        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0]["name"], "custom_fixture")
        self.assertEqual(modules[0]["start_line"], 8)
        self.assertEqual(modules[0]["end_line"], 10)
        self.assertEqual(modules[0]["line_count"], 3)

    def test_rust_brace_and_string_handling_in_tests(self):
        rust_code = (
            "#[cfg(test)]\n"
            "mod tests {\n"
            '    const BRACES: &str = "{ { { } } }";\n'
            "    // comment with }\n"
            "    /* multi-line\n"
            "       comment with }\n"
            "    */\n"
            "    #[test]\n"
            "    fn test_foo() {\n"
            "        let x = 1;\n"
            "    }\n"
            "}\n"
        )
        modules = find_rust_inline_test_modules(rust_code)
        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0]["name"], "tests")
        self.assertEqual(modules[0]["start_line"], 2)
        self.assertEqual(modules[0]["end_line"], 12)

    def test_rust_multiple_test_modules(self):
        rust_code = (
            "#[cfg(test)]\n"
            "mod unit_tests {\n"
            "    #[test]\n"
            "    fn test_1() {}\n"
            "}\n\n"
            "#[cfg(test)]\n"
            "mod prop_tests {\n"
            "    #[test]\n"
            "    fn test_2() {}\n"
            "}\n"
        )
        modules = find_rust_inline_test_modules(rust_code)
        self.assertEqual(len(modules), 2)
        self.assertEqual(modules[0]["name"], "unit_tests")
        self.assertEqual(modules[1]["name"], "prop_tests")

    def test_rust_feature_containing_test_substring_not_flagged(self):
        rust_code = (
            "#[cfg(feature = \"latest\")]\n"
            "mod latest_driver {\n"
            "    pub fn run() {}\n"
            "}\n\n"
            "#[cfg(feature = \"fastest\")]\n"
            "mod fastest_engine {\n"
            "    pub fn run() {}\n"
            "}\n"
        )
        modules = find_rust_inline_test_modules(rust_code)
        self.assertEqual(modules, [])

    def test_rust_stacked_cfg_attributes_preserved(self):
        rust_code = (
            "#[cfg(test)]\n"
            "#[cfg(feature = \"heavy\")]\n"
            "mod heavy_tests_runner {\n"
            "    #[test]\n"
            "    fn test_heavy() {}\n"
            "}\n"
        )
        modules = find_rust_inline_test_modules(rust_code)
        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0]["name"], "heavy_tests_runner")

    def test_rust_fn_cfg_test_does_not_leak_to_subsequent_mod(self):
        rust_code = (
            "#[cfg(test)]\n"
            "pub async fn test_async_helper() {}\n\n"
            "#[cfg(test)]\n"
            "unsafe fn test_unsafe_helper() {}\n\n"
            "mod regular_prod_module {\n"
            "    pub fn run() {}\n"
            "}\n"
        )
        modules = find_rust_inline_test_modules(rust_code)
        self.assertEqual(modules, [])

    def test_binary_file_skipped_for_loc_check(self):
        bin_file = self.dir_path / "data.bin"
        bin_file.write_bytes(b"hello\x00world\n" * 600)
        violations = check_file(bin_file)
        self.assertEqual(violations, [])

    def test_scan_paths_aggregate_violations(self):
        f1 = self.dir_path / "too_long.py"
        f1.write_text("x = 1\n" * 501)

        f2 = self.dir_path / "smoke_check.sh"
        f2.write_text("#!/bin/bash\necho ok\n")

        f3 = self.dir_path / "heavy_test.rs"
        inner = ["    // test\n"] * 155
        f3.write_text("#[cfg(test)]\nmod tests {\n" + "".join(inner) + "}\n")

        f4 = self.dir_path / "clean.py"
        f4.write_text("print('clean')\n")

        violations = scan_paths([self.dir_path])
        codes = [v.code for v in violations]
        self.assertIn("FILE_LENGTH_EXCEEDED", codes)
        self.assertNotIn("SMOKE_TEST_SCRIPT", codes)
        self.assertIn("INLINE_TEST_EXCEEDED", codes)
        self.assertEqual(len(violations), 2)

    def test_cli_execution_with_clean_directory(self):
        clean_dir = self.dir_path / "clean_dir"
        clean_dir.mkdir()
        (clean_dir / "app.py").write_text("print('ok')\n")

        script_path = SCRIPT_DIR / "check_anti_bloat.py"
        result = subprocess.run(
            [sys.executable, str(script_path), str(clean_dir)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Anti-bloat checks passed", result.stdout)

    def test_cli_execution_with_violations(self):
        dirty_dir = self.dir_path / "dirty_dir"
        dirty_dir.mkdir()
        (dirty_dir / "large.py").write_text("x = 1\n" * 501)

        script_path = SCRIPT_DIR / "check_anti_bloat.py"
        result = subprocess.run(
            [sys.executable, str(script_path), "--strict", str(dirty_dir)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("FILE_LENGTH_EXCEEDED", result.stderr + result.stdout)

    def test_scan_paths_in_tmp_parent_directory_scans_subdirectories(self):
        tmp_parent = Path(tempfile.gettempdir()) / f"bloat_test_tmp_{os.getpid()}"
        tmp_parent.mkdir(parents=True, exist_ok=True)
        try:
            src_dir = tmp_parent / "src"
            src_dir.mkdir(exist_ok=True)
            (src_dir / "oversized.py").write_text("x = 1\n" * 501)
            violations = scan_paths([tmp_parent])
            self.assertEqual(len(violations), 1)
            self.assertEqual(violations[0].code, "FILE_LENGTH_EXCEEDED")
        finally:
            import shutil
            shutil.rmtree(tmp_parent, ignore_errors=True)

    def test_smoke_path_scoping_ignores_parent_username_containing_smoke(self):
        fake_base = Path("/home/smoke_tester/project")
        app_file = fake_base / "src" / "app.py"
        violations = check_file(app_file, base_path=fake_base)
        self.assertEqual(violations, [])

        smoke_file = fake_base / "tests" / "smoke_runner.py"
        violations_smoke = check_file(smoke_file, base_path=fake_base)
        self.assertEqual(violations_smoke, [])

    def test_rust_lifetimes_and_char_escapes_handled_cleanly(self):
        rust_code = (
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    fn test_lifetimes<'a>() where 'a: 'static {\n"
            "        let b = b'\\\'';\n"
            "        let c = '}';\n"
            "        let r = r###\"nested } brace\"###;\n"
            "    }\n"
            "}\n"
        )
        modules = find_rust_inline_test_modules(rust_code)
        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0]["name"], "tests")

    def test_cli_self_test_flag(self):
        if os.environ.get("_CHECK_ANTI_BLOAT_IN_SELF_TEST"):
            return
        script_path = SCRIPT_DIR / "check_anti_bloat.py"
        env = dict(os.environ, _CHECK_ANTI_BLOAT_IN_SELF_TEST="1")
        result = subprocess.run(
            [sys.executable, str(script_path), "--self-test"],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("OK", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()


