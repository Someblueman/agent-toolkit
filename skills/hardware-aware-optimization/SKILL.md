---
name: hardware-aware-optimization
description: Optimize a measured CPU, memory, allocation or concurrency bottleneck using target-appropriate layout, SIMD, compiler or runtime techniques. Use when performance work needs hardware-specific decisions and correctness checks; do not apply every technique as a checklist.
---

# Hardware-aware optimization

Start with a measured bottleneck and a behavior contract. Choose one technique that addresses the evidence; the references are alternatives, not sequential requirements. Keep a change only when the measured benefit justifies its complexity on the supported hardware and workload.

- Locality: [data layout](references/data-oriented-design.md). Confirm actual cache geometry and access patterns before changing alignment or AoS/SoA layout.
- Arithmetic throughput: [SIMD](references/simd-vectorization-intrinsics.md). Check target features, tails, alignment, overflow and floating-point semantics; try compiler vectorization first.
- Unpredictable branches: [branchless operations](references/branchless-and-bit-manipulation.md). Benchmark; branchless code can do more work.
- Allocation pressure: [allocators and views](references/zero-copy-and-custom-allocators.md). Prefer established allocators; establish lifetime, alignment and overflow contracts.
- Contention: [concurrency](references/lock-free-concurrency.md). Reduce sharing first. Lock-free code requires memory-order and reclamation proof plus relevant concurrency checks.
- Compiler opportunities: [PGO/LTO](references/compiler-tuning-pgo-lto.md). Use representative training data and deployable target flags.
- Haskell: [strictness and unboxing](references/haskell-optimization.md). Preserve demanded evaluation and termination behavior.

## Verification helpers

Resolve `SKILL_DIR` to this loaded skill's absolute directory.

```bash
python3 "$SKILL_DIR/scripts/differential_test_runner.py" --baseline './baseline' --optimized './candidate' --iterations 30
python3 "$SKILL_DIR/scripts/benchmark_comparator.py" --baseline './baseline' --optimized './candidate' --runs 15
```

The differential runner supplies numeric vectors on stdin; use it only for that input protocol. Other domains need their own representative corpus. Commands use shell-style argument quoting without shell evaluation, have a 10-second execution timeout, and must exit successfully. Stdout is exact by default and stderr exact always. Explicit positive `--tolerance` allows finite floating-point token approximation while integer tokens remain exact. A passing run applies only to completed vectors, not all behavior.

The comparator alternates execution order, retains raw samples, and uses the same median estimator for the ratio and approximate bootstrap interval. Runs time fresh processes including startup, with a 60-second command timeout. Warmups do not establish persistent runtime/JIT steady state. Small samples or correlated observations can understate uncertainty; use an in-process benchmark when that is the actual performance target.

Runnable examples under `examples/` illustrate techniques; qualify them on the actual target before adopting them.
