#!/usr/bin/env python3
"""
Python Managed Profiling Example: CPU vs Memory Allocation Bottlenecks.

Demonstrates:
1. Identifying CPU hotspots using cProfile and pstats.
2. Identifying memory allocation bloat using tracemalloc.
3. Verification assertion ensuring optimized logic preserves mathematical equivalence.
"""

import cProfile
import io
import math
import pstats
from pstats import SortKey
import time
import tracemalloc
from typing import List, Tuple


# --- Bottleneck Workload Definitions ---

def cpu_heavy_is_prime(n: int) -> bool:
    """CPU Bottleneck: Unoptimized trial division checking every integer up to n-1."""
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    # Inefficient trial division without skipping even numbers
    for i in range(5, int(math.isqrt(n)) + 1, 2):
        if n % i == 0:
            return False
    return True


def cpu_workload_count_primes(limit: int) -> int:
    """Count primes up to limit."""
    count = 0
    for i in range(2, limit):
        if cpu_heavy_is_prime(i):
            count += 1
    return count


def memory_leaky_accumulation(iterations: int) -> int:
    """Memory Bottleneck: Creating millions of temporary string and list objects."""
    accumulated_data: List[str] = []
    total_len = 0
    for i in range(iterations):
        # Inefficient: Allocates a new string and list entry every iteration
        formatted = f"record_id_{i:06d}_payload_{i * 3}"
        accumulated_data.append(formatted)
        total_len += len(formatted)
    return total_len


def memory_efficient_accumulation(iterations: int) -> int:
    """Memory Optimized: Compute length and metrics without retaining temporary strings."""
    total_len = 0
    for i in range(iterations):
        # Format on the fly without retaining list of strings in heap
        s = f"record_id_{i:06d}_payload_{i * 3}"
        total_len += len(s)
    return total_len


def main() -> None:
    print("=== Python Managed Profiling: CPU & Memory Diagnostics ===\n")

    # 1. Parity Verification
    len_leaky = memory_leaky_accumulation(10_000)
    len_opt = memory_efficient_accumulation(10_000)
    assert len_leaky == len_opt, f"Parity mismatch: {len_leaky} != {len_opt}"
    print("[+] Parity Check PASSED: Memory accumulation algorithms produce identical results.\n")

    # 2. CPU Profiling with cProfile
    print("--- 1. CPU Profiling via cProfile ---")
    profiler = cProfile.Profile()
    profiler.enable()

    prime_count = cpu_workload_count_primes(50_000)

    profiler.disable()

    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats(SortKey.CUMULATIVE)
    ps.print_stats(10)
    print(s.getvalue())
    print(f"Total primes found: {prime_count}\n")

    # 3. Memory Profiling with tracemalloc
    print("--- 2. Memory Allocation Profiling via tracemalloc ---")
    tracemalloc.start(10)

    snap_before = tracemalloc.take_snapshot()
    _ = memory_leaky_accumulation(50_000)
    snap_after = tracemalloc.take_snapshot()

    top_stats = snap_after.compare_to(snap_before, 'lineno')
    print("Top Memory Allocations (Leaky Accumulator):")
    for stat in top_stats[:5]:
        print(f"  {stat}")

    current_kb, peak_kb = tracemalloc.get_traced_memory()
    print(f"\nPeak memory during leaky run: {peak_kb / 1024:.2f} KB")

    tracemalloc.reset_peak()
    snap_opt_before = tracemalloc.take_snapshot()
    _ = memory_efficient_accumulation(50_000)
    snap_opt_after = tracemalloc.take_snapshot()
    _, peak_opt_kb = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"Peak memory during optimized run: {peak_opt_kb / 1024:.2f} KB (Reduced by {peak_kb / max(peak_opt_kb, 1):.1f}x)\n")
    print("=== Profiling Complete ===")


if __name__ == "__main__":
    main()
