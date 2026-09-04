---
name: profiling-software-performance
description: >-
  Comprehensive performance profiling and measurement playbook for identifying CPU, memory, cache, concurrency, and I/O bottlenecks before optimization. Use when benchmarking code, establishing noise-controlled baselines, analyzing hardware PMU counters (IPC, cache/branch misses) on Linux/macOS, profiling managed runtimes (Python, Go, Node.js), diagnosing GHC Haskell space leaks and cost centres, or generating flamegraphs.
---

# Performance profiling

Define the workload, performance target and measurement boundary first: startup, steady-state throughput, latency distribution, allocation or I/O. Record toolchain, build, machine and input so comparisons can be repeated.

Default to observation and process-local profiling. Host-wide frequency, indexing, scheduler and security changes are separate operations requiring explicit authorization, captured prior state and restoration. They are not profiling prerequisites.

Choose the profiler for the suspected cost:

- [Systems: perf and Instruments](references/systems-profiling-perf-instruments.md)
- [Python, Go and Node](references/managed-runtime-profiling.md)
- [Haskell time, heap and eventlog](references/haskell-ghc-profiling.md)
- [Measurement design and noise](references/noise-reduction-and-benchmarking.md)

Use PMU events supported by the actual CPU and interpret counters together with workload evidence. IPC, cache misses, GC productivity and hotspot percentage have no universal pass/fail thresholds. Allocation alone does not establish a space leak. Estimate the possible end-to-end benefit before selecting an optimization; small hotspots can still matter to a relevant latency or resource target.

## Helpers

Resolve `SKILL_DIR` to the absolute directory of this loaded skill.

```bash
python3 "$SKILL_DIR/scripts/run_benchmark_with_stats.py" --warmup 3 --iterations 30 --json-out baseline.json -- ./my_app
perf script | "$SKILL_DIR/scripts/generate_flamegraph.sh" - flame.svg
python3 "$SKILL_DIR/scripts/analyze_ghc_prof.py" program.prof
```

The benchmark helper measures fresh-process elapsed time including startup. Warmups can affect OS caches but do not warm later processes' JIT/runtime state. Choose sample counts from the uncertainty and effect being tested; the example count is not a quota. The mean interval is an approximate percentile bootstrap assuming independent observations; raw samples are retained. At least two samples are needed, but two do not establish reliable tail or confidence estimates. CV is descriptive, not a stability verdict.

The flamegraph helper accepts folded stacks, supported perf/sample text or stdin. Inspect generated content against the original profile. The GHC parser rejects unsupported/incomplete input; its alerts are hypotheses, not proof of leaks or balanced resource use.

Report observations, uncertainty and one evidence-supported next action. No profiler is zero overhead, and passing correctness tests does not establish speedup.
