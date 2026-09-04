#!/usr/bin/env python3
"""
Differential Test Runner
========================
Executes a baseline implementation and an optimized implementation across
numeric boundary and randomized vectors to compare outputs on those cases.

Usage:
  python3 differential_test_runner.py --baseline <cmd> --optimized <cmd> [options]
  python3 differential_test_runner.py --test-internal
"""

import argparse
import json
import math
import random
import shlex
import subprocess
import sys
from typing import Any


def compare_outputs(
    base_out: str, opt_out: str, tolerance: float = 0.0
) -> tuple[bool, str | None]:
    """
    Compares two string outputs. Supports both exact string matching
    and floating-point token-by-token comparison within tolerance.
    """
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Tolerance must be finite and nonnegative")
    if base_out == opt_out:
        return True, None
    if tolerance == 0:
        return False, "Exact output mismatch"
    base_tokens, opt_tokens = base_out.split(), opt_out.split()
    if len(base_tokens) != len(opt_tokens):
        return False, "Token count mismatch"
    for i, (left, right) in enumerate(zip(base_tokens, opt_tokens)):
        if left == right:
            continue
        try:
            # Integer outputs remain exact even with floating point tolerance.
            if left.lstrip("+-").isdigit() or right.lstrip("+-").isdigit():
                equal = (
                    left.lstrip("+-").isdigit()
                    and right.lstrip("+-").isdigit()
                    and int(left) == int(right)
                )
            else:
                x, y = float(left), float(right)
                equal = (
                    math.isfinite(x)
                    and math.isfinite(y)
                    and math.isclose(x, y, rel_tol=tolerance, abs_tol=tolerance)
                )
        except ValueError:
            equal = False
        if not equal:
            return False, f"Mismatch at token {i}: {left!r} != {right!r}"
    return True, None


def run_differential_test(
    baseline_cmd: str,
    optimized_cmd: str,
    iterations: int = 20,
    tolerance: float = 0.0,
    seed: int = 42,
) -> dict[str, Any]:
    """Runs differential testing across randomized iterations."""
    if iterations <= 0:
        raise ValueError("At least one iteration is required")
    compare_outputs("", "", tolerance)
    random.seed(seed)
    results = {
        "passed": True,
        "total_iterations": iterations,
        "successful_iterations": 0,
        "failures": [],
    }

    print(f"[*] Starting Differential Parity Test ({iterations} iterations)...")
    print(f"    Baseline:  {baseline_cmd}")
    print(f"    Optimized: {optimized_cmd}")
    print(f"    Tolerance: {tolerance:.2e}\n")

    for i in range(1, iterations + 1):
        # Generate varied test inputs (boundary, small, large, pseudo-random)
        if i == 1:
            test_vector = [0]
        elif i == 2:
            test_vector = [1, -1, 0, 2147483647, -2147483648]
        elif i == 3:
            test_vector = [random.uniform(-1000.0, 1000.0) for _ in range(16)]
        else:
            length = random.randint(10, 500)
            test_vector = [random.uniform(-1e4, 1e4) for _ in range(length)]

        input_str = " ".join(str(x) for x in test_vector)

        # Execute baseline
        try:
            p_base = subprocess.run(
                shlex.split(baseline_cmd),
                input=input_str,
                text=True,
                capture_output=True,
                check=False,
                timeout=10,
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as e:
            results["passed"] = False
            results["failures"].append(
                {"iteration": i, "error": f"Baseline execution failed: {e}"}
            )
            break

        # Execute optimized
        try:
            p_opt = subprocess.run(
                shlex.split(optimized_cmd),
                input=input_str,
                text=True,
                capture_output=True,
                check=False,
                timeout=10,
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as e:
            results["passed"] = False
            results["failures"].append(
                {"iteration": i, "error": f"Optimized execution failed: {e}"}
            )
            break

        if p_base.returncode != 0 or p_opt.returncode != 0:
            results["passed"] = False
            results["failures"].append(
                {
                    "iteration": i,
                    "error": f"Exit code mismatch: baseline {p_base.returncode} vs optimized {p_opt.returncode}",
                }
            )
            break

        is_match, reason = compare_outputs(p_base.stdout, p_opt.stdout, tolerance)
        if p_base.stderr != p_opt.stderr:
            is_match, reason = False, "stderr mismatch"
        if not is_match:
            results["passed"] = False
            results["failures"].append(
                {
                    "iteration": i,
                    "reason": reason,
                    "baseline_sample": p_base.stdout[:200],
                    "optimized_sample": p_opt.stdout[:200],
                }
            )
            print(f"[-] FAILED at iteration {i}: {reason}")
            break
        else:
            results["successful_iterations"] += 1

    if results["passed"]:
        print(f"[+] SUCCESS: Outputs matched for {iterations} test iterations.\n")
    else:
        print(
            f"[-] DIFFERENTIAL PARITY CHECK FAILED: {len(results['failures'])} errors detected.\n"
        )

    return results


def run_internal_self_test():
    """Validates the differential tester itself against synthetic functions."""
    print("[*] Running internal self-test suite for differential_test_runner...")

    # 1. Matching exact outputs
    res, _msg = compare_outputs("100 200 300\n", "100 200 300\n")
    assert res is True, "Exact match should pass"

    # 2. Matching within floating point tolerance
    res, _msg = compare_outputs("10.000001 20.5", "10.000002 20.5", tolerance=1e-4)
    assert res is True, "Float tolerance match should pass"

    # 3. Detecting precision error exceeding tolerance
    res, _msg = compare_outputs("10.000001", "10.5", tolerance=1e-4)
    assert res is False, "Exceeding tolerance should fail"

    # 4. Detecting token count mismatch
    res, _msg = compare_outputs("1 2 3", "1 2")
    assert res is False, "Length mismatch should fail"

    print("[+] Internal self-test passed successfully.")


def main():
    parser = argparse.ArgumentParser(
        description="Differential Test Runner for Optimization Verification"
    )
    parser.add_argument("--baseline", help="Command to execute baseline implementation")
    parser.add_argument(
        "--optimized", help="Command to execute optimized implementation"
    )
    parser.add_argument(
        "--iterations", type=int, default=30, help="Number of randomized test runs"
    )
    parser.add_argument(
        "--tolerance", type=float, default=0.0, help="Floating point tolerance"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility"
    )
    parser.add_argument("--json-output", help="Path to write JSON results")
    parser.add_argument(
        "--test-internal", action="store_true", help="Run internal validation test"
    )

    args = parser.parse_args()

    if args.test_internal:
        run_internal_self_test()
        return

    if not args.baseline or not args.optimized:
        parser.print_help()
        sys.exit(1)

    if args.iterations <= 0 or not math.isfinite(args.tolerance) or args.tolerance < 0:
        parser.error("iterations must be positive and tolerance finite and nonnegative")

    result = run_differential_test(
        baseline_cmd=args.baseline,
        optimized_cmd=args.optimized,
        iterations=args.iterations,
        tolerance=args.tolerance,
        seed=args.seed,
    )

    if args.json_output:
        with open(args.json_output, "w") as f:
            json.dump(result, f, indent=2)

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
