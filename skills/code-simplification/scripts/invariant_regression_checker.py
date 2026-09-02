#!/usr/bin/env python3
"""
Invariant Regression Checker CLI

Executes differential testing and golden snapshot verification across baseline
and refactored implementations to assert 100% behavioral invariance.

Supports:
1. Module/Function Differential Fuzzing: Compares return values and exceptions.
2. CLI Command Differential Runner: Compares stdout, stderr, and exit codes.
3. Golden Master Snapshot Verification: Validates candidate outputs against golden files.
4. Non-deterministic Token Normalization: Masks UUIDs, timestamps, and memory addresses.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


@dataclass
class TestResult:
    test_id: str
    passed: bool
    baseline_output: Any
    candidate_output: Any
    baseline_time_ms: float = 0.0
    candidate_time_ms: float = 0.0
    diff_detail: Optional[str] = None


@dataclass
class InvarianceReport:
    total_tests: int
    passed_tests: int
    failed_tests: int
    baseline_total_time_ms: float
    candidate_total_time_ms: float
    speedup_ratio: float
    results: List[TestResult] = field(default_factory=list)


def normalize_tokens(text: str, custom_patterns: Optional[List[Tuple[str, str]]] = None) -> str:
    """
    Normalizes dynamic/non-deterministic tokens like UUIDs, timestamps, and memory addresses.
    """
    patterns = [
        (r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", "<UUID>"),
        (r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?", "<TIMESTAMP>"),
        (r"0x[0-9a-fA-F]{6,16}", "<PTR_ADDR>"),
        (r"PID:\s*\d+", "PID: <PID>"),
    ]
    if custom_patterns:
        patterns.extend(custom_patterns)

    normalized = text
    for pattern, replacement in patterns:
        normalized = re.sub(pattern, replacement, normalized)
    return normalized


def _compare_numeric(val1: Any, val2: Any, float_tol: float) -> Tuple[bool, Optional[str]]:
    if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
        if math.isclose(float(val1), float(val2), rel_tol=float_tol, abs_tol=float_tol):
            return True, None
        return False, f"Numeric mismatch: {val1} != {val2} (tol={float_tol})"
    return False, f"Type mismatch: {type(val1).__name__} != {type(val2).__name__}"


def _compare_dict(d1: Dict[Any, Any], d2: Dict[Any, Any], float_tol: float) -> Tuple[bool, Optional[str]]:
    if set(d1.keys()) != set(d2.keys()):
        return False, f"Dict keys differ: {set(d1.keys()) ^ set(d2.keys())}"
    for k in d1:
        ok, diff = deep_compare(d1[k], d2[k], float_tol)
        if not ok:
            return False, f"At key '{k}': {diff}"
    return True, None


def _compare_sequence(s1: Sequence[Any], s2: Sequence[Any], float_tol: float) -> Tuple[bool, Optional[str]]:
    if len(s1) != len(s2):
        return False, f"Length mismatch: {len(s1)} != {len(s2)}"
    for i, (item1, item2) in enumerate(zip(s1, s2)):
        ok, diff = deep_compare(item1, item2, float_tol)
        if not ok:
            return False, f"At index [{i}]: {diff}"
    return True, None


def deep_compare(val1: Any, val2: Any, float_tol: float = 1e-9) -> Tuple[bool, Optional[str]]:
    """
    Deep recursive comparison supporting floats with epsilon tolerance and structural types.
    """
    if isinstance(val1, (int, float)) or isinstance(val2, (int, float)):
        return _compare_numeric(val1, val2, float_tol)
    if type(val1) is not type(val2):
        return False, f"Type mismatch: {type(val1).__name__} != {type(val2).__name__}"
    if isinstance(val1, dict):
        return _compare_dict(val1, val2, float_tol)
    if isinstance(val1, (list, tuple)):
        return _compare_sequence(val1, val2, float_tol)
    if val1 == val2:
        return True, None
    return False, f"Value mismatch: {repr(val1)} != {repr(val2)}"


def load_module_from_path(file_path: Path) -> Any:
    """
    Dynamically imports a Python module from a file path.
    """
    module_name = file_path.stem
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module specification from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def run_command(cmd: str, cwd: Optional[Path] = None) -> Tuple[int, str, str, float]:
    """
    Executes a shell command and returns (exit_code, stdout, stderr, elapsed_ms).
    """
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return proc.returncode, proc.stdout, proc.stderr, elapsed_ms


def run_differential_cli(
    baseline_cmd: str, candidate_cmd: str, test_inputs: List[str]
) -> InvarianceReport:
    """
    Runs differential CLI execution across a list of test inputs.
    """
    results: List[TestResult] = []
    base_total_ms = 0.0
    cand_total_ms = 0.0

    for idx, test_in in enumerate(test_inputs, 1):
        b_code, b_out, b_err, b_ms = run_command(f"{baseline_cmd} '{test_in}'")
        c_code, c_out, c_err, c_ms = run_command(f"{candidate_cmd} '{test_in}'")

        base_total_ms += b_ms
        cand_total_ms += c_ms

        b_norm = normalize_tokens(f"CODE:{b_code}\nOUT:{b_out}\nERR:{b_err}")
        c_norm = normalize_tokens(f"CODE:{c_code}\nOUT:{c_out}\nERR:{c_err}")

        passed = (b_norm == c_norm)
        diff = None if passed else f"Baseline:\n{b_norm}\nCandidate:\n{c_norm}"

        results.append(
            TestResult(
                test_id=f"case_{idx:03d}",
                passed=passed,
                baseline_output=b_norm,
                candidate_output=c_norm,
                baseline_time_ms=b_ms,
                candidate_time_ms=c_ms,
                diff_detail=diff,
            )
        )

    passed_count = sum(1 for r in results if r.passed)
    speedup = (base_total_ms / cand_total_ms) if cand_total_ms > 0 else 1.0

    return InvarianceReport(
        total_tests=len(results),
        passed_tests=passed_count,
        failed_tests=len(results) - passed_count,
        baseline_total_time_ms=base_total_ms,
        candidate_total_time_ms=cand_total_ms,
        speedup_ratio=speedup,
        results=results,
    )


def _safe_invoke(fn: Callable[..., Any], args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Tuple[Any, Optional[str], float]:
    t0 = time.perf_counter()
    err: Optional[str] = None
    val: Any = None
    try:
        val = fn(*args, **kwargs)
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return val, err, elapsed_ms


def _eval_python_diff_case(
    idx: int,
    call_args: Tuple[Tuple[Any, ...], Dict[str, Any]],
    fns: Tuple[Callable[..., Any], Callable[..., Any]],
    float_tol: float,
) -> Tuple[TestResult, float, float]:
    args, kwargs = call_args
    fn_base, fn_cand = fns
    base_val, base_err, b_ms = _safe_invoke(fn_base, args, kwargs)
    cand_val, cand_err, c_ms = _safe_invoke(fn_cand, args, kwargs)

    if base_err or cand_err:
        passed = (base_err == cand_err)
        diff = None if passed else f"Exception mismatch: '{base_err}' vs '{cand_err}'"
        b_out, c_out = base_err, cand_err
    else:
        passed, diff = deep_compare(base_val, cand_val, float_tol=float_tol)
        b_out, c_out = base_val, cand_val

    res = TestResult(
        test_id=f"test_case_{idx:03d}",
        passed=passed,
        baseline_output=b_out,
        candidate_output=c_out,
        baseline_time_ms=b_ms,
        candidate_time_ms=c_ms,
        diff_detail=diff,
    )
    return res, b_ms, c_ms


def run_differential_python_functions(
    fn_baseline: Callable[..., Any],
    fn_candidate: Callable[..., Any],
    test_cases: List[Tuple[Tuple[Any, ...], Dict[str, Any]]],
    float_tol: float = 1e-9,
) -> InvarianceReport:
    """
    Executes differential tests on Python functions with identical arguments.
    """
    results: List[TestResult] = []
    base_total_ms = 0.0
    cand_total_ms = 0.0
    fns = (fn_baseline, fn_candidate)

    for idx, case_args in enumerate(test_cases, 1):
        res, b_ms, c_ms = _eval_python_diff_case(idx, case_args, fns, float_tol)
        base_total_ms += b_ms
        cand_total_ms += c_ms
        results.append(res)


    passed_count = sum(1 for r in results if r.passed)
    speedup = (base_total_ms / cand_total_ms) if cand_total_ms > 0 else 1.0

    return InvarianceReport(
        total_tests=len(results),
        passed_tests=passed_count,
        failed_tests=len(results) - passed_count,
        baseline_total_time_ms=base_total_ms,
        candidate_total_time_ms=cand_total_ms,
        speedup_ratio=speedup,
        results=results,
    )



def _eval_golden_case(case: Dict[str, Any], candidate_fn: Callable[[Any], Any]) -> TestResult:
    case_id = case["id"]
    inp = case["input"]
    expected = case["expected"]

    cand_val, cand_err, ms = _safe_invoke(candidate_fn, (inp,), {})
    actual = cand_err if cand_err else cand_val
    passed, diff = deep_compare(expected, actual)

    return TestResult(
        test_id=case_id,
        passed=passed,
        baseline_output=expected,
        candidate_output=actual,
        baseline_time_ms=0.0,
        candidate_time_ms=ms,
        diff_detail=diff,
    )


def verify_golden_master(
    candidate_fn: Callable[[Any], Any],
    golden_file: Path,
) -> InvarianceReport:
    """
    Verifies candidate outputs against a golden master JSON file.
    """
    if not golden_file.exists():
        raise FileNotFoundError(f"Golden master file {golden_file} not found.")

    golden_data = json.loads(golden_file.read_text(encoding="utf-8"))
    results = [_eval_golden_case(c, candidate_fn) for c in golden_data.get("test_cases", [])]
    total_ms = sum(r.candidate_time_ms for r in results)
    passed_count = sum(1 for r in results if r.passed)

    return InvarianceReport(
        total_tests=len(results),
        passed_tests=passed_count,
        failed_tests=len(results) - passed_count,
        baseline_total_time_ms=0.0,
        candidate_total_time_ms=total_ms,
        speedup_ratio=1.0,
        results=results,
    )


def format_report_table(report: InvarianceReport) -> str:
    lines: List[str] = []
    lines.append("=" * 96)
    lines.append(f"{'INVARIANT REGRESSION & DIFFERENTIAL PARITY REPORT':^96}")
    lines.append("=" * 96)
    lines.append(
        f"{'Test ID':<20} {'Status':<10} {'Base Time (ms)':>16} {'Cand Time (ms)':>16} {'Parity Check':>28}"
    )
    lines.append("-" * 96)

    for r in report.results:
        status = "PASSED" if r.passed else "FAILED"
        parity = "IDENTICAL" if r.passed else "REGRESSION DETECTED"
        lines.append(
            f"{r.test_id:<20} {status:<10} {r.baseline_time_ms:>16.3f} {r.candidate_time_ms:>16.3f} {parity:>28}"
        )
        if not r.passed and r.diff_detail:
            lines.append(f"  └── ❌ Diff: {r.diff_detail}")

    lines.append("=" * 96)
    status_str = "PASSED (100% Behavioral Invariance)" if report.failed_tests == 0 else f"FAILED ({report.failed_tests} regressions)"
    lines.append(
        f"Summary: {report.total_tests} tests | Passed: {report.passed_tests} | Failed: {report.failed_tests} | "
        f"Speedup: {report.speedup_ratio:.2f}x | Status: {status_str}"
    )
    lines.append("=" * 96)
    return "\n".join(lines)


def _handle_diff_python(base_path: Path, cand_path: Path, entry: str) -> InvarianceReport:
    base_mod = load_module_from_path(base_path)
    cand_mod = load_module_from_path(cand_path)
    base_fn = getattr(base_mod, entry)
    cand_fn = getattr(cand_mod, entry)
    test_cases = getattr(base_mod, "TEST_CASES", [((), {})])
    return run_differential_python_functions(base_fn, cand_fn, test_cases)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Invariant Regression Checker - Assert 100% behavioral equivalence."
    )
    parser.add_argument("--baseline", help="Baseline Python script or command")
    parser.add_argument("--candidate", help="Candidate / refactored Python script or command")
    parser.add_argument("--entrypoint", default="run", help="Function name to invoke (for Python modules)")
    parser.add_argument("--golden", help="Path to golden JSON file for snapshot verification")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    if args.golden and args.candidate:
        cand_mod = load_module_from_path(Path(args.candidate).resolve())
        report = verify_golden_master(getattr(cand_mod, args.entrypoint), Path(args.golden).resolve())
    elif args.baseline and args.candidate:
        bp, cp = Path(args.baseline).resolve(), Path(args.candidate).resolve()
        if bp.suffix == ".py" and cp.suffix == ".py":
            report = _handle_diff_python(bp, cp, args.entrypoint)
        else:
            report = run_differential_cli(args.baseline, args.candidate, ["test1", "test2", "test3"])
    else:
        print("Usage error: Provide either (--baseline and --candidate) or (--golden and --candidate).", file=sys.stderr)
        return 2

    print(json.dumps(asdict(report), indent=2) if args.json else format_report_table(report))
    return 0 if report.failed_tests == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
