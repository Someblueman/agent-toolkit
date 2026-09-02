# SIMD Vectorization & Hardware Intrinsics Guide

Single Instruction, Multiple Data (SIMD) processes multiple independent data elements simultaneously in a single CPU instruction cycle using wide vector registers (128-bit, 256-bit, or 512-bit). Vectorization is essential for high-throughput arithmetic, digital signal processing, linear algebra, and high-frequency data filtering.

---

## 1. Vector Register Architectures

| Architecture / ISA | Register Width | Elements per Register (`float` / `int32`) | Elements per Register (`double` / `int64`) | Typical Instruction Set |
|---|---|---|---|---|
| **ARM NEON** (AArch64 / Apple Silicon) | **128-bit** (`v0`–`v31`) | 4 floats / 4 int32 | 2 doubles / 2 int64 | Native in all ARMv8/v9 CPUs |
| **x86 SSE4.2** | **128-bit** (`xmm0`–`xmm15`) | 4 floats / 4 int32 | 2 doubles / 2 int64 | Universal across x86_64 |
| **x86 AVX2 / FMA** | **256-bit** (`ymm0`–`ymm15`) | 8 floats / 8 int32 | 4 doubles / 4 int64 | Standard on modern x86_64 |
| **x86 AVX-512** | **512-bit** (`zmm0`–`zmm31`) | 16 floats / 16 int32 | 8 doubles / 8 int64 | Intel Xeon / AMD Zen 4/5 |

---

## 2. ARM NEON Intrinsics (`<arm_neon.h>`)

ARM NEON registers are 128 bits wide and are accessed via `<arm_neon.h>`.

### Common NEON Types
- `float32x4_t`: Vector of 4 single-precision 32-bit floats.
- `float64x2_t`: Vector of 2 double-precision 64-bit floats.
- `int32x4_t` / `uint32x4_t`: Vector of 4 32-bit signed/unsigned integers.
- `int16x8_t` / `uint8x16_t`: Vector of 8 16-bit integers / 16 8-bit bytes.

### Core NEON Operations
```c
#include <arm_neon.h>

// 1. Vector Loads and Stores
float32x4_t va = vld1q_f32(a_ptr);     // Load 4 contiguous floats
vst1q_f32(out_ptr, va);                // Store 4 floats to memory

// 2. Vector Arithmetic
float32x4_t vsum = vaddq_f32(va, vb);  // vsum[i] = va[i] + vb[i]
float32x4_t vmul = vmulq_f32(va, vb);  // vmul[i] = va[i] * vb[i]

// 3. Fused Multiply-Add (FMA): res = acc + (va * vb) in a single cycle
float32x4_t vfma = vfmaq_f32(vacc, va, vb);

// 4. Comparison and Masking
uint32x4_t mask = vcgtq_f32(va, vb);   // mask[i] = (va[i] > vb[i]) ? 0xFFFFFFFF : 0
float32x4_t vsel = vbslq_f32(mask, va, vb); // Bitwise select: mask ? va : vb

// 5. Horizontal Reduction (Sum all 4 lanes into 1 scalar)
float total = vaddvq_f32(vsum);        // Fast single instruction on AArch64
```

### Complete NEON Dot Product Example:
```c
#include <arm_neon.h>
#include <stddef.h>

float dot_product_neon(const float* restrict a, const float* restrict b, size_t n) {
    size_t i = 0;
    float32x4_t acc0 = vdupq_n_f32(0.0f);
    float32x4_t acc1 = vdupq_n_f32(0.0f);
    
    // Process 8 floats per loop iteration (2x unrolled 128-bit vector pipelines)
    size_t vec_limit = n & ~7UL;
    for (; i < vec_limit; i += 8) {
        float32x4_t va0 = vld1q_f32(a + i);
        float32x4_t vb0 = vld1q_f32(b + i);
        acc0 = vfmaq_f32(acc0, va0, vb0);
        
        float32x4_t va1 = vld1q_f32(a + i + 4);
        float32x4_t vb1 = vld1q_f32(b + i + 4);
        acc1 = vfmaq_f32(acc1, va1, vb1);
    }
    
    // Combine accumulators and horizontally reduce
    float32x4_t acc = vaddq_f32(acc0, acc1);
    float sum = vaddvq_f32(acc);
    
    // Scalar tail cleanup for remaining elements (0 to 7)
    for (; i < n; ++i) {
        sum += a[i] * b[i];
    }
    return sum;
}
```

---

## 3. x86_64 AVX2 / AVX-512 Intrinsics (`<immintrin.h>`)

AVX2 operates on 256-bit registers (`__m256`, `__m256i`, `__m256d`).

### Core AVX2 Operations
```c
#include <immintrin.h>

// 1. Unaligned vs Aligned Loads/Stores
__m256 va = _mm256_loadu_ps(a_ptr);     // Load 8 unaligned floats
__m256 vb = _mm256_load_ps(aligned_ptr);// Load 8 floats (requires 32-byte alignment!)
_mm256_storeu_ps(out_ptr, va);          // Store 8 floats

// 2. Vector Arithmetic & FMA
__m256 vsum = _mm256_add_ps(va, vb);    // Add 8 floats
__m256 vfma = _mm256_fmadd_ps(va, vb, vacc); // FMA: (va * vb) + vacc

// 3. Horizontal Reduction (Sum 8 lanes of __m256)
float horizontal_sum_avx2(__m256 v) {
    // High 128-bits + Low 128-bits
    __m128 vlow = _mm256_castps256_ps128(v);
    __m128 vhigh = _mm256_extractf128_ps(v, 1);
    __m128 vsum128 = _mm_add_ps(vlow, vhigh);
    
    // Intra-128-bit reduction
    __m128 shuf = _mm_movehl_ps(vsum128, vsum128);
    __m128 sums = _mm_add_ps(vsum128, shuf);
    shuf = _mm_shuffle_ps(sums, sums, 1);
    sums = _mm_add_ss(sums, shuf);
    return _mm_cvtss_f32(sums);
}
```

---

## 4. Compiler Auto-Vectorization Best Practices

Modern compilers (Clang, GCC) can automatically vectorize loops without manual intrinsics if written according to these strict rules:

### 1. The `restrict` Pointer Qualifier
The compiler cannot vectorize if pointers might alias (overlap in memory):
```c
// BAD: Compiler assumes dst might overlap with src1 or src2 -> Cannot vectorize
void add_arrays_bad(float* dst, const float* src1, const float* src2, size_t n) {
    for (size_t i = 0; i < n; ++i) dst[i] = src1[i] + src2[i];
}

// GOOD: 'restrict' promises no pointer aliasing -> Vectorizer emits AVX2/NEON
void add_arrays_good(float* restrict dst, const float* restrict src1, const float* restrict src2, size_t n) {
    #pragma clang loop vectorize(enable)
    #pragma clang loop interleave_count(4)
    for (size_t i = 0; i < n; ++i) {
        dst[i] = src1[i] + src2[i];
    }
}
```

### 2. Clang Vectorization Diagnostics
Use compiler flags to inspect auto-vectorization decisions:
```bash
clang -O3 -Rpass=loop-vectorize -Rpass-missed=loop-vectorize -Rpass-analysis=loop-vectorize kernel.c
```
*Output*:
```text
remark: vectorized loop (vectorization width: 4, interleaved count: 4) [-Rpass=loop-vectorize]
```

---

## 5. Portable SIMD Patterns

To write code that compiles natively on both ARM NEON and x86_64 AVX2, use preprocessor abstraction layers:

```c
#if defined(__ARM_NEON) || defined(__ARM_NEON__)
    #include <arm_neon.h>
    #define HAS_NEON 1
#elif defined(__AVX2__)
    #include <immintrin.h>
    #define HAS_AVX2 1
#endif

void vector_scale(float* restrict out, const float* restrict in, float scale, size_t count) {
#if defined(HAS_AVX2)
    __m256 vscale = _mm256_set1_ps(scale);
    size_t i = 0;
    for (; i + 8 <= count; i += 8) {
        __m256 vin = _mm256_loadu_ps(in + i);
        _mm256_storeu_ps(out + i, _mm256_mul_ps(vin, vscale));
    }
    for (; i < count; ++i) out[i] = in[i] * scale;
#elif defined(HAS_NEON)
    float32x4_t vscale = vdupq_n_f32(scale);
    size_t i = 0;
    for (; i + 4 <= count; i += 4) {
        float32x4_t vin = vld1q_f32(in + i);
        vst1q_f32(out + i, vmulq_f32(vin, vscale));
    }
    for (; i < count; ++i) out[i] = in[i] * scale;
#else
    // Fallback scalar loop with auto-vectorization hints
    #pragma clang loop vectorize(enable)
    for (size_t i = 0; i < count; ++i) {
        out[i] = in[i] * scale;
    }
#endif
}
```

---

## 6. SIMD Edge Cases & Pitfalls

1. **Alignment Segfaults**: Loading unaligned memory with aligned load intrinsics (`_mm256_load_ps`) causes instant `SIGSEGV`. Always use unaligned variants (`_mm256_loadu_ps` / `vld1q_f32`) unless data is explicitly allocated on 32-byte or 64-byte boundaries with `posix_memalign` / `alignas`.
2. **Floating-Point Non-Associativity**: Due to IEEE-754 precision rounding, `(a + b) + c` does not strictly equal `a + (b + c)`. SIMD reductions accumulate values in a different order than serial scalar loops. When running differential parity checks, compare floats using an epsilon tolerance (`fabs(a - b) < 1e-5f`) rather than strict bitwise equality `==`.
3. **AVX-512 Frequency Throttling**: On earlier Intel Skylake-X/Cascade Lake chips, executing heavy 512-bit vector instructions caused the CPU core to throttle its base clock frequency by 10%–20%. AVX2 (256-bit) often outperformed AVX-512 for mixed workloads on those older architectures. Modern AMD Zen 4/5 and Intel Sapphire Rapids execute AVX-512 without throttling penalties.
4. **Tail Processing**: Always peel off the loop tail (`count % SIMD_WIDTH`) with a scalar loop or masked store to avoid reading past buffer bounds (which causes `SIGSEGV` at page boundaries).
