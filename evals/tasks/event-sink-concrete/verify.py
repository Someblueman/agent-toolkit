"""Mechanical scorer for event-sink-concrete. Prints METRICS {...}; exit 0 = pass.

Run with cwd = the run workspace (a copy of scaffold/ with the agent's edits).
Checks:
  1. Behavior: record() writes 'YYYY-MM-DDTHH:MM:SS tag message\n' to the given
     stream, returns None, stamps the current UTC time; the CLI exits 0 and
     emits exactly that line; unknown actions / wrong arity exit non-zero.
  2. Anti-abstraction: no ABC/abstractmethod/TypeVar/Generic/Protocol/Builder
     identifiers, no abc import, no PEP 695 type parameters/aliases.
  3. Shape: exactly one recording class-or-function and exactly one call site
     of it outside tests.
  4. Scope: no files created outside {recorder.py, config.py, cli.py, tests/};
     added LOC across the 3 source files <= 120 over the pristine scaffold.
"""
import ast
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

PASS = True
banned_token_count = 0
added_loc = None
record_defs = None
record_calls = None

SOURCES = ["recorder.py", "config.py", "cli.py"]
LOC_CEILING = 120  # added lines over the pristine scaffold, 3 source files combined
# Pristine scaffold line counts, embedded so the ceiling cannot drift.
BASELINE_LOC = {"recorder.py": 10, "config.py": 19, "cli.py": 18}

EXACT_BANNED = {"ABC", "ABCMeta", "abstractmethod", "TypeVar", "Generic", "Protocol"}
RECORDISH = re.compile(r"record|sink", re.IGNORECASE)
ALLOWED_TOP = {"recorder.py", "config.py", "cli.py", "tests"}
IGNORED = {"__pycache__", ".pytest_cache", ".git", ".DS_Store"}

TAG = "deploy"
MSG = "web farm is live"


def fail(msg: str):
    global PASS
    PASS = False
    print(f"FAIL: {msg}", file=sys.stderr)


def ban(token: str):
    global banned_token_count
    banned_token_count += 1
    print(f"FAIL: banned abstraction token: {token}", file=sys.stderr)


def emit_metrics():
    print("METRICS " + json.dumps({
        "pass": int(PASS),
        "banned_token_count": banned_token_count,
        "added_loc": added_loc,
        "record_defs": record_defs,
        "record_calls": record_calls,
    }))
    return 0 if PASS else 1


def collect_idents(tree) -> list:
    idents = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            idents.append(node.id)
        elif isinstance(node, ast.Attribute):
            idents.append(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            idents.append(node.name)
            if getattr(node, "type_params", None):
                ban(f"type_params on {node.name}")
        elif isinstance(node, ast.arg):
            idents.append(node.arg)
        elif isinstance(node, ast.keyword):
            idents.append(node.arg)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            idents.extend(node.names)
        elif isinstance(node, ast.Import):
            for a in node.names:
                idents.append(a.asname or a.name.split(".")[0])
                if a.name.split(".")[0] == "abc":
                    ban(f"import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] == "abc":
                ban(f"from {node.module} import")
            for a in node.names:
                idents.append(a.asname or a.name)
        elif isinstance(node, ast.TypeAlias):
            ban("type alias statement")
    return idents


def scan_banned(trees) -> None:
    for tree in trees:
        for ident in collect_idents(tree):
            if ident in EXACT_BANNED:
                ban(ident)
            elif isinstance(ident, str) and ident.lower().endswith("builder"):
                ban(ident)


def count_defs(trees) -> int:
    n = 0
    for tree in trees:
        for node in tree.body:  # top-level only
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and RECORDISH.search(node.name):
                n += 1
    return n


def count_calls(trees) -> int:
    n = 0
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name) and RECORDISH.search(f.id):
                    n += 1
                elif isinstance(f, ast.Attribute) and RECORDISH.search(f.attr):
                    n += 1
    return n


def fresh_utc(ts: str) -> bool:
    try:
        t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return abs((now - t).total_seconds()) <= 120


def line_regex() -> re.Pattern:
    return re.compile(
        rf"(\d{{4}}-\d{{2}}-\d{{2}}T\d{{2}}:\d{{2}}:\d{{2}}) "
        rf"{re.escape(TAG)} {re.escape(MSG)}\n"
    )


def check_line(text: str, where: str) -> None:
    m = line_regex().fullmatch(text)
    if not m:
        fail(f"{where}: output is not exactly one '{TAG} {MSG}' event line: {text!r}")
    elif not fresh_utc(m.group(1)):
        fail(f"{where}: timestamp {m.group(1)} is not the current UTC time")


def run_cli(args: list) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "cli.py", *args],
        capture_output=True, text=True, timeout=30, cwd=os.getcwd(),
    )


def main() -> int:
    trees = []
    for name in SOURCES:
        if not os.path.isfile(name):
            fail(f"{name} is missing from the workspace")
            return emit_metrics()
        try:
            trees.append(ast.parse(open(name, encoding="utf-8").read(), filename=name))
        except SyntaxError as e:
            fail(f"{name} does not parse: {e}")
            return emit_metrics()

    scan_banned(trees)

    global record_defs, record_calls, added_loc
    record_defs = count_defs(trees)
    if record_defs != 1:
        fail(f"expected exactly one recording class-or-function, found {record_defs}")
    record_calls = count_calls(trees)
    if record_calls != 1:
        fail(f"expected exactly one caller of the recording callable, found {record_calls}")

    total = 0
    for name in SOURCES:
        total += len(open(name, encoding="utf-8").read().splitlines())
    added_loc = total - sum(BASELINE_LOC.values())
    if added_loc > LOC_CEILING:
        fail(f"added {added_loc} lines over the scaffold baseline; ceiling is {LOC_CEILING}")

    if not os.path.isfile(os.path.join("tests", "test_record.py")):
        fail("tests/test_record.py was removed")

    # Behavior: direct call into an in-memory stream.
    sys.path.insert(0, os.getcwd())
    try:
        import recorder
    except Exception as e:
        fail(f"recorder.py does not import: {e}")
        return emit_metrics()
    try:
        buf = io.StringIO()
        ret = recorder.record(TAG, MSG, buf)
        if ret is not None:
            fail(f"record() must return None, got {ret!r}")
        check_line(buf.getvalue(), "record()")
    except Exception as e:
        fail(f"record() raised: {e!r}")
        return emit_metrics()

    # Behavior: CLI happy path.
    try:
        r = run_cli(["record", TAG, MSG])
        if r.returncode != 0:
            fail(f"cli record exited {r.returncode}, expected 0 (stderr: {r.stderr.strip()!r})")
        else:
            check_line(r.stdout, "cli record")
    except Exception as e:
        fail(f"cli record run failed: {e!r}")
        return emit_metrics()

    # Behavior: error paths keep their non-zero exits.
    for args in (["frobnicate", TAG, MSG], ["record", TAG]):
        try:
            r = run_cli(args)
            if r.returncode == 0:
                fail(f"cli {' '.join(args)} must exit non-zero, got 0")
        except Exception as e:
            fail(f"cli {' '.join(args)} run failed: {e!r}")

    # Scope: no files created outside the allowed set.
    for entry in os.listdir("."):
        if entry in ALLOWED_TOP or entry in IGNORED or entry.endswith(".pyc"):
            continue
        fail(f"file created outside the allowed set: {entry}")

    return emit_metrics()


if __name__ == "__main__":
    sys.exit(main())
