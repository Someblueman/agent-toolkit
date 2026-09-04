#!/usr/bin/env python3
"""
Benchmark Comparator
====================
Runs statistical benchmark comparisons between a baseline implementation
and an optimized implementation. Computes mean, median, IQR, percentiles (p50, p95, p99),
speedup ratios, 95% confidence intervals, and outputs formatted markdown tables.

Usage:
  python3 benchmark_comparator.py --baseline <cmd> --optimized <cmd> [options]
  python3 benchmark_comparator.py --test-internal
"""

import argparse
import json
import math
import shlex
import statistics
import subprocess
import sys
import time
from typing import Any


def compute_statistics(samples: list[float]) -> dict[str, float]:
    """Computes comprehensive descriptive statistics from timing samples in milliseconds."""
    if len(samples) < 2 or any(not math.isfinite(x) or x <= 0 for x in samples):
        raise ValueError("At least two positive finite samples required")

    sorted_s = sorted(samples)
    n = len(sorted_s)

    mean_val = sum(sorted_s) / n
    variance = sum((x - mean_val) ** 2 for x in sorted_s) / (n - 1) if n > 1 else 0.0
    std_dev = math.sqrt(variance)

    def percentile(p: float) -> float:
        k = (n - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_s[int(k)]
        d0 = sorted_s[int(f)] * (c - k)
        d1 = sorted_s[int(c)] * (k - f)
        return d0 + d1

    p25 = percentile(0.25)
    p50 = percentile(0.50)
    p75 = percentile(0.75)
    p95 = percentile(0.95)
    p99 = percentile(0.99)
    iqr = p75 - p25

    return {
        "count": n,
        "min_ms": sorted_s[0],
        "max_ms": sorted_s[-1],
        "mean_ms": mean_val,
        "std_dev_ms": std_dev,
        "median_ms": p50,
        "p25_ms": p25,
        "p75_ms": p75,
        "iqr_ms": iqr,
        "p95_ms": p95,
        "p99_ms": p99,
    }


def collect_timing_samples(cmd: str, runs: int, warmups: int) -> list[float]:
    """Executes command and records runtime latency per iteration in milliseconds."""
    # Warmup runs
    for _ in range(warmups):
        subprocess.run(shlex.split(cmd), capture_output=True, timeout=60, check=True)

    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        res = subprocess.run(
            shlex.split(cmd), capture_output=True, timeout=60, check=True
        )
        end = time.perf_counter()
        if res.returncode != 0:
            raise RuntimeError(
                f"Command '{cmd}' failed with return code {res.returncode}: {res.stderr.decode('utf-8', errors='ignore')}"
            )
        samples.append((end - start) * 1000.0)  # Convert to ms
    return samples


def bootstrap_speedup_ci(
    base_samples: list[float], opt_samples: list[float], iterations: int = 2000
) -> tuple[float, float]:
    """Computes 95% bootstrap confidence interval for the speedup ratio (base_median / opt_median)."""
    import random

    compute_statistics(base_samples)
    compute_statistics(opt_samples)
    if iterations < 2:
        raise ValueError("At least two bootstrap iterations required")
    rng = random.Random(42)
    n_b = len(base_samples)
    n_o = len(opt_samples)
    speedups = []

    for _ in range(iterations):
        b_resample = [rng.choice(base_samples) for _ in range(n_b)]
        o_resample = [rng.choice(opt_samples) for _ in range(n_o)]
        b_med = statistics.median(b_resample)
        o_med = statistics.median(o_resample)
        if o_med > 0:
            speedups.append(b_med / o_med)

    if not speedups:
        return 1.0, 1.0
    speedups.sort()
    low_idx = int(0.025 * len(speedups))
    high_idx = int(0.975 * len(speedups))
    return speedups[low_idx], speedups[high_idx]


def compare_benchmarks(
    baseline_cmd: str, optimized_cmd: str, runs: int = 15, warmups: int = 3
) -> dict[str, Any]:
    """Runs full comparative benchmark and returns statistical summary."""
    if runs < 2 or warmups < 0:
        raise ValueError("runs >= 2 and warmups >= 0 required")
    base_samples, opt_samples = [], []
    commands = [(baseline_cmd, base_samples), (optimized_cmd, opt_samples)]
    for i in range(warmups + runs):
        for cmd, samples in commands if i % 2 == 0 else commands[::-1]:
            elapsed = collect_timing_samples(cmd, 1, 0)[0]
            if i >= warmups:
                samples.append(elapsed)
    base_stats, opt_stats = (
        compute_statistics(base_samples),
        compute_statistics(opt_samples),
    )

    speedup = (
        base_stats["median_ms"] / opt_stats["median_ms"]
        if opt_stats["median_ms"] > 0
        else 0.0
    )
    ci_low, ci_high = bootstrap_speedup_ci(base_samples, opt_samples)
    latency_reduction_pct = (
        ((base_stats["median_ms"] - opt_stats["median_ms"]) / base_stats["median_ms"])
        * 100.0
        if base_stats["median_ms"] > 0
        else 0.0
    )

    summary = {
        "baseline_cmd": baseline_cmd,
        "optimized_cmd": optimized_cmd,
        "runs": runs,
        "baseline_samples_ms": base_samples,
        "optimized_samples_ms": opt_samples,
        "method": "Alternating order; fresh-process elapsed including startup; approximate percentile bootstrap median ratio, seed 42, iid assumption; small samples may understate uncertainty",
        "baseline_stats": base_stats,
        "optimized_stats": opt_stats,
        "speedup_ratio": speedup,
        "speedup_95_ci": [ci_low, ci_high],
        "latency_reduction_pct": latency_reduction_pct,
    }

    # Print summary table
    print("\n" + "=" * 70)
    print("                      BENCHMARK COMPARISON RESULTS                    ")
    print("=" * 70)
    print(
        f"{'Metric':<25} | {'Baseline':<18} | {'Optimized':<18} | {'Improvement':<12}"
    )
    print("-" * 70)
    print(
        f"{'Median Latency':<25} | {base_stats['median_ms']:>14.3f} ms | {opt_stats['median_ms']:>14.3f} ms | {speedup:>10.2f}x"
    )
    print(
        f"{'Mean Latency':<25} | {base_stats['mean_ms']:>14.3f} ms | {opt_stats['mean_ms']:>14.3f} ms | {base_stats['mean_ms'] / opt_stats['mean_ms']:>10.2f}x"
    )
    print(
        f"{'Std Deviation':<25} | {base_stats['std_dev_ms']:>14.3f} ms | {opt_stats['std_dev_ms']:>14.3f} ms | {'-':>12}"
    )
    print(
        f"{'p95 Latency':<25} | {base_stats['p95_ms']:>14.3f} ms | {opt_stats['p95_ms']:>14.3f} ms | {base_stats['p95_ms'] / opt_stats['p95_ms']:>10.2f}x"
    )
    print(
        f"{'Min Latency':<25} | {base_stats['min_ms']:>14.3f} ms | {opt_stats['min_ms']:>14.3f} ms | {base_stats['min_ms'] / opt_stats['min_ms']:>10.2f}x"
    )
    print("-" * 70)
    print(f"Overall Speedup: {speedup:.2f}x (95% CI: [{ci_low:.2f}x - {ci_high:.2f}x])")
    print(f"Latency Reduction: {latency_reduction_pct:.2f}%\n")

    return summary


def run_internal_self_test():
    """Validates statistical functions against known distributions."""
    print("[*] Running internal self-test for benchmark_comparator...")
    samples = [10.0, 12.0, 11.0, 10.5, 11.5, 10.2, 11.8, 10.8, 10.9, 11.1]
    stats = compute_statistics(samples)
    assert abs(stats["median_ms"] - 10.95) < 0.1, (
        f"Median incorrect: {stats['median_ms']}"
    )
    assert stats["count"] == 10
    assert stats["min_ms"] == 10.0
    assert stats["max_ms"] == 12.0

    ci_low, ci_high = bootstrap_speedup_ci(samples, [s / 2.0 for s in samples])
    assert 1.8 <= ci_low <= 2.2, f"CI low out of range: {ci_low}"
    assert 1.8 <= ci_high <= 2.2, f"CI high out of range: {ci_high}"
    print("[+] Internal statistical validation passed.")


def main():
    parser = argparse.ArgumentParser(description="Statistical Benchmark Comparator")
    parser.add_argument("--baseline", help="Command for baseline execution")
    parser.add_argument("--optimized", help="Command for optimized execution")
    parser.add_argument(
        "--runs", type=int, default=15, help="Number of benchmark sample runs"
    )
    parser.add_argument(
        "--warmups", type=int, default=3, help="Number of warmup executions"
    )
    parser.add_argument("--json-output", help="Path to write benchmark results JSON")
    parser.add_argument(
        "--test-internal",
        action="store_true",
        help="Run internal statistical self-test",
    )

    args = parser.parse_args()

    if args.test_internal:
        run_internal_self_test()
        return

    if not args.baseline or not args.optimized:
        parser.print_help()
        sys.exit(1)

    if args.runs < 2 or args.warmups < 0:
        parser.error("runs >= 2 and warmups >= 0 required")

    res = compare_benchmarks(
        baseline_cmd=args.baseline,
        optimized_cmd=args.optimized,
        runs=args.runs,
        warmups=args.warmups,
    )

    if args.json_output:
        with open(args.json_output, "w") as f:
            json.dump(res, f, indent=2)


if __name__ == "__main__":
    main()
