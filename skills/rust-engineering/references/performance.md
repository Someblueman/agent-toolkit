# Performance

Read this when the requested outcome is runtime or compile-time speed, latency, throughput, allocation reduction, binary size, or build-profile tuning. Performance work needs a reproducible claim, not a collection of “fast Rust” idioms.

## Define the claim

Before editing, identify:

- the workload and input distribution;
- the metric: latency percentile, throughput, CPU time, allocations, peak memory, binary size, or build time;
- the optimized build profile and target hardware;
- correctness and output equivalence constraints;
- the smallest effect that would matter.

If no benchmark or build-time measurement protocol exists, establish one before making a performance claim. Use a realistic end-to-end case when possible and a microbenchmark only to isolate a suspected mechanism.

## Default workflow

1. **Reproduce correctness.** Preserve outputs, ordering, error behavior, and relevant resource limits.
2. **Establish the relevant baseline.** Runtime claims normally need the optimized profile users run. Compile-time claims need the exact clean or incremental `check`, build, test, or link mode being improved.
3. **Measure variability.** Repeat enough to understand noise, warm-up, caching, and outliers. Record source revision, toolchain and tool versions, target, profile and flags, hardware, feature set, environment, exact command, sample count, estimator, spread or confidence interval, and outlier policy.
4. **Profile the representative workload.** Use a sampler for time, allocation tools for heap questions, and counters when the hypothesis requires them. Generated-code inspection can validate a mechanism; timing or counter evidence validates its effect.
5. **Change the largest justified cost.** Prefer doing less work or using a better algorithm before instruction-level tuning.
6. **Re-run correctness and the same measurement.** Report effect size and uncertainty, not just the better sample.
7. **Keep only demonstrated wins.** Revert neutral or regressing complexity unless it has another explicit benefit.

Do not modify release profiles, allocators, hashers, representations, or concurrency merely because they appear in this guide. Each is a hypothesis with workload-specific tradeoffs.

## Benchmarking

- Criterion and Divan are suitable Rust benchmark harnesses; Hyperfine is useful for whole CLI runs. Follow the repository's existing harness when present.
- Use `std::hint::black_box` around relevant inputs and outputs to discourage unwanted optimization. It is a best-effort benchmark barrier, not a correctness or code-generation guarantee.
- Separate construction/setup from steady-state operations when users can amortize setup. Measure both when both matter.
- Include realistic sizes and adversarial or boundary inputs where they affect algorithmic behavior. A one-size microbenchmark can select the wrong design.
- Control or record CPU frequency policy, contention, I/O cache state, thread count, allocator, environment, and input data when material.
- Wall-clock comparisons on shared CI runners can be noisy. Use dedicated runners, robust statistical thresholds, or lower-variance counters before making a blocking regression gate. Deterministic instruction counts still do not capture every cache, syscall, or real-time effect.

Any reported win should include the before and after values, units, revisions, command, workload, raw or replayable output, sample or confidence information, and whether correctness gates passed.

## Profiling tools

Choose the tool from the question:

| Question | Examples |
|---|---|
| Where is wall time spent? | `perf`, Instruments, Samply, `cargo flamegraph` |
| Which allocations dominate? | DHAT, heaptrack, allocator instrumentation |
| Did instructions or cache behavior change? | `perf stat`, Callgrind/Cachegrind, platform counters |
| Did inlining/vectorization/bounds elimination occur? | `cargo-show-asm`, compiler remarks, Godbolt for isolated code |
| What drives binary or generic-code size? | `cargo-bloat`, `cargo-llvm-lines` |

Profile an optimized build with enough debug information for symbols, commonly a dedicated profile:

```toml
[profile.profiling]
inherits = "release"
debug = "line-tables-only"
```

Build or run with that profile (for example, `cargo build --profile profiling`); declaring it alone does not change ordinary release commands.

Use a second tool when the first result is ambiguous, not as ritual. Sampling, allocation, and instruction tools answer different questions.

## Compile-time performance

Treat build time as its own workload. Do not compare a clean release build with an incremental check, or a default-feature package with an all-feature workspace, and call the difference an improvement.

- Define the edit/build loop being improved: clean or incremental, `check`, debug build, test build, release build, or linking. Record the package selection, targets, features, toolchain, linker, environment, and cache state.
- Use the relevant Cargo command with `--timings` (for example, `cargo build --timings`) or the repository's established tooling to inspect the critical path, parallelism, build scripts, procedural macros, code generation, and slow dependencies. A wall-clock total alone does not identify the cause.
- Compare dependency and feature graphs with commands such as `cargo tree -e features` when dependency compilation is implicated. A dependency removal can trade build time against duplicated local code or weaker maintenance; measure total cost rather than optimizing crate count.
- Distinguish front-end/type-checking, monomorphization/code generation, and linking hypotheses. Generic expansion, large generated files, proc macros, build scripts, LTO, and linker choice affect different phases.
- Measure clean builds in isolated target directories instead of deleting a broad shared cache. Measure incremental builds after a representative edit, not an unchanged no-op build.
- Keep runtime, binary-size, diagnostics, and incremental-rebuild behavior as correctness constraints. Faster compilation does not justify a slower artifact or a less usable public API unless that tradeoff is explicit.

Report before and after using the same build mode and include the timing artifact or replay command. Do not turn noisy shared-runner timings into a blocking CI threshold without a stable environment and a justified tolerance. See [Cargo build timings](https://doc.rust-lang.org/cargo/reference/timings.html).

## Build-profile hypotheses

Cargo documents the exact semantics and defaults in the [profiles reference](https://doc.rust-lang.org/cargo/reference/profiles.html). Benchmark profile changes independently because rustc, linkers, and workloads evolve.

| Option | Potential benefit | Important cost or constraint |
|---|---|---|
| `codegen-units = 1` | Less within-crate partitioning may improve optimization | Slower compilation; may not improve runtime |
| `lto = "thin"` | Cross-crate optimization with moderate link cost | Longer builds and larger cache work |
| `lto = "fat"` | May outperform Thin LTO for some final binaries | Highest link cost; can be neutral or worse |
| `panic = "abort"` | Smaller/simpler panic paths for suitable artifacts | Changes unwinding behavior; assess application, FFI, and test needs |
| target CPU/features | Enables instructions available on a controlled fleet | Artifact will require that CPU feature floor |
| alternate allocator | May help allocation-heavy contention patterns | Dependency/platform cost and possible regressions |
| PGO | Uses representative execution profiles to guide optimization | Complex, workload-sensitive build pipeline |

Tune the final application or controlled artifact. A library should generally not dictate the consumer's profile or global allocator. Keep a size-optimized profile separate from a speed-optimized profile because their goals conflict.

## Optimization levers

Apply these after measurement identifies the relevant cost.

### Do less work

- Improve algorithmic complexity or reduce calls to the hot operation.
- Reject impossible candidates cheaply before an expensive confirmation step.
- Cache only when locality, invalidation, and memory bounds are understood.
- Fuse passes when it removes repeated traversal without making correctness opaque.

### Allocation and ownership

- Pre-size collections when a reliable size estimate exists; reuse buffers with `clear`; use entry APIs where they avoid duplicate lookups or permit in-place initialization.
- Avoid allocating formatted strings in a hot path when writing into a reusable buffer is equivalent.
- `BufRead::lines` creates owned strings. Reuse a `String` with `read_line` when allocation profiles show line parsing is hot.
- `Cow`, inline-capacity collections, arenas, interning, boxed variants, and structure-of-arrays each trade allocation, indirection, locality, or complexity differently. Use the ownership and layout guide, then re-measure.

### Iteration and generated code

- Do not materialize an iterator merely to traverse it once. Do materialize when sorting, repeated traversal, ownership, locality, parallel partitioning, or an error boundary benefits.
- Prefer ordinary iterators and slices before unchecked indexing. If bounds checks are suspected, verify emitted code; compiler optimization is context-dependent.
- `#[inline]` is a hint and can increase compile time and code size. Apply it to an observed cross-crate or call-boundary problem, then inspect and benchmark. Use `#[cold]` for genuinely rare paths only when profiles support the split.
- Micro-level iterator rewrites are compiler- and context-sensitive. Keep the clearest version unless measurement distinguishes them.

### Hashing

- The standard `HashMap` currently uses a randomly keyed, HashDoS-resistant hasher, but its exact algorithm is not a stable contract.
- Change a hasher only when hashing is measured hot and the key threat model is known. Review the specific algorithm: “non-cryptographic” does not by itself describe HashDoS behavior, and keyed does not mean cryptographically secure. Do not weaken adversarial-input protection accidentally.
- Integer-keyed or compiler-style workloads may benefit from specialized hashers, but choose with the actual key distribution and collision behavior.

### I/O and output

- Buffering helps repeated small reads or writes. It can add no value around already-buffered sources or large direct operations. Explicitly `flush` a `BufWriter` when errors must be observed; errors during drop cannot be reported to the caller.
- Lock stdout or stderr once for a hot output loop, or buffer per worker and serialize larger chunks. Preserve output ordering requirements.
- Byte-oriented reads avoid UTF-8 validation only when the data contract permits bytes.
- Memory mapping depends on OS, filesystem, file sizes, access pattern, and page-fault behavior. Benchmark it against buffered I/O on the deployment workload.

## Transferable patterns, not prescriptions

Projects such as ripgrep and regex demonstrate useful patterns: cheap literal prefilters before expensive matching, bulk scanning with lazy line accounting, construction-time selection of specialized engines, reusable scratch space, and per-worker output buffers. Apply a pattern only when the target workload has the same shape and profiling justifies its added complexity.

Document performance as an API contract only when the implementation and tests actually support that guarantee. State complexity, conditions, hardware or input assumptions, and the tradeoff accepted; do not generalize numbers from another project.
