---
name: hardware-aware-optimization
description: >-
  Provides systematic, hardware-aware optimization playbooks, decision rubrics,
  and reproducible workflows for extracting maximum throughput and minimum latency
  across systems languages (C, C++, Rust), managed runtimes (Go, Python), and
  functional paradigms (Haskell). Applies Data-Oriented Design (AoS vs SoA),
  SIMD vectorization (ARM NEON, x86_64 AVX2/AVX-512), branchless programming and
  hardware bit manipulation, zero-copy custom allocators (monotonic arena, slab pools),
  lock-free atomic concurrency (SPSC ring buffers, Treiber stacks), Profile-Guided
  Optimization (PGO), Link-Time Optimization (ThinLTO), and Haskell unboxed primitives
  (MagicHash, stream fusion, rewrite rules). Use when an identified performance bottleneck
  requires orders-of-magnitude speedup, high cache line efficiency, zero-allocation loops,
  or lock-free scaling with strict differential parity verification.
---

# Hardware-Aware Optimization Playbook

This skill provides production-grade, hardware-aware optimization methodologies designed to extract maximum performance from modern multi-core processors. It operates under a strict **Verification-First Protocol**: every optimization must preserve 100% behavioral equivalence against baseline implementations before speedup is accepted.

---

## 1. Hardware-Aware Optimization Decision Matrix

Use this flowchart to select the appropriate optimization strategy based on the identified bottleneck:

```
                  ┌──────────────────────────────────────────────┐
                  │ Bottleneck Classification (from Profiling)   │
                  └──────────────────────┬───────────────────────┘
                                         │
     ┌───────────────────┬───────────────┴───────────────┬───────────────────┐
     ▼                   ▼                               ▼                   ▼
┌──────────────┐ ┌──────────────┐                 ┌──────────────┐    ┌──────────────┐
│ Memory Bound │ │ Compute/SIMD │                 │ Branch / CPU │    │ Concurrency  │
│ Cache Misses │ │ Vector Loops │                 │ Mispredicts  │    │ Contention   │
└──────┬───────┘ └──────┬───────┘                 └──────┬───────┘    └──────┬───────┘
       │                │                                │                   │
       ▼                ▼                                ▼                   ▼
┌──────────────┐ ┌──────────────┐                 ┌──────────────┐    ┌──────────────┐
│ Transform to │ │ Apply SIMD   │                 │ Branchless   │    │ Lock-Free    │
│ SoA/AoSoA    │ │ NEON / AVX2  │                 │ CMOV / Masks │    │ SPSC Queue / │
│ 64B Align    │ │ Intrinsics   │                 │ Bit Twiddling│    │ Acquire-Rel  │
└──────────────┘ └──────────────┘                 └──────────────┘    └──────────────┘
```

| Primary Bottleneck | Architectural Diagnosis | Recommended Transformation | Reference Deep Dive |
|---|---|---|---|
| **High L1/L2/L3 Cache Misses** | Poor spatial locality; AoS pulling cold fields into cache lines. | Transform to **SoA / AoSoA** layout; pack structs; align to 64 bytes. | [references/data-oriented-design.md](references/data-oriented-design.md) |
| **Compute-Bound Loops** | Scalar arithmetic processing 1 element per instruction. | Vectorize with **ARM NEON** or **x86 AVX2/AVX-512** intrinsics / `#pragma clang loop vectorize`. | [references/simd-vectorization-intrinsics.md](references/simd-vectorization-intrinsics.md) |
| **High Branch Mispredict Rate** | Unpredictable `if/else` flushing 15–20 cycle CPU pipelines. | Replace with **arithmetic bitmasks**, conditional moves (`CMOV`), and **bit manipulation**. | [references/branchless-and-bit-manipulation.md](references/branchless-and-bit-manipulation.md) |
| **Memory Allocator Lock Contention** | Repeated `malloc`/`free` or garbage collector pauses in hot paths. | Deploy **Monotonic Bump Arena** or **Fixed-Size Slab Pools**; use **zero-copy views**. | [references/zero-copy-and-custom-allocators.md](references/zero-copy-and-custom-allocators.md) |
| **Thread Lock / Mutex Stalls** | OS context switches and kernel transitions under contention. | Implement **Lock-Free SPSC Ring Buffers** and atomic **Acquire/Release** fences. | [references/lock-free-concurrency.md](references/lock-free-concurrency.md) |
| **Whole-Program Inlining & Layout** | Suboptimal function boundaries and cold branch layouts. | Apply **Profile-Guided Optimization (PGO)** and **Link-Time Optimization (ThinLTO)**. | [references/compiler-tuning-pgo-lto.md](references/compiler-tuning-pgo-lto.md) |
| **Haskell Thunks & Space Leaks** | Lazy evaluation accumulating boxed closures on the heap. | Utilize unboxed primitives (`Int#`, `MagicHash`), `{-# UNPACK #-}`, and **stream fusion**. | [references/haskell-optimization.md](references/haskell-optimization.md) |

---

## 2. Progressive Optimization Workflow

When applying these optimizations to a critical computational kernel:

### Step 1: Establish Baseline & Differential Correctness Harness
Before modifying production code, build a differential test harness that runs randomized and boundary input vectors against both baseline and proposed implementations.
- Reference runner: [scripts/differential_test_runner.py](scripts/differential_test_runner.py)
- Benchmark analyzer: [scripts/benchmark_comparator.py](scripts/benchmark_comparator.py)

### Step 2: Apply Memory & Data Layout Optimization
Transform data representations from object-oriented arrays of structures (AoS) to cache-friendly structures of arrays (SoA). Align concurrent counters to 64-byte boundaries with `alignas(64)` / `#[repr(align(64))]` to eliminate false sharing.
- Details: [references/data-oriented-design.md](references/data-oriented-design.md)

### Step 3: Vectorize with SIMD Intrinsics
Replace scalar iterations with 128-bit (ARM NEON) or 256-bit (AVX2) vector registers. Use fused multiply-add (`vfmaq_f32` / `_mm256_fmadd_ps`) to double arithmetic throughput per cycle.
- Details: [references/simd-vectorization-intrinsics.md](references/simd-vectorization-intrinsics.md)
- Runnable example: [examples/simd_neon_avx2_benchmark/](examples/simd_neon_avx2_benchmark/)

### Step 4: Eliminate Branch Mispredictions
Convert data-dependent branches into branchless arithmetic masks or hardware bit manipulation instructions (`__builtin_popcount`, `__builtin_clz`, `__builtin_ctz`).
- Details: [references/branchless-and-bit-manipulation.md](references/branchless-and-bit-manipulation.md)
- Runnable example: [examples/branchless_parser/](examples/branchless_parser/)

### Step 5: Eliminate Heap Allocations
Replace general-purpose heap allocations in hot loops with monotonic bump arenas or fixed-size intrusive object pools. Pass non-owning slices (`std::string_view`, `&[T]`, `memoryview`).
- Details: [references/zero-copy-and-custom-allocators.md](references/zero-copy-and-custom-allocators.md)
- Runnable example: [examples/custom_arena_allocator/](examples/custom_arena_allocator/)

### Step 6: Scale Multi-Threading via Lock-Free Primitives
Replace mutex-locked queues with Single-Producer Single-Consumer (SPSC) lock-free ring buffers using cache-line separated head/tail indices and `std::memory_order_acquire`/`release`.
- Details: [references/lock-free-concurrency.md](references/lock-free-concurrency.md)
- Runnable example: [examples/lockfree_spsc_queue/](examples/lockfree_spsc_queue/)

### Step 7: Apply Compiler Tuning (PGO / LTO)
Compile with `-O3`, `-march=native`, `-flto=thin`, and run 2-stage Profile-Guided Optimization to optimize instruction cache locality and devirtualize calls.
- Details: [references/compiler-tuning-pgo-lto.md](references/compiler-tuning-pgo-lto.md)

### Step 8: Haskell Domain Optimization
In Haskell codebases, eliminate boxed heap closures by rewriting critical loops with unboxed primitives (`Int#` via `MagicHash`), strictness pragmas (`BangPatterns`), `{-# UNPACK #-}`, and vector stream fusion (`Data.Vector.Unboxed`).
- Details: [references/haskell-optimization.md](references/haskell-optimization.md)
- Runnable example: [examples/haskell_unboxed_fusion/](examples/haskell_unboxed_fusion/)

---

## 3. Skill Resources Index

### Technical Reference Manuals (`references/`)
- [Data-Oriented Design & Cache Layout](references/data-oriented-design.md): AoS vs SoA, 64-byte cache line alignment, false sharing elimination, struct packing.
- [SIMD Vectorization & Intrinsics](references/simd-vectorization-intrinsics.md): ARM NEON, x86 AVX2/AVX-512, auto-vectorization directives, portable SIMD.
- [Branchless Programming & Bit Manipulation](references/branchless-and-bit-manipulation.md): Eliminating branch mispredictions, arithmetic masking, hardware bit intrinsics (`POPCNT`, `LZCNT`, `TZCNT`).
- [Zero-Copy & Custom Allocators](references/zero-copy-and-custom-allocators.md): Monotonic bump arenas, fixed-size slab pools, `mmap` sequential paging.
- [Lock-Free Concurrency & Atomics](references/lock-free-concurrency.md): Lock-free SPSC queues, atomic memory models (`acquire`/`release`), ABA prevention with tagged pointers/epochs.
- [Compiler Tuning, PGO & LTO](references/compiler-tuning-pgo-lto.md): 2-stage PGO pipelines, ThinLTO, architecture flags (`-march=native`), fast-math tradeoffs.
- [Haskell Optimization](references/haskell-optimization.md): Unboxed types (`Int#`, `ByteArray#`), strictness, record unpacking, stream fusion, GHC rewrite rules.

### Automation Scripts (`scripts/`)
- [scripts/differential_test_runner.py](scripts/differential_test_runner.py): Automated test runner executing baseline vs optimized binaries across randomized vectors to verify 100% parity.
- [scripts/benchmark_comparator.py](scripts/benchmark_comparator.py): Statistical benchmark comparator calculating speedup ratios, confidence intervals, and summary markdown tables.

### Runnable Multi-Language Examples (`examples/`)
- [examples/simd_neon_avx2_benchmark/](examples/simd_neon_avx2_benchmark/): C/C++ benchmark comparing scalar vs ARM NEON/AVX2 vector math with automated parity verification.
- [examples/custom_arena_allocator/](examples/custom_arena_allocator/): C++ / Rust benchmark comparing monotonic arena allocation against system `malloc`/`free`.
- [examples/branchless_parser/](examples/branchless_parser/): Branchless parsing and filtering benchmark comparing branching vs branchless bitmask logic.
- [examples/lockfree_spsc_queue/](examples/lockfree_spsc_queue/): High-throughput C++ lock-free SPSC queue benchmark vs mutex-guarded queue.
- [examples/haskell_unboxed_fusion/](examples/haskell_unboxed_fusion/): Haskell benchmark comparing boxed list processing vs unboxed primitive worker-wrapper + vector stream fusion.
