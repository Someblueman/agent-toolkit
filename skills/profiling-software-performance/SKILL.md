---
name: profiling-software-performance
description: >-
  Comprehensive performance profiling and measurement playbook for identifying CPU, memory, cache, concurrency, and I/O bottlenecks before optimization. Use when benchmarking code, establishing noise-controlled baselines, analyzing hardware PMU counters (IPC, cache/branch misses) on Linux/macOS, profiling managed runtimes (Python, Go, Node.js), diagnosing GHC Haskell space leaks and cost centres, or generating flamegraphs.
---

# Performance Profiling & Measurement Playbook

Never optimize code without baseline profiling data. Premature or intuition-guided optimization wastes effort on non-critical code paths and frequently degrades maintainability.

Follow this 5-stage workflow to isolate environmental noise, measure performance metrics, pinpoint the exact hardware or runtime bottleneck, and formulate an optimization plan.

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. Establish Noise-Controlled Baseline                      │
│    Lock CPU frequency, warmup caches, sample N >= 30,       │
│    verify CV <= 5%, compute median and 95% CI.              │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Execute Domain-Specific Profiling                        │
│    ├─ Systems (C/C++/Rust): Linux perf / macOS xctrace      │
│    ├─ Managed (Python/Go/Node): pprof / cProfile / V8 ticks │
│    └─ Functional (Haskell GHC): +RTS -p / -hc / Eventlog    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Analyze Hardware PMU & Instruction Counters              │
│    Calculate IPC, L1/LLC cache miss rates, branch misses.   │
│    Diagnose Memory-bound vs Compute-bound vs Stalls.        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Evaluate Runtime Overheads & Heap Dynamics               │
│    Measure GC pause latency, heap allocation churn rate,    │
│    compiler escape analysis, and lazy thunk space leaks.    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Calculate Amdahl's Law Speedup & Optimization Handoff    │
│    Verify bottleneck fraction p >= 30%, establish parity    │
│    assertions, and hand off to hardware-aware-optimization │
└─────────────────────────────────────────────────────────────┘
```

---

## Stage 1: Noise-Controlled Baseline Setup

Environmental variance (frequency scaling, thread migration, cold caches) can introduce up to $\pm 35\%$ measurement error.

1. **Eliminate Dynamic Clock Variance**:
   - **Linux**: Lock CPU governor to `performance` and disable Turbo Boost via sysfs.
   - **macOS**: Ensure AC power, disable Spotlight indexing (`mdutil -a -i off`), and set QoS (`taskpolicy -c throughput`).
   - *Deep Dive*: [references/noise-reduction-and-benchmarking.md](references/noise-reduction-and-benchmarking.md)
2. **Pin CPU Affinity**: Pin worker threads to dedicated physical cores using `taskset -c <core>` or `pthread_setaffinity_np`.
3. **Execute Warmup Iterations**: Always execute untimed warmup iterations ($W \ge 3$) to populate L1/L2 caches and page tables.
4. **Collect Statistically Rigorous Samples ($N \ge 30$)**:
   - Collect at least 30 timing samples.
   - Compute Median ($p50$), Mean ($\mu$), Standard Deviation ($\sigma$), Interquartile Range (IQR), and 95% Confidence Interval.
   - **Variance Gate**: Assert Coefficient of Variation $\text{CV}\% = (\sigma / \mu) \times 100\% \le 5.0\%$. If $\text{CV} > 5\%$, do not proceed until system load is stabilized.

*Automated Utility*: Run [scripts/run_benchmark_with_stats.py](scripts/run_benchmark_with_stats.py) to execute commands with automatic warmup, sample collection, and statistical reporting:
```bash
python3 skills/profiling-software-performance/scripts/run_benchmark_with_stats.py \
  --warmup 5 --iterations 30 --json-out baseline.json -- ./my_target_app
```

---

## Stage 2: Domain-Specific Profiling & Bottleneck Identification

Select the profiler matching the execution runtime:

### 2.1 Systems Languages (C, C++, Rust)
- **Linux `perf`**:
  ```bash
  # Sample call stacks at 997 Hz with frame pointers
  perf record -F 997 -g -- ./my_app
  perf report -i perf.data --stdio
  ```
- **macOS `xctrace` / Instruments**:
  ```bash
  xcrun xctrace record --template 'Time Profiler' --time-limit 5s --launch -- ./my_app
  ```
- **Interactive Flamegraphs**: Generate hierarchical SVG flamegraphs using [scripts/generate_flamegraph.sh](scripts/generate_flamegraph.sh):
  ```bash
  perf script | skills/profiling-software-performance/scripts/generate_flamegraph.sh - flame.svg
  ```
- *Full Reference*: [references/systems-profiling-perf-instruments.md](references/systems-profiling-perf-instruments.md)
- *Runnable Example*: [examples/c_systems_profiling/](examples/c_systems_profiling/) (demonstrating cache line locality vs stride misses).

### 2.2 Managed Runtimes (Python, Go, Node.js)
- **Python**: Use `cProfile` for deterministic call trees, `tracemalloc` for line-by-line memory tracking, or `py-spy` for zero-overhead sampling.
- **Go**: Integrate `pprof` CPU and heap profiling into benchmarks (`go test -bench=. -cpuprofile=cpu.pprof -memprofile=mem.pprof -benchmem`), and run escape analysis (`go build -gcflags="-m -m"`).
- **Node.js / V8**: Use `node --prof` tick logs with `node --prof-process`, or capture `.cpuprofile` / `.heapprofile` via `node --cpu-prof`.
- *Full Reference*: [references/managed-runtime-profiling.md](references/managed-runtime-profiling.md)
- *Runnable Example*: [examples/python_go_node_profiling/](examples/python_go_node_profiling/) (demonstrating CPU vs heap allocation bottlenecks).

### 2.3 Functional & Lazy Paradigms (Haskell / GHC)
- **Time Profiling**: Compile with `-prof -fprof-auto -rtsopts` and run with `+RTS -p` to generate `<prog>.prof`.
- **Heap Profiling**: Run with `+RTS -hc` (cost-centre) or `+RTS -hy` (type) and convert `.hp` to PostScript via `hp2ps -c <prog>.hp`.
- **GC Health Check**: Run any `-rtsopts` binary with `+RTS -s` to inspect GC productivity.
- *Full Reference*: [references/haskell-ghc-profiling.md](references/haskell-ghc-profiling.md)
- *Automated Parser*: [scripts/analyze_ghc_prof.py](scripts/analyze_ghc_prof.py)
- *Runnable Example*: [examples/haskell_space_leak_profiling/](examples/haskell_space_leak_profiling/) (lazy fold space leak vs strict accumulator).

---

## Stage 3: PMU Counter & Hardware Analysis

When profiling systems code, query the CPU Performance Monitoring Unit (PMU) to classify the low-level microarchitectural bottleneck:

$$\text{IPC} = \frac{\text{instructions}}{\text{cycles}}$$

| Metric | Target Value | Symptom if Violated | Root Cause & Remediation |
| :--- | :--- | :--- | :--- |
| **Instructions Per Cycle (IPC)** | $\ge 2.0$ | $\text{IPC} < 0.8$ | Memory latency stall, pipeline flush, or execution port contention. |
| **L1 D-Cache Miss Rate** | $< 3.0\%$ | Miss rate $> 5.0\%$ | Non-contiguous memory strides or pointer-chasing. Reorganize data into Structure-of-Arrays (SoA). |
| **LLC (L3) Miss Rate** | $< 1.0\%$ | Miss rate $> 5.0\%$ | Working set exceeds CPU cache capacity; DRAM bandwidth saturation. Apply cache blocking / tiling. |
| **Branch Misprediction Rate** | $< 2.0\%$ | Miss rate $> 3.0\%$ | Data-dependent branching. Replace branchy conditionals with branchless arithmetic / lookup tables. |

---

## Stage 4: Runtime Overhead & GC Analysis

In managed and lazy runtimes, high CPU utilization often masks runtime garbage collection and memory allocation overhead:

1. **Evaluate GC Productivity (Haskell / Go / Node.js)**:
   $$\text{Productivity} = \frac{\text{MUT Time}}{\text{TOTAL Time}} \times 100\%$$
   - If Productivity $< 80\%$, the application is spending $> 20\%$ of time in garbage collection. Target allocation reduction rather than algorithm compute tuning.
2. **Inspect Escape Analysis Diagnostics (Go)**:
   - Check if variables escape to the heap due to interface conversion, closure capture, or dynamic slicing (`go build -gcflags="-m"`).
3. **Diagnose Space Leaks (Haskell)**:
   - Check for linear heap growth in GHC heap profiles (`+RTS -hc`), indicating unforced thunk build-up in lazy accumulator chains. Enforce WHNF evaluation with `foldl'` or bang patterns (`!acc`).

---

## Stage 5: Actionable Optimization Handoff

Before initiating code changes, compute the theoretical upper bound of your proposed optimization using **Amdahl's Law**:

$$S_{\text{latency}} = \frac{1}{(1 - p) + \frac{p}{s}}$$

- **Rule**: Only prioritize optimization on functions where execution fraction $p \ge 30\%$.
- **Verification Requirement**: Establish automated parity assertions ($\text{assert } f_{\text{baseline}}(x) \equiv f_{\text{opt}}(x)$) across randomized test vectors to guarantee zero behavioral regressions before proceeding to optimization.

---

## Reference & Asset Index

### Deep-Dive References
- [references/noise-reduction-and-benchmarking.md](references/noise-reduction-and-benchmarking.md) — CPU pinning, turbo boost control, warmup protocols, statistical distributions ($p50$, IQR, CI95%), and Amdahl's Law.
- [references/systems-profiling-perf-instruments.md](references/systems-profiling-perf-instruments.md) — Linux `perf stat`/`record`, hardware PMU counter metrics, macOS `xctrace`/Instruments, and flamegraphs.
- [references/managed-runtime-profiling.md](references/managed-runtime-profiling.md) — Python (`cProfile`, `tracemalloc`, `py-spy`), Go (`pprof`, `go tool trace`, escape analysis), and Node.js (`node --prof`, V8 tick logs).
- [references/haskell-ghc-profiling.md](references/haskell-ghc-profiling.md) — GHC cost centres (`+RTS -p`), heap profiling (`-hc`/`-hy`, `hp2ps`), Eventlog / ThreadScope, GC statistics (`+RTS -s`), and GHC Core optimization inspection (`-ddump-simpl`).

### Utility Scripts
- [scripts/run_benchmark_with_stats.py](scripts/run_benchmark_with_stats.py) — CLI utility executing benchmarks with warmup, statistical aggregation, and noise status.
- [scripts/generate_flamegraph.sh](scripts/generate_flamegraph.sh) — Shell script generating interactive SVG flamegraphs from perf, sample, or folded stack files.
- [scripts/analyze_ghc_prof.py](scripts/analyze_ghc_prof.py) — CLI parser extracting metadata, top cost centres, and space leaks from GHC `.prof` files.

### Runnable Examples
- [examples/c_systems_profiling/](examples/c_systems_profiling/) — C cache-friendly vs stride-miss matrix traversal benchmark with parity checks and automated runner.
- [examples/python_go_node_profiling/](examples/python_go_node_profiling/) — Runnable Python, Go, and Node.js profiling benchmarks identifying CPU vs heap allocation bottlenecks.
- [examples/haskell_space_leak_profiling/](examples/haskell_space_leak_profiling/) — Runnable Haskell GHC space leak demonstration with cost-centre profiling and GC statistics.
