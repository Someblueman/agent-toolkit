#!/usr/bin/env python3
"""
check_anti_bloat.py - Automated anti-bloat guardrail checker.

Enforces:
1. Hard file length ceiling (maximum 500 LOC per file).
2. Ban on standalone smoke test scripts / paths (*smoke* in filename or path).
3. Hard inline test budget in Rust files (maximum 150 LOC for inline mod tests).

Returns exit code 0 when clean and exit code 1 with actionable violation messages.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

DEFAULT_MAX_FILE_LOC = 500
DEFAULT_MAX_INLINE_TEST_LOC = 150

DEFAULT_EXCLUDE_DIRS = {
    ".git", ".hg", ".svn", ".bzr", "CVS", "node_modules", "target", "dist",
    "build", "out", "bin", "obj", ".next", ".turbo", ".nuxt", ".docusaurus",
    "Pods", "DerivedData", "__pycache__", ".venv", "venv", "env", ".env",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox", ".coverage",
    "htmlcov", ".idea", ".vscode", "sessions", "log", "logs", "cache", "tmp",
    "temp", "attachments", "teamwork-runs", "teamwork-drafts", "memories",
    "generated_images", "dictation-history", "node_repl", "skill-runtimes",
    "worktrees", "vendor", "vendor_imports", "packages", "plugins", "state", "browser",
    "shell_snapshots", "process_manager", "sqlite", "mcp-oauth-locks",
    "thread-writer-locks", "app-server-control", "app-server-daemon", "ipc",
    "automations", "scratch", "visualizations",
}

DEFAULT_BUNDLE_EXTENSIONS = (
    ".app", ".framework", ".bundle", ".xcassets", ".xcodeproj",
    ".xcworkspace", ".dSYM", ".photoslibrary",
)

DEFAULT_EXCLUDE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".avif", ".icns",
    ".sqlite", ".sqlite-shm", ".sqlite-wal", ".db", ".bin", ".tar", ".gz", ".zip",
    ".lock", ".pdf", ".woff", ".woff2", ".ttf", ".eot", ".dylib", ".so", ".a",
    ".o", ".exe", ".dll", ".wasm", ".pyc", ".pyo", ".pyd", ".class", ".jar",
    ".war", ".ear", ".nib", ".car", ".dmg", ".pkg", ".iso", ".mp3", ".mp4",
    ".wav", ".mov", ".avi", ".mkv", ".flac", ".ogg", ".jsonl", ".log",
    ".parquet", ".arrow", ".plist", ".strings",
}


@dataclass
class Violation:
    file_path: Path
    code: str
    message: str
    line_count: int
    line_start: Optional[int] = None
    line_end: Optional[int] = None

    def __str__(self) -> str:
        loc_info = ""
        if self.line_start is not None and self.line_end is not None:
            loc_info = f" (lines {self.line_start}-{self.line_end}, {self.line_count} lines)"
        elif self.line_count > 0:
            loc_info = f" ({self.line_count} lines)"
        return f"[{self.code}] {self.file_path}{loc_info}: {self.message}"


def strip_not_clauses(text: str) -> str:
    """Remove balanced not(...) expressions from a cfg predicate."""
    result, i, n = [], 0, len(text)
    while i < n:
        m = re.match(r"\bnot\s*\(", text[i:])
        if m:
            i += m.end()
            depth = 1
            while i < n and depth > 0:
                if text[i] == "(":
                    depth += 1
                elif text[i] == ")":
                    depth -= 1
                i += 1
        else:
            result.append(text[i])
            i += 1
    return "".join(result)


def is_cfg_test(attr_content: str) -> bool:
    """Check if a #[cfg(...)] attribute affirmatively enables compilation for tests."""
    m = re.match(r"^#\[\s*cfg\s*\((.*)\)\s*\]$", attr_content.strip(), re.DOTALL)
    if not m:
        return False
    cleaned = strip_not_clauses(m.group(1).strip())
    feat_pat = r'feature\s*=\s*"[^"]*(?:(?<=[^a-zA-Z0-9])|^)(?:tests?|testing)(?:(?=[^a-zA-Z0-9])|$)[^"]*"'
    return bool(re.search(r"\btests?\b", cleaned) or re.search(feat_pat, cleaned))


def is_cfg_not_test(attr_content: str) -> bool:
    """Check if a #[cfg(...)] attribute explicitly negates test compilation."""
    m = re.match(r"^#\[\s*cfg\s*\((.*)\)\s*\]$", attr_content.strip(), re.DOTALL)
    if not m:
        return False
    return bool(re.search(r"\bnot\s*\([^)]*tests?", m.group(1)))


def find_rust_inline_test_modules(source_code: str) -> List[dict]:
    """
    Parse Rust source code to identify inline test modules (mod tests / #[cfg(test)] mod ... { ... }).
    Handles strings, raw strings, comments, nested block comments, and nested braces.
    Returns a list of dicts with: name, start_line, end_line, line_count.
    """
    if not source_code:
        return []

    modules = []
    total_chars, line_num = len(source_code), 1
    in_line_comment, block_comment_depth = False, 0
    in_string, in_raw_string, raw_string_hashes, in_char = False, False, 0, False

    pending_cfg_test_line = None
    active_module_name, active_module_start_line, active_module_depth = None, None, None
    current_brace_depth = 0

    attr_pat = re.compile(r"^#\[\s*([a-zA-Z0-9_]+(?:\s*\([^\]]*\))?)\s*\]", re.DOTALL)
    mod_pat = re.compile(r"^\b(?:pub(?:\s*\([^)]+\))?\s+)?mod\s+([a-zA-Z0-9_]+)")
    non_mod_decl_pat = re.compile(
        r"^\b(?:pub(?:\s*\([^)]+\))?\s+)?(?:default\s+)?(?:const\s+|async\s+|unsafe\s+|extern(?:\s+\"[^\"]+\")?\s+)*(?:fn|struct|enum|union|impl|trait|type|const|static|use|let)\b"
    )

    i = 0
    while i < total_chars:
        ch = source_code[i]

        if ch == "\n":
            line_num += 1
            if in_line_comment:
                in_line_comment = False
            i += 1
            continue

        if in_line_comment:
            i += 1
            continue

        if block_comment_depth > 0:
            if ch == "/" and i + 1 < total_chars and source_code[i + 1] == "*":
                block_comment_depth += 1
                i += 2
                continue
            if ch == "*" and i + 1 < total_chars and source_code[i + 1] == "/":
                block_comment_depth -= 1
                i += 2
                continue
            i += 1
            continue

        if in_raw_string:
            if ch == '"':
                hashes = 0
                while i + 1 + hashes < total_chars and source_code[i + 1 + hashes] == "#" and hashes < raw_string_hashes:
                    hashes += 1
                if hashes == raw_string_hashes:
                    in_raw_string = False
                    i += 1 + hashes
                    continue
            i += 1
            continue

        if in_string:
            if ch == "\\":
                if i + 1 < total_chars and source_code[i + 1] == "\n":
                    line_num += 1
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue

        if in_char:
            if ch == "\\":
                i += 2
                continue
            if ch == "'":
                in_char = False
            i += 1
            continue

        # Comments start
        if ch == "/" and i + 1 < total_chars:
            if source_code[i + 1] == "/":
                in_line_comment = True
                i += 2
                continue
            if source_code[i + 1] == "*":
                block_comment_depth = 1
                i += 2
                continue

        # Raw string start
        if (ch == "r" or (ch == "b" and i + 1 < total_chars and source_code[i + 1] == "r")) and i + 1 < total_chars:
            r_idx = i if ch == "r" else i + 1
            h_idx, hashes = r_idx + 1, 0
            while h_idx < total_chars and source_code[h_idx] == "#":
                hashes += 1
                h_idx += 1
            if h_idx < total_chars and source_code[h_idx] == '"':
                in_raw_string, raw_string_hashes, i = True, hashes, h_idx + 1
                continue

        # Normal string start
        if ch == '"':
            in_string, i = True, i + 1
            continue
        if ch == "b" and i + 1 < total_chars and source_code[i + 1] == '"':
            in_string, i = True, i + 2
            continue

        # Char literal start
        if ch == "'" and i + 1 < total_chars:
            if (i + 2 < total_chars and source_code[i + 2] == "'") or source_code[i + 1] == "\\":
                in_char, i = True, i + 1
                continue

        # Braces, semicolons & commas
        if ch == "{":
            current_brace_depth += 1
            if active_module_name is not None and active_module_depth is None:
                active_module_depth = current_brace_depth
            elif active_module_name is None:
                pending_cfg_test_line = None
            i += 1
            continue
        elif ch == "}":
            if active_module_depth is not None and current_brace_depth == active_module_depth:
                end_line = line_num
                start_line = active_module_start_line or end_line
                modules.append({
                    "name": active_module_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "line_count": end_line - start_line + 1,
                })
                active_module_name, active_module_start_line, active_module_depth = None, None, None
            current_brace_depth = max(0, current_brace_depth - 1)
            pending_cfg_test_line = None
            i += 1
            continue
        elif ch == ";":
            if active_module_name is not None and active_module_depth is None:
                active_module_name, active_module_start_line = None, None
            pending_cfg_test_line = None
            i += 1
            continue
        elif ch == ",":
            pending_cfg_test_line = None
            i += 1
            continue

        # Check attributes and declarations when no active module signature is pending
        if active_module_name is None:
            remaining = source_code[i:]
            if ch == "#":
                attr_match = attr_pat.match(remaining)
                if attr_match:
                    attr_text = attr_match.group(0)
                    if attr_text.startswith("#[cfg"):
                        if is_cfg_test(attr_text):
                            if pending_cfg_test_line is None:
                                pending_cfg_test_line = line_num
                        elif is_cfg_not_test(attr_text):
                            pending_cfg_test_line = None
                    line_num += attr_text.count("\n")
                    i += len(attr_text)
                    continue

            # Word boundary check for mod or non-mod declarations
            if i == 0 or not (source_code[i - 1].isalnum() or source_code[i - 1] == "_"):
                mod_match = mod_pat.match(remaining)
                if mod_match:
                    mod_name = mod_match.group(1)
                    is_test_mod = (
                        pending_cfg_test_line is not None
                        or mod_name in ("tests", "test")
                        or mod_name.startswith("test_")
                        or mod_name.endswith(("_test", "_tests"))
                    )
                    if is_test_mod:
                        active_module_name = mod_name
                        active_module_start_line = line_num
                        pending_cfg_test_line = None
                    matched_text = mod_match.group(0)
                    line_num += matched_text.count("\n")
                    i += len(matched_text)
                    continue

                if pending_cfg_test_line is not None and non_mod_decl_pat.match(remaining):
                    pending_cfg_test_line = None

        i += 1

    return modules


def check_file(
    file_path: Path | str,
    max_file_loc: int = DEFAULT_MAX_FILE_LOC,
    max_inline_test_loc: int = DEFAULT_MAX_INLINE_TEST_LOC,
    base_path: Optional[Path | str] = None,
) -> List[Violation]:
    """Check a single file for anti-bloat violations."""
    path = Path(file_path)
    violations: List[Violation] = []

    # 1. Ban standalone smoke test scripts / paths (*smoke* in filename or relative path)
    if base_path is not None:
        try:
            rel = path.relative_to(base_path)
            parts_to_check = rel.parts
        except ValueError:
            parts_to_check = path.parts
    else:
        try:
            rel = path.relative_to(Path.cwd())
            parts_to_check = rel.parts
        except ValueError:
            parts_to_check = path.parts

    if any("smoke" in part for part in [p.lower() for p in parts_to_check]):
        violations.append(
            Violation(
                file_path=path,
                code="SMOKE_TEST_SCRIPT",
                message=f"Standalone smoke test script / path detected: '{path.name}'. Use focused unit tests instead.",
                line_count=0,
            )
        )

    try:
        raw_bytes = path.read_bytes()
    except Exception:
        return violations

    # Skip LOC checks on binary files (containing null bytes)
    if b"\x00" in raw_bytes[:8192]:
        return violations

    try:
        content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content = raw_bytes.decode("utf-8", errors="replace")

    lines = content.splitlines()
    total_loc = len(lines)

    # 2. Hard file length ceiling (500 LOC)
    if total_loc > max_file_loc:
        violations.append(
            Violation(
                file_path=path,
                code="FILE_LENGTH_EXCEEDED",
                message=f"File exceeds {max_file_loc} LOC ceiling: {total_loc} lines (limit: {max_file_loc}). Decompose into modular submodules.",
                line_count=total_loc,
            )
        )

    # 3. Rust inline test budget (150 LOC)
    if path.suffix == ".rs":
        for mod_info in find_rust_inline_test_modules(content):
            if mod_info["line_count"] > max_inline_test_loc:
                violations.append(
                    Violation(
                        file_path=path,
                        code="INLINE_TEST_EXCEEDED",
                        message=(
                            f"Inline test module '{mod_info['name']}' exceeds {max_inline_test_loc} LOC limit: "
                            f"{mod_info['line_count']} lines (lines {mod_info['start_line']}-{mod_info['end_line']}, limit: {max_inline_test_loc}). "
                            f"Extract into a dedicated test file under tests/ or a sibling module."
                        ),
                        line_count=mod_info["line_count"],
                        line_start=mod_info["start_line"],
                        line_end=mod_info["end_line"],
                    )
                )

    return violations


def should_skip_dir(dir_name: str) -> bool:
    """Determine if a directory should be skipped during recursive traversal."""
    if dir_name in DEFAULT_EXCLUDE_DIRS or dir_name.startswith("."):
        return True
    if dir_name.endswith(DEFAULT_BUNDLE_EXTENSIONS):
        return True
    return False


def scan_paths(
    paths: List[Path | str],
    max_file_loc: int = DEFAULT_MAX_FILE_LOC,
    max_inline_test_loc: int = DEFAULT_MAX_INLINE_TEST_LOC,
    excludes: Optional[set] = None,
) -> List[Violation]:
    """Scan files and directories for anti-bloat violations."""
    all_violations: List[Violation] = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        if path.is_file():
            all_violations.extend(check_file(path, max_file_loc=max_file_loc, max_inline_test_loc=max_inline_test_loc))
        elif path.is_dir():
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if not should_skip_dir(d)]
                for f in files:
                    file_path = Path(root) / f
                    if file_path.suffix in DEFAULT_EXCLUDE_EXTENSIONS:
                        continue
                    all_violations.extend(
                        check_file(
                            file_path,
                            max_file_loc=max_file_loc,
                            max_inline_test_loc=max_inline_test_loc,
                            base_path=path,
                        )
                    )
    return all_violations


def run_self_tests() -> int:
    """Run internal test suite."""
    os.environ["_CHECK_ANTI_BLOAT_IN_SELF_TEST"] = "1"
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from test_check_anti_bloat import TestCheckAntiBloat

    suite = unittest.TestLoader().loadTestsFromTestCase(TestCheckAntiBloat)
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Automated anti-bloat guardrail checker (500 LOC per file, 150 LOC inline tests, ban smoke scripts)."
    )
    parser.add_argument("paths", nargs="*", default=["."], help="Paths (files or directories) to check.")
    parser.add_argument("--max-file-loc", type=int, default=DEFAULT_MAX_FILE_LOC, help=f"Max file LOC (default: {DEFAULT_MAX_FILE_LOC}).")
    parser.add_argument("--max-inline-test-loc", type=int, default=DEFAULT_MAX_INLINE_TEST_LOC, help=f"Max inline test LOC (default: {DEFAULT_MAX_INLINE_TEST_LOC}).")
    parser.add_argument("--self-test", action="store_true", help="Run self-tests and exit.")

    args = parser.parse_args(argv)
    if args.self_test:
        return run_self_tests()

    violations = scan_paths([Path(p) for p in args.paths], max_file_loc=args.max_file_loc, max_inline_test_loc=args.max_inline_test_loc)
    if violations:
        print(f"FAILED: Found {len(violations)} anti-bloat violation(s):\n", file=sys.stderr)
        for v in violations:
            print(f"  ❌ {v}", file=sys.stderr)
        print("\nPlease fix violations by decomposing files > 500 LOC, extracting inline tests > 150 LOC, or removing smoke scripts.", file=sys.stderr)
        return 1

    print("✅ Anti-bloat checks passed: all files conform to LOC ceilings and anti-bloat rules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
