# SIMD Vectorization Benchmark (ARM NEON & AVX2)

This example demonstrates how hardware SIMD intrinsics (ARM NEON and x86_64 AVX2) accelerate floating-point polynomial transformations (`out[i] = a[i]*x^2 + b[i]*x + c[i]`) across 4 million elements with fused multiply-add (`vfmaq_f32` / `_mm256_fmadd_ps`).

## Key Techniques
1. **128-bit ARM NEON vectorization** (`<arm_neon.h>`) using 2-way unrolled vector streams.
2. **256-bit x86_64 AVX2 vectorization** (`<immintrin.h>`).
3. **64-byte cache line aligned buffers** via `posix_memalign`.
4. **Differential parity verification** asserting numerical equivalence between scalar and vector computations.

## Building and Running
```bash
make
./simd_bench
```
