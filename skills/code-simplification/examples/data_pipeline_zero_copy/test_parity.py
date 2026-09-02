#!/usr/bin/env python3
"""
Parity and Memory Allocation Test Suite for Data Pipeline Refactoring

Demonstrates 100% behavioral equivalence between multi-pass allocating pipeline and
single-pass zero-copy pipeline while proving dramatic reduction in heap allocations and latency.
"""

from __future__ import annotations

import random
import time
import tracemalloc
from typing import List

import baseline_multi_pass as baseline
import simplified_zero_copy as simplified


def generate_synthetic_logs(num_lines: int = 10000) -> str:
    endpoints = ["/api/v1/user", "/api/v1/checkout", "/health", "/metrics", "/api/v2/orders"]
    statuses = [200, 200, 200, 201, 400, 404, 500, 503]
    lines: List[str] = ["# Timestamp, Endpoint, Status, DurationMS"]

    for i in range(num_lines):
        ts = 1700000000 + i
        ep = random.choice(endpoints)
        st = random.choice(statuses)
        dur = round(random.uniform(1.0, 500.0), 3)

        if i % 20 == 0:
            lines.append("   ")  # Empty line test
        elif i % 25 == 0:
            lines.append(f"# Comment at row {i}")
        elif i % 30 == 0:
            lines.append(f"{ts},{ep},MALFORMED,12.3")  # Malformed status test
        elif i % 35 == 0:
            lines.append(f"CORRUPT_TS_{i},{ep},{st},{dur}")  # Malformed timestamp test
        else:
            lines.append(f"{ts},{ep},{st},{dur}")

    return "\n".join(lines)


def run_parity_tests() -> None:
    # Deterministic edge cases
    test_cases = [
        ("", 200, 10.0),
        ("# Only comments\n# Second comment", 200, 10.0),
        ("17000,ep,200,50.5\n17001,ep,200,100.0", 200, 60.0),
        ("17000,ep,404,50.5\n17001,ep,500,100.0", 200, 10.0),
        ("CORRUPT_TIMESTAMP,/api/v1/user,200,45.5", 200, 10.0),
        ("not_a_ts,/api/v1/user,200,50.0\n17001,/api/v1/user,200,100.0", 200, 10.0),
        ("   17000  ,/api/v1/user,200,50.0", 200, 10.0),
        ("17000.5,/api/v1/user,200,50.0", 200, 10.0),
    ]

    for raw, st, dur in test_cases:
        res_b = baseline.process_log_records_multi_pass(raw, st, dur)
        res_s = simplified.process_log_records_zero_copy(raw, st, dur)
        assert res_b == res_s, f"Parity mismatch on edge case:\nBase: {res_b}\nSimp: {res_s}"

    # Randomized large payload parity
    synthetic_logs = generate_synthetic_logs(20000)
    res_b = baseline.process_log_records_multi_pass(synthetic_logs, 200, 50.0)
    res_s = simplified.process_log_records_zero_copy(synthetic_logs, 200, 50.0)
    assert res_b == res_s, f"Parity mismatch on synthetic logs:\nBase: {res_b}\nSimp: {res_s}"

    print(f"✓ All edge cases and 20,000 synthetic log records passed with 100% parity: {res_s}")


def benchmark_memory_and_speed() -> None:
    raw_logs = generate_synthetic_logs(50000)

    # Measure Baseline Memory & Time
    tracemalloc.start()
    t0 = time.perf_counter()
    res_b = baseline.process_log_records_multi_pass(raw_logs, 200, 25.0)
    t_base = time.perf_counter() - t0
    _, peak_base = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Measure Simplified Memory & Time
    tracemalloc.start()
    t0 = time.perf_counter()
    res_s = simplified.process_log_records_zero_copy(raw_logs, 200, 25.0)
    t_simp = time.perf_counter() - t0
    _, peak_simp = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert res_b == res_s, "Parity check failed during benchmark!"

    speedup = (t_base / t_simp) if t_simp > 0 else 1.0
    mem_reduction = ((peak_base - peak_simp) / peak_base * 100.0) if peak_base > 0 else 0.0

    print("-----------------------------------------------------------------")
    print(f"Dataset Size            : 50,000 log records")
    print(f"Baseline Time           : {t_base * 1000.0:.2f} ms | Peak Memory: {peak_base / 1024:.2f} KB")
    print(f"Simplified Time         : {t_simp * 1000.0:.2f} ms | Peak Memory: {peak_simp / 1024:.2f} KB")
    print(f"Latency Improvement     : {speedup:.2f}x faster")
    print(f"Peak Memory Reduction   : {mem_reduction:.1f}% less memory")
    print("-----------------------------------------------------------------")


def main() -> int:
    print("=================================================================")
    print(" Running Data Pipeline Zero-Copy Parity & Benchmark Suite")
    print("=================================================================")
    run_parity_tests()
    benchmark_memory_and_speed()
    print("Status: 100% Invariant Parity PASSED")
    print("=================================================================")
    return 0


if __name__ == "__main__":
    main()
