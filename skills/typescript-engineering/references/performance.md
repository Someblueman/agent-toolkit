# TypeScript and JavaScript Performance

Use this reference only when performance is part of the task or evidence identifies a bottleneck. Runtime speed, memory, compiler latency, editor responsiveness, startup, and bundle size are different objectives; optimize and report them separately.

## 1. Define a falsifiable target

Record:

- deployed Node/browser/runtime and TypeScript versions;
- hardware/OS when relevant;
- production-shaped input sizes and data distribution;
- cold versus warmed execution;
- metric: startup, operations/second, p50/p95/p99 latency, CPU time, event-loop utilization, RSS/heap, output size, `tsc` time, or editor delay;
- sample count, variance, and acceptance threshold;
- correctness and resource constraints that must remain unchanged.

Short-lived CLIs may be dominated by parse/compile/startup. Services may care about sustained throughput, tail latency, and memory. A tight-loop microbenchmark is not evidence for either unless profiling proves that loop dominates the real workload.

Sources: [V8 real-world performance](https://v8.dev/blog/real-world-performance), [V8 Sparkplug/startup tradeoffs](https://v8.dev/blog/sparkplug), [Node performance hooks](https://nodejs.org/api/perf_hooks.html).

## 2. Measure the correct layer

### Runtime

- CPU: run the real entry point with `node --cpu-prof ...` and inspect the `.cpuprofile`.
- Heap/allocation: use `node --heap-prof ...`, heap snapshots, and `node:v8` statistics where appropriate.
- Application spans and event loop: `performance.mark`, `performance.measure`, `PerformanceObserver`, and `performance.eventLoopUtilization()`.
- Database/network/filesystem: measure their latency and bytes separately before blaming JavaScript.

Warm up JIT-compiled workloads deliberately, but also retain a cold measurement if users experience startup. Isolate network and filesystem variability when measuring CPU changes. Never report one wall-clock sample as a result.

### Compiler and editor

First run the repository's `tsc` directly so bundler/plugins are not conflated with compiler time:

```text
tsc --extendedDiagnostics
tsc --explainFiles
tsc --traceResolution
tsc --generateTrace <directory>
tsc --generateCpuProfile <file>
```

Use only the commands supported by the pinned compiler. Trace schemas and diagnostics are version-sensitive; record the exact version and do not build durable tooling against undocumented trace structure.

Sources: [Node CLI profiling](https://nodejs.org/api/cli.html), [Node V8 diagnostics](https://nodejs.org/api/v8.html), [TypeScript performance](https://github.com/microsoft/TypeScript/wiki/Performance), [TypeScript tracing](https://github.com/microsoft/TypeScript/wiki/Performance-Tracing).

## 3. Runtime optimization order

1. Remove work: cache only stable expensive results, reject early, avoid repeated parsing/scanning/serialization, and skip data not needed for the result.
2. Fix algorithms and queries. Bound algorithmic complexity as input grows, especially for untrusted input.
3. Fix I/O shape: batch operations, eliminate sequential round trips, stream large data, and respect backpressure.
4. Fix concurrency: parallelize independent I/O only, cap it at the constrained resource, and move substantial CPU work to a bounded worker pool.
5. Fix retention and allocation identified by heap evidence: unbounded maps/caches/queues, listener leaks, closures retaining request graphs, pending promises, and avoidable whole-buffer copies.
6. Only then investigate hot representation, call shape, or V8 specialization. Keep data representation stable when natural, but do not cargo-cult hidden-class or inlining folklore across V8 versions.

Re-measure after each change. A faster mean with worse p99 or materially higher RSS may be a regression for the actual goal.

Sources: [Node event-loop guidance](https://nodejs.org/en/learn/asynchronous-work/dont-block-the-event-loop), [Node streams](https://nodejs.org/api/stream.html), [Node workers](https://nodejs.org/api/worker_threads.html), [V8 tiered execution](https://v8.dev/blog/launching-ignition-and-turbofan).

## 4. Memory and allocation

- Measure RSS and heap; successful garbage collection does not guarantee RSS immediately returns to the OS.
- Find retention roots before rewriting code to reuse objects. Manual pooling can increase lifetime and memory.
- Bound caches by entries/bytes and define eviction plus invalidation. A cache without an ownership and invalidation story is a leak with a lookup API.
- Stream or chunk large inputs. Avoid parsing/stringifying huge payloads on the event loop when input size is not tightly bounded.
- Avoid per-item worker/process creation and repeated cloning of large messages. Transfer buffers when supported and ownership can move safely.
- Remove event listeners, timers, and subscriptions when their owner completes.

Heap snapshot and V8 statistics formats can change; use public APIs and the deployed runtime version.

Source: [Node V8 heap APIs](https://nodejs.org/api/v8.html).

## 5. Type-check and build performance

Only tune after diagnostics identify compiler cost.

- Keep `include`/`files` scoped to real inputs; inspect `--explainFiles` for generated output, fixtures, dependency trees, or duplicate source inclusion.
- Control automatic global `@types` inclusion with `types` only when unwanted packages are actually entering the program.
- Use `incremental` for repeated builds when its state file fits the workflow.
- Use project references for genuinely large/coherent packages with real dependency boundaries. Avoid one huge project and dozens of tiny satellites; references add declaration/build coordination cost.
- Prefer interfaces over large intersections for composed object shapes; name recurring complex types so relationships can be cached.
- Add annotations, especially exported return types, where diagnostics show repeated expensive inference or enormous declaration output. Do not annotate every local merely for performance folklore.
- Simplify very large unions and distributive conditional/mapped types when traces identify them.
- `skipLibCheck` trades declaration-file checking for speed. It can hide duplicate/incompatible declaration problems; treat it as a deliberate boundary, not a fix.
- Fast/loose watch options may omit transitive checks. Pair them with periodic full builds and label the tradeoff.

Sources: [TypeScript performance guidance](https://github.com/microsoft/TypeScript/wiki/Performance), [project references](https://www.typescriptlang.org/docs/handbook/project-references.html), [`skipLibCheck`](https://www.typescriptlang.org/tsconfig/skipLibCheck.html).

## 6. Benchmark acceptance

A performance handoff includes:

```text
objective and threshold
runtime/compiler + platform
workload and input sizes
exact command
warm-up and samples
before distribution
after distribution
correctness gates
memory/latency tradeoffs
profile-based explanation
```

Keep a regression benchmark when the win is meaningful and the benchmark is stable enough to fail usefully. Shared CI hosts can be noisy; prefer generous statistical budgets or deterministic work counters over brittle tiny wall-time thresholds.
