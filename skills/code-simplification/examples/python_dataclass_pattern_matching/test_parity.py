#!/usr/bin/env python3
"""
Parity Test Suite for Python Dataclass & Pattern Matching Refactoring

Verifies 100% semantic equivalence between OOP Visitor pattern and `@dataclass(slots=True)`
pattern matching across arithmetic expressions, error conditions, and randomized expression trees.
"""

from __future__ import annotations

import math
import random
import sys
import time
from typing import Any, Dict, Tuple

import baseline_oop_hierarchy as baseline
import simplified_dataclass_match as simplified


def build_ast_pair(depth: int, max_depth: int = 4) -> Tuple[baseline.ASTNode, simplified.Expr]:
    """
    Recursively builds identical expression trees for both baseline and simplified implementations.
    """
    if depth >= max_depth or (depth > 1 and random.random() < 0.4):
        if random.random() < 0.5:
            val = round(random.uniform(-50.0, 50.0), 2)
            return baseline.LiteralNode(val), simplified.Literal(val)
        else:
            var = random.choice(["x", "y", "z", "w"])
            return baseline.VariableNode(var), simplified.Variable(var)

    kind = random.choice(["binary", "unary"])
    if kind == "unary":
        op = random.choice(["+", "-"])
        b_child, s_child = build_ast_pair(depth + 1, max_depth)
        return baseline.UnaryOpNode(op, b_child), simplified.UnaryOp(op, s_child)
    else:
        op = random.choice(["+", "-", "*", "/"])
        b_left, s_left = build_ast_pair(depth + 1, max_depth)
        b_right, s_right = build_ast_pair(depth + 1, max_depth)
        return baseline.BinaryOpNode(op, b_left, b_right), simplified.BinaryOp(op, s_left, s_right)


def run_deterministic_tests() -> None:
    env = {"x": 10.0, "y": 2.5, "z": 4.0, "w": -1.5}

    # Test 1: (x * y) + (z / w)
    b_ast = baseline.BinaryOpNode(
        "+",
        baseline.BinaryOpNode("*", baseline.VariableNode("x"), baseline.VariableNode("y")),
        baseline.BinaryOpNode("/", baseline.VariableNode("z"), baseline.VariableNode("w")),
    )
    s_ast = simplified.BinaryOp(
        "+",
        simplified.BinaryOp("*", simplified.Variable("x"), simplified.Variable("y")),
        simplified.BinaryOp("/", simplified.Variable("z"), simplified.Variable("w")),
    )

    res_b = baseline.evaluate_expression(b_ast, env)
    res_s = simplified.evaluate_expression(s_ast, env)
    assert math.isclose(res_b, res_s, rel_tol=1e-9), f"Mismatch: {res_b} != {res_s}"

    # Test 2: Division by zero exception parity
    b_zero = baseline.BinaryOpNode("/", baseline.LiteralNode(10.0), baseline.LiteralNode(0.0))
    s_zero = simplified.BinaryOp("/", simplified.Literal(10.0), simplified.Literal(0.0))

    try:
        baseline.evaluate_expression(b_zero, env)
        assert False, "Baseline should raise ZeroDivisionError"
    except ZeroDivisionError:
        pass

    try:
        simplified.evaluate_expression(s_zero, env)
        assert False, "Simplified should raise ZeroDivisionError"
    except ZeroDivisionError:
        pass

    # Test 3: Missing variable KeyError parity
    b_key = baseline.VariableNode("missing_var")
    s_key = simplified.Variable("missing_var")

    try:
        baseline.evaluate_expression(b_key, env)
        assert False, "Baseline should raise KeyError"
    except KeyError:
        pass

    try:
        simplified.evaluate_expression(s_key, env)
        assert False, "Simplified should raise KeyError"
    except KeyError:
        pass

    print("✓ Deterministic arithmetic and exception parity tests PASSED.")


def run_property_fuzzing(iterations: int = 5000) -> Tuple[int, float, float]:
    env = {"x": 12.5, "y": -4.2, "z": 3.0, "w": 0.5}
    base_t = 0.0
    simp_t = 0.0
    evaluated_count = 0

    for _ in range(iterations):
        b_ast, s_ast = build_ast_pair(0, max_depth=4)

        t0 = time.perf_counter()
        base_err = None
        base_val = None
        try:
            base_val = baseline.evaluate_expression(b_ast, env)
        except Exception as e:
            base_err = type(e).__name__
        base_t += time.perf_counter() - t0

        t0 = time.perf_counter()
        simp_err = None
        simp_val = None
        try:
            simp_val = simplified.evaluate_expression(s_ast, env)
        except Exception as e:
            simp_err = type(e).__name__
        simp_t += time.perf_counter() - t0

        if base_err or simp_err:
            assert base_err == simp_err, f"Exception mismatch: {base_err} != {simp_err}"
        else:
            assert math.isclose(base_val, simp_val, rel_tol=1e-7, abs_tol=1e-7), (
                f"Numeric divergence: {base_val} != {simp_val}"
            )
        evaluated_count += 1

    print(f"✓ Randomized property fuzzing passed ({iterations} random expression trees, 100% parity).")
    return evaluated_count, base_t, simp_t


def main() -> int:
    print("=================================================================")
    print(" Running Python Dataclass & Pattern Matching Parity Suite")
    print("=================================================================")
    run_deterministic_tests()
    count, base_t, simp_t = run_property_fuzzing(5000)

    speedup = (base_t / simp_t) if simp_t > 0 else 1.0
    print("-----------------------------------------------------------------")
    print(f"Random AST Trees Evaluated : {count}")
    print(f"Baseline Time (Visitor)    : {base_t * 1000.0:.2f} ms")
    print(f"Simplified Time (Match)    : {simp_t * 1000.0:.2f} ms")
    print(f"Speedup Ratio              : {speedup:.2f}x faster")
    print("Status                     : 100% Invariant Parity PASSED")
    print("=================================================================")
    return 0


if __name__ == "__main__":
    main()
