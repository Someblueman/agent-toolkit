#!/usr/bin/env python3
"""
Differential Test Runner
========================
Executes a baseline implementation and an optimized implementation across
randomized and boundary test vectors to verify 100% differential correctness
and parity before performance optimizations are accepted.

Usage:
  python3 differential_test_runner.py --baseline <cmd> --optimized <cmd> [options]
  python3 differential_test_runner.py --test-internal
"""

import argparse
import json
import math
import os
import random
import subprocess
import sys
import tempfile
from typing import List, Tuple, Dict, Any, Optional


def compare_outputs(base_out: str, opt_out: str, tolerance: float = 1e-5) -> Tuple[bool, Optional[str]]:
    """
    Compares two string outputs. Supports both exact string matching
    and floating-point token-by-token comparison within tolerance.
    """
    if base_out == opt_out:
        return True, None

    base_tokens = base_out.strip().split()
    opt_tokens = opt_out.strip().split()

    if len(base_tokens) != len(opt_tokens):
        return False, f"Token count mismatch: baseline has {len(base_tokens)} tokens, optimized has {len(opt_tokens)} tokens."

    for i, (b_tok, o_tok) in enumerate(zip(base_tokens, opt_tokens)):
        if b_tok == o_tok:
            continue
        try:
            b_val = float(b_tok)
            o_val = float(o_tok)
            if math.isnan(b_val) and math.isnan(o_val):
                continue
            if math.isinf(b_val) and math.isinf(o_val) and (b_val > 0) == (o_val > 0):
                continue
            diff = abs(b_val - o_val)
            if diff > tolerance and (abs(b_val) > 0 and diff / abs(b_val) > tolerance):
                return False, f"Float mismatch at token {i}: baseline '{b_tok}' vs optimized '{o_tok}' (diff: {diff:.2e} > tol {tolerance:.2e})"
        except ValueError:
            return False, f"String mismatch at token {i}: baseline '{b_tok}' vs optimized '{o_tok}'"

    return True, None


def run_differential_test(
    baseline_cmd: str,
    optimized_cmd: str,
    iterations: int = 20,
    tolerance: float = 1e-5,
    seed: int = 42
) -> Dict[str, Any]:
    """Runs differential testing across randomized iterations."""
    random.seed(seed)
    results = {
        "passed": True,
        "total_iterations": iterations,
        "successful_iterations": 0,
        "failures": []
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
                baseline_cmd,
                input=input_str,
                text=True,
                shell=True,
                capture_output=True,
                timeout=10
            )
        except Exception as e:
            results["passed"] = False
            results["failures"].append({"iteration": i, "error": f"Baseline execution failed: {e}"})
            break

        # Execute optimized
        try:
            p_opt = subprocess.run(
                optimized_cmd,
                input=input_str,
                text=True,
                shell=True,
                capture_output=True,
                timeout=10
            )
        except Exception as e:
            results["passed"] = False
            results["failures"].append({"iteration": i, "error": f"Optimized execution failed: {e}"})
            break

        if p_base.returncode != p_opt.returncode:
            results["passed"] = False
            results["failures"].append({
                "iteration": i,
                "error": f"Exit code mismatch: baseline {p_base.returncode} vs optimized {p_opt.returncode}"
            })
            break

        is_match, reason = compare_outputs(p_base.stdout, p_opt.stdout, tolerance)
        if not is_match:
            results["passed"] = False
            results["failures"].append({
                "iteration": i,
                "reason": reason,
                "baseline_sample": p_base.stdout[:200],
                "optimized_sample": p_opt.stdout[:200]
            })
            print(f"[-] FAILED at iteration {i}: {reason}")
            break
        else:
            results["successful_iterations"] += 1

    if results["passed"]:
        print(f"[+] SUCCESS: 100% parity verified across all {iterations} test iterations.\n")
    else:
        print(f"[-] DIFFERENTIAL PARITY CHECK FAILED: {len(results['failures'])} errors detected.\n")

    return results


def run_internal_self_test():
    """Validates the differential tester itself against synthetic functions."""
    print("[*] Running internal self-test suite for differential_test_runner...")
    
    # 1. Matching exact outputs
    res, msg = compare_outputs("100 200 300\n", "100 200 300\n")
    assert res is True, "Exact match should pass"

    # 2. Matching within floating point tolerance
    res, msg = compare_outputs("10.000001 20.5", "10.000002 20.5", tolerance=1e-4)
    assert res is True, "Float tolerance match should pass"

    # 3. Detecting precision error exceeding tolerance
    res, msg = compare_outputs("10.000001", "10.5", tolerance=1e-4)
    assert res is False, "Exceeding tolerance should fail"

    # 4. Detecting token count mismatch
    res, msg = compare_outputs("1 2 3", "1 2")
    assert res is False, "Length mismatch should fail"

    print("[+] Internal self-test passed successfully.")


def main():
    parser = argparse.ArgumentParser(description="Differential Test Runner for Optimization Verification")
    parser.add_argument("--baseline", help="Command to execute baseline implementation")
    parser.add_argument("--optimized", help="Command to execute optimized implementation")
    parser.add_argument("--iterations", type=int, default=30, help="Number of randomized test runs")
    parser.add_argument("--tolerance", type=float, default=1e-5, help="Floating point tolerance")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--json-output", help="Path to write JSON results")
    parser.add_argument("--test-internal", action="store_true", help="Run internal validation test")

    args = parser.parse_args()

    if args.test_internal:
        run_internal_self_test()
        return

    if not args.baseline or not args.optimized:
        parser.print_help()
        sys.exit(1)

    result = run_differential_test(
        baseline_cmd=args.baseline,
        optimized_cmd=args.optimized,
        iterations=args.iterations,
        tolerance=args.tolerance,
        seed=args.seed
    )

    if args.json_output:
        with open(args.json_output, "w") as f:
            json.dump(result, f, indent=2)

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
