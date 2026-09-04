#!/usr/bin/env python3
"""
Statistical Benchmark Runner with Automated Warmup and Noise Analysis.

Executes a target command over multiple warmup and measurement iterations,
capturing high-resolution timings, computing rigorous statistical distributions
(mean, median, stdev, IQR, percentiles, confidence intervals), and evaluating
measurement stability/noise.
"""

import argparse
import json
import math
import os
import random
import statistics
import subprocess
import sys
import time
from typing import Any


def calculate_percentile(sorted_data: list[float], percentile: float) -> float:
    """Calculate the p-th percentile of sorted data using linear interpolation."""
    if not sorted_data:
        return 0.0
    k = (len(sorted_data) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)] * (c - k)
    d1 = sorted_data[int(c)] * (k - f)
    return d0 + d1


def compute_statistics(samples_ms: list[float]) -> dict[str, Any]:
    """Compute comprehensive statistical metrics from timing samples in milliseconds."""
    n = len(samples_ms)
    if n < 2 or any(not math.isfinite(x) or x <= 0 for x in samples_ms):
        raise ValueError("At least two finite positive samples are required")

    sorted_samples = sorted(samples_ms)
    mean_val = sum(sorted_samples) / n
    variance = (
        sum((x - mean_val) ** 2 for x in sorted_samples) / (n - 1) if n > 1 else 0.0
    )
    stdev = math.sqrt(variance)
    cv_percent = (stdev / mean_val * 100.0) if mean_val > 0 else 0.0

    min_val = sorted_samples[0]
    max_val = sorted_samples[-1]
    p25 = calculate_percentile(sorted_samples, 25.0)
    p50 = calculate_percentile(sorted_samples, 50.0)
    p75 = calculate_percentile(sorted_samples, 75.0)
    p90 = calculate_percentile(sorted_samples, 90.0)
    p95 = calculate_percentile(sorted_samples, 95.0)
    p99 = calculate_percentile(sorted_samples, 99.0)
    iqr = p75 - p25

    # Tukey's fences for outlier detection
    lower_fence = p25 - 1.5 * iqr
    upper_fence = p75 + 1.5 * iqr
    outliers = [x for x in sorted_samples if x < lower_fence or x > upper_fence]

    # Percentile bootstrap of the mean: approximate, assumes independent samples.
    rng = random.Random(42)
    means = sorted(statistics.mean(rng.choices(samples_ms, k=n)) for _ in range(2000))
    ci_low, ci_high = (
        calculate_percentile(means, 2.5),
        calculate_percentile(means, 97.5),
    )
    ci95_margin = (ci_high - ci_low) / 2
    noise_status = "Descriptive CV only; assess uncertainty against the target effect"

    return {
        "sample_count": n,
        "mean_ms": round(mean_val, 4),
        "stdev_ms": round(stdev, 4),
        "variance_ms2": round(variance, 6),
        "cv_percent": round(cv_percent, 2),
        "min_ms": round(min_val, 4),
        "max_ms": round(max_val, 4),
        "median_ms": round(p50, 4),
        "p25_ms": round(p25, 4),
        "p75_ms": round(p75, 4),
        "p90_ms": round(p90, 4),
        "p95_ms": round(p95, 4),
        "p99_ms": round(p99, 4),
        "iqr_ms": round(iqr, 4),
        "ci95_margin_ms": round(ci95_margin, 4),
        "ci95_low_ms": ci_low,
        "ci95_high_ms": ci_high,
        "outlier_count": len(outliers),
        "noise_status": noise_status,
        "raw_samples_ms": list(samples_ms),
        "ci_method": "Approximate percentile bootstrap mean, 2000 resamples, seed 42; iid assumption; small samples may understate uncertainty",
        "measurement": "Fresh-process elapsed time, including startup; warmups do not warm a persistent runtime",
    }


def execute_single_run(
    cmd: list[str],
    quiet: bool = True,
    timeout_sec: float | None = None,
    affinity_core: int | None = None,
) -> tuple[float, int]:
    """Execute a single run of the target command and return (elapsed_time_ms, exit_code)."""
    env = os.environ.copy()
    exec_cmd = list(cmd)

    # Apply core pinning via taskset if specified on Linux
    if affinity_core is not None and sys.platform.startswith("linux"):
        exec_cmd = ["taskset", "-c", str(affinity_core)] + exec_cmd

    stdout_dest = subprocess.DEVNULL if quiet else None
    stderr_dest = subprocess.DEVNULL if quiet else None

    start_ns = time.perf_counter_ns()
    try:
        proc = subprocess.run(
            exec_cmd,
            stdout=stdout_dest,
            stderr=stderr_dest,
            env=env,
            timeout=timeout_sec,
            check=False,
        )
        end_ns = time.perf_counter_ns()
        elapsed_ms = (end_ns - start_ns) / 1_000_000.0
        return elapsed_ms, proc.returncode
    except subprocess.TimeoutExpired:
        end_ns = time.perf_counter_ns()
        return (end_ns - start_ns) / 1_000_000.0, -1


def print_stats_table(stats: dict[str, Any], command_str: str, warmups: int) -> None:
    """Print formatted statistical summary table to stdout."""
    print("=" * 65)
    print("BENCHMARK STATISTICAL REPORT")
    print(f"Command:    {command_str}")
    print(f"Iterations: {stats['sample_count']} timed (+ {warmups} warmup)")
    print(f"Stability:  {stats['noise_status']}")
    print("-" * 65)
    print(f"{'Metric':<25} | {'Value (ms)':<15} | {'Notes':<18}")
    print("-" * 65)
    print(
        f"{'Mean (μ)':<25} | {stats['mean_ms']:<15.4f} | +/- {stats['stdev_ms']:.4f} ms"
    )
    print(f"{'Median (p50)':<25} | {stats['median_ms']:<15.4f} | 50th percentile")
    print(
        f"{'Min ... Max':<25} | {stats['min_ms']:<7.3f} ... {stats['max_ms']:<6.3f} | Range: {stats['max_ms'] - stats['min_ms']:.3f} ms"
    )
    print(
        f"{'Std Dev (σ)':<25} | {stats['stdev_ms']:<15.4f} | CV = {stats['cv_percent']:.2f}%"
    )
    print(f"{'IQR (p75 - p25)':<25} | {stats['iqr_ms']:<15.4f} | Middle 50% spread")
    print(
        f"{'95% Conf Interval':<25} | [{stats['ci95_low_ms']:.3f}, {stats['ci95_high_ms']:.3f}] | +/- {stats['ci95_margin_ms']:.3f} ms"
    )
    print(f"{'90th Percentile (p90)':<25} | {stats['p90_ms']:<15.4f} | ")
    print(f"{'95th Percentile (p95)':<25} | {stats['p95_ms']:<15.4f} | Tail latency")
    print(f"{'99th Percentile (p99)':<25} | {stats['p99_ms']:<15.4f} | Extreme tail")
    print(f"{'Outliers Detected':<25} | {stats['outlier_count']:<15} | Tukey's 1.5*IQR")
    print(stats["ci_method"])
    print(stats["measurement"])
    print("=" * 65)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Statistically rigorous benchmark runner with warmup and noise analysis."
    )
    parser.add_argument(
        "--warmup",
        "-w",
        type=int,
        default=3,
        help="Number of untimed warmup iterations (default: 3)",
    )
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=30,
        help="Number of timed measurement iterations (default: 30)",
    )
    parser.add_argument(
        "--json-out",
        "-j",
        type=str,
        default=None,
        help="Path to export statistical results in JSON format",
    )
    parser.add_argument(
        "--core",
        "-c",
        type=int,
        default=None,
        help="Physical CPU core ID to pin execution (Linux taskset)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Per-iteration execution timeout in seconds (default: 60.0)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show command stdout and stderr during benchmark runs",
    )
    parser.add_argument(
        "cmd",
        nargs=argparse.REMAINDER,
        help="Command to benchmark (prefix with -- if using flags)",
    )

    args = parser.parse_args()

    if (
        args.iterations < 2
        or args.warmup < 0
        or not math.isfinite(args.timeout)
        or args.timeout <= 0
    ):
        parser.error(
            "iterations >= 2, warmup >= 0, and finite positive timeout required"
        )

    # Clean leading '--' from command args if present
    target_cmd = args.cmd
    if target_cmd and target_cmd[0] == "--":
        target_cmd = target_cmd[1:]

    if not target_cmd:
        parser.print_help()
        print("\nError: No target command specified to benchmark.", file=sys.stderr)
        return 1

    command_str = " ".join(target_cmd)
    quiet = not args.verbose

    # 1. Warmup Phase
    if args.warmup > 0:
        if not quiet:
            print(f"[*] Executing {args.warmup} warmup iterations...", file=sys.stderr)
        for i in range(args.warmup):
            _, code = execute_single_run(
                target_cmd,
                quiet=quiet,
                timeout_sec=args.timeout,
                affinity_core=args.core,
            )
            if code != 0:
                print(
                    f"Error: Warmup iteration {i + 1} exited with non-zero return code {code}",
                    file=sys.stderr,
                )

                return 1

    # 2. Measurement Phase
    samples_ms: list[float] = []
    for i in range(args.iterations):
        elapsed_ms, code = execute_single_run(
            target_cmd,
            quiet=quiet,
            timeout_sec=args.timeout,
            affinity_core=args.core,
        )
        if code != 0:
            print(
                f"Error: Iteration {i + 1} failed with exit code {code}",
                file=sys.stderr,
            )
            return code
        samples_ms.append(elapsed_ms)

    # 3. Statistical Analysis
    stats = compute_statistics(samples_ms)
    stats["command"] = command_str
    stats["warmup_count"] = args.warmup

    # 4. Output Presentation
    print_stats_table(stats, command_str, args.warmup)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
        print(f"[+] JSON report saved to: {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
