# Performance, SIMD Vectorization, Data Layout, and Branchless Programming

Read this for cache line alignment, Structure of Arrays (SoA), compiler auto-vectorization, explicit SIMD intrinsics (AVX2/NEON), and branchless bitwise programming. Memory arenas belong in `memory-arenas.md`; atomics in `concurrency-atomics.md`; benchmarking tooling in `tooling-sanitizers-ci.md`.

---

## Data Layout: Array of Structures (AoS) vs Structure of Arrays (SoA)

When performing batch operations across collections, data layout determines cache line utilization and SIMD vectorizability:

- **Array of Structures (AoS)**: Best for single-entity access (e.g. updating one player entity). In batch computation, loading `x` forces loading `y`, `z`, and non-computational metadata, wasting 75%+ of cache line bandwidth.
- **Structure of Arrays (SoA)**: Contiguous arrays for each property. Enables $8 \times 32$-bit float loads per instruction via 256-bit SIMD registers with 100% cache line utilization.

### ❌ ANTI-PATTERN: AoS with Strided Cache Thrashing
```c
// Anti-pattern: Interleaved fields waste memory bandwidth during vector math
typedef struct particle {
    float x, y, z;
    float vx, vy, vz;
    char name[32]; // Metadata polluting the cache line
} particle_t;

void update_particles_aos(particle_t *pts, size_t count, float dt) {
    for (size_t i = 0; i < count; ++i) {
        pts[i].x += pts[i].vx * dt;
        pts[i].y += pts[i].vy * dt;
        pts[i].z += pts[i].vz * dt;
    }
}
```

### ✅ PRAGMATIC: Structure of Arrays (SoA) for Vectorization
```c
// Pragmatic: Contiguous coordinate arrays allow direct SIMD vector loads
typedef struct particle_system {
    float *x;
    float *y;
    float *z;
    float *vx;
    float *vy;
    float *vz;
    size_t count;
} particle_system_t;

void update_particles_soa(particle_system_t *ps, float dt) {
    float * restrict px = ps->x;
    float * restrict pvx = ps->vx;
    size_t count = ps->count;

    // Compiler automatically vectorizes this cleanly
    for (size_t i = 0; i < count; ++i) {
        px[i] += pvx[i] * dt;
    }
}
```

---

## Pointer Aliasing and the `restrict` Qualifier

By default, the C compiler assumes any two pointers of the same type might point to the same memory location (pointer aliasing). This forces the compiler to emit scalar re-loads after every store.

Declaring pointers with `restrict` guarantees they do not overlap, enabling aggressive auto-vectorization and register reuse.

```c
// restrict tells the compiler that dst, a, and b do not overlap in memory
void vector_add(float * restrict dst, 
                const float * restrict a, 
                const float * restrict b, 
                size_t n) {
    for (size_t i = 0; i < n; ++i) {
        dst[i] = a[i] + b[i];
    }
}
```

---

## Explicit SIMD Vector Intrinsics (AVX2 & ARM NEON)

For maximum throughput in critical computational kernels, use explicit vector intrinsics with a scalar cleanup loop for remainders.

### x86_64 AVX2 Implementation (8 floats per register)
```c
#if defined(__x86_64__) || defined(_M_X64)
#include <immintrin.h>

void vector_fma_avx2(float * restrict dst, 
                     const float * restrict a, 
                     const float * restrict b, 
                     float scale, 
                     size_t n) {
    size_t i = 0;
    __m256 vscale = _mm256_set1_ps(scale);

    // Vector loop: process 8 floats per iteration
    for (; i + 7 < n; i += 8) {
        __m256 va = _mm256_loadu_ps(&a[i]);
        __m256 vb = _mm256_loadu_ps(&b[i]);
        __m256 vres = _mm256_fmadd_ps(vb, vscale, va); // va + (vb * vscale)
        _mm256_storeu_ps(&dst[i], vres);
    }

    // Scalar tail loop for remaining elements
    for (; i < n; ++i) {
        dst[i] = a[i] + (b[i] * scale);
    }
}
#endif
```

### ARM NEON Implementation (4 floats per register)
```c
#if defined(__ARM_NEON) || defined(__aarch64__)
#include <arm_neon.h>

void vector_fma_neon(float * restrict dst, 
                     const float * restrict a, 
                     const float * restrict b, 
                     float scale, 
                     size_t n) {
    size_t i = 0;
    float32x4_t vscale = vdupq_n_f32(scale);

    // Vector loop: process 4 floats per iteration
    for (; i + 3 < n; i += 4) {
        float32x4_t va = vld1q_f32(&a[i]);
        float32x4_t vb = vld1q_f32(&b[i]);
        float32x4_t vres = vfmaq_f32(va, vb, vscale); // va + (vb * vscale)
        vst1q_f32(&dst[i], vres);
    }

    // Scalar tail loop for remaining elements
    for (; i < n; ++i) {
        dst[i] = a[i] + (b[i] * scale);
    }
}
#endif
```

---

## Branchless Programming & Bit Manipulation

In inner loops, unpredictable conditional branches cause CPU pipeline flushes (15-20 cycle penalty). Use branchless arithmetic and compiler builtins.

### Branchless Clamping / Min / Max
```c
// Branchless integer clamp to range [min_val, max_val]
static inline int32_t clamp_branchless(int32_t val, int32_t min_val, int32_t max_val) {
    int32_t d1 = val - min_val;
    val = min_val + (d1 & ~(d1 >> 31)); // val = max(val, min_val)
    int32_t d2 = max_val - val;
    val = max_val - (d2 & ~(d2 >> 31)); // val = min(val, max_val)
    return val;
}
```

### Hardware Bit Manipulation Builtins
```c
#include <stdint.h>

// Count leading zeros (useful for fast log2 calculation)
static inline int fast_log2_u32(uint32_t x) {
    if (x == 0) return -1;
    return 31 - __builtin_clz(x);
}

// Count set bits (population count)
static inline int count_bits_u64(uint64_t x) {
    return __builtin_popcountll(x);
}

// Count trailing zeros (find lowest set bit)
static inline int lowest_set_bit_index(uint32_t x) {
    if (x == 0) return -1;
    return __builtin_ctz(x);
}
```

---

## Anti-Pattern Summary

| Anti-Pattern | Performance Bottleneck | Pragmatic Replacement |
|---|---|---|
| AoS data layout for batch math | Cache line waste, prevents SIMD vectorization | Structure of Arrays (SoA) |
| Missing `restrict` qualifiers | Compiler assumes aliasing; scalar fallback | Add `restrict` to non-overlapping pointers |
| Omitted SIMD scalar tail loop | Out-of-bounds memory read/write or skipped elements | Process `n % VECTOR_WIDTH` in scalar loop |
| Unpredictable `if/else` in inner loop | CPU branch mispredictions and pipeline stalls | Branchless bitwise arithmetic or conditional move |
| Unaligned SIMD load without unaligned intrinsic | Crash (`SIGBUS`/`SIGSEGV`) on x86/ARM | Use `_mm256_loadu_ps` or `posix_memalign` |

---

## Fast-Path Verification Recipes

Benchmark and verify SIMD assembly output:

```bash
# Check compiler auto-vectorization optimization remarks
clang -O3 -Rpass=loop-vectorize -Rpass-missed=loop-vectorize -c src/vector_math.c

# Inspect generated assembly for SIMD instructions (ymm/zmm/v registers)
clang -O3 -S -masm=intel -o - src/vector_math.c | grep -E "vmov|vadd|vmul|vfmadd"
```
