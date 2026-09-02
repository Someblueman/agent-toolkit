/**
 * SIMD Vectorization Benchmark: Scalar vs ARM NEON / AVX2
 * =======================================================
 * Computes high-order polynomial vector transformation:
 *   out[i] = c0[i] + c1[i]*x + c2[i]*x^2 + c3[i]*x^3 + c4[i]*x^4
 * Features:
 *  1. Scalar baseline implementation (forced scalar computation)
 *  2. ARM NEON 128-bit SIMD implementation (with FMA vfmaq_f32 pipelines)
 *  3. x86_64 AVX2 256-bit SIMD implementation (_mm256_fmadd_ps)
 *  4. Strict differential parity verification against baseline
 *  5. High-resolution benchmark timing
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <math.h>
#include <time.h>

#if defined(__ARM_NEON) || defined(__ARM_NEON__)
    #include <arm_neon.h>
    #define HAS_NEON 1
#endif

#if defined(__AVX2__)
    #include <immintrin.h>
    #define HAS_AVX2 1
#endif

// Scalar Baseline Reference Implementation
__attribute__((noinline))
void polynomial_transform_scalar(
    const float* restrict c0,
    const float* restrict c1,
    const float* restrict c2,
    const float* restrict c3,
    const float* restrict c4,
    float x,
    float* restrict out,
    size_t count
) {
    float x2 = x * x;
    float x3 = x2 * x;
    float x4 = x2 * x2;
    #pragma clang loop vectorize(disable)
    for (size_t i = 0; i < count; ++i) {
        out[i] = c0[i] + c1[i] * x + c2[i] * x2 + c3[i] * x3 + c4[i] * x4;
    }
}

// ARM NEON SIMD Implementation (128-bit, 4 floats per vector, 2-way unrolled)
#if defined(HAS_NEON)
__attribute__((noinline))
void polynomial_transform_neon(
    const float* restrict c0,
    const float* restrict c1,
    const float* restrict c2,
    const float* restrict c3,
    const float* restrict c4,
    float x,
    float* restrict out,
    size_t count
) {
    float x2 = x * x;
    float x3 = x2 * x;
    float x4 = x2 * x2;

    float32x4_t vx  = vdupq_n_f32(x);
    float32x4_t vx2 = vdupq_n_f32(x2);
    float32x4_t vx3 = vdupq_n_f32(x3);
    float32x4_t vx4 = vdupq_n_f32(x4);

    size_t i = 0;
    size_t limit = count & ~7UL; // 8 floats per iteration (2x 128-bit lanes)

    for (; i < limit; i += 8) {
        // Lane 0 (first 4 floats)
        float32x4_t v0 = vld1q_f32(c0 + i);
        float32x4_t v1 = vld1q_f32(c1 + i);
        float32x4_t v2 = vld1q_f32(c2 + i);
        float32x4_t v3 = vld1q_f32(c3 + i);
        float32x4_t v4 = vld1q_f32(c4 + i);

        float32x4_t res0 = vfmaq_f32(v0, v1, vx);
        res0 = vfmaq_f32(res0, v2, vx2);
        res0 = vfmaq_f32(res0, v3, vx3);
        res0 = vfmaq_f32(res0, v4, vx4);
        vst1q_f32(out + i, res0);

        // Lane 1 (second 4 floats)
        float32x4_t v0_b = vld1q_f32(c0 + i + 4);
        float32x4_t v1_b = vld1q_f32(c1 + i + 4);
        float32x4_t v2_b = vld1q_f32(c2 + i + 4);
        float32x4_t v3_b = vld1q_f32(c3 + i + 4);
        float32x4_t v4_b = vld1q_f32(c4 + i + 4);

        float32x4_t res1 = vfmaq_f32(v0_b, v1_b, vx);
        res1 = vfmaq_f32(res1, v2_b, vx2);
        res1 = vfmaq_f32(res1, v3_b, vx3);
        res1 = vfmaq_f32(res1, v4_b, vx4);
        vst1q_f32(out + i + 4, res1);
    }

    // Scalar tail cleanup
    for (; i < count; ++i) {
        out[i] = c0[i] + c1[i] * x + c2[i] * x2 + c3[i] * x3 + c4[i] * x4;
    }
}
#endif

// x86_64 AVX2 SIMD Implementation (256-bit, 8 floats per vector)
#if defined(HAS_AVX2)
__attribute__((noinline))
void polynomial_transform_avx2(
    const float* restrict c0,
    const float* restrict c1,
    const float* restrict c2,
    const float* restrict c3,
    const float* restrict c4,
    float x,
    float* restrict out,
    size_t count
) {
    float x2 = x * x;
    float x3 = x2 * x;
    float x4 = x2 * x2;

    __m256 vx  = _mm256_set1_ps(x);
    __m256 vx2 = _mm256_set1_ps(x2);
    __m256 vx3 = _mm256_set1_ps(x3);
    __m256 vx4 = _mm256_set1_ps(x4);

    size_t i = 0;
    size_t limit = count & ~7UL;

    for (; i < limit; i += 8) {
        __m256 v0 = _mm256_loadu_ps(c0 + i);
        __m256 v1 = _mm256_loadu_ps(c1 + i);
        __m256 v2 = _mm256_loadu_ps(c2 + i);
        __m256 v3 = _mm256_loadu_ps(c3 + i);
        __m256 v4 = _mm256_loadu_ps(c4 + i);

        __m256 res = _mm256_fmadd_ps(v1, vx, v0);
        res = _mm256_fmadd_ps(v2, vx2, res);
        res = _mm256_fmadd_ps(v3, vx3, res);
        res = _mm256_fmadd_ps(v4, vx4, res);

        _mm256_storeu_ps(out + i, res);
    }

    // Scalar cleanup tail
    for (; i < count; ++i) {
        out[i] = c0[i] + c1[i] * x + c2[i] * x2 + c3[i] * x3 + c4[i] * x4;
    }
}
#endif

// Differential Parity Verification
bool verify_parity(const float* base, const float* opt, size_t count, float tolerance) {
    for (size_t i = 0; i < count; ++i) {
        float diff = fabsf(base[i] - opt[i]);
        if (diff > tolerance) {
            fprintf(stderr, "[-] Parity Error at index %zu: baseline %.6f vs optimized %.6f (diff: %.2e)\n",
                    i, base[i], opt[i], diff);
            return false;
        }
    }
    return true;
}

static inline double get_time_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

int main(int argc, char** argv) {
    (void)argc;
    (void)argv;
    const size_t N = 2000000; // 2 Million elements (~8 MB per coefficient array)
    const int ITERATIONS = 30;
    const float X_VAL = 1.41421f;

    printf("===============================================================\n");
    printf("     SIMD Vectorization Benchmark (NEON / AVX2 vs Scalar)      \n");
    printf("===============================================================\n");
    printf("Array Size: %zu elements\n", N);
    printf("Benchmark Iterations: %d\n\n", ITERATIONS);

    // Allocate 64-byte aligned memory buffers
    float* c0 = NULL;
    float* c1 = NULL;
    float* c2 = NULL;
    float* c3 = NULL;
    float* c4 = NULL;
    float* out_scalar = NULL;
    float* out_simd = NULL;

    posix_memalign((void**)&c0, 64, N * sizeof(float));
    posix_memalign((void**)&c1, 64, N * sizeof(float));
    posix_memalign((void**)&c2, 64, N * sizeof(float));
    posix_memalign((void**)&c3, 64, N * sizeof(float));
    posix_memalign((void**)&c4, 64, N * sizeof(float));
    posix_memalign((void**)&out_scalar, 64, N * sizeof(float));
    posix_memalign((void**)&out_simd, 64, N * sizeof(float));

    // Initialize with randomized floating-point values
    srand(12345);
    for (size_t i = 0; i < N; ++i) {
        c0[i] = (float)rand() / (float)RAND_MAX * 2.0f;
        c1[i] = (float)rand() / (float)RAND_MAX * 2.0f;
        c2[i] = (float)rand() / (float)RAND_MAX * 2.0f;
        c3[i] = (float)rand() / (float)RAND_MAX * 2.0f;
        c4[i] = (float)rand() / (float)RAND_MAX * 2.0f;
    }

    // Step 1: Run Scalar Baseline
    printf("[*] Running Scalar Baseline...\n");
    polynomial_transform_scalar(c0, c1, c2, c3, c4, X_VAL, out_scalar, N); // Warmup
    double t_start = get_time_sec();
    for (int it = 0; it < ITERATIONS; ++it) {
        polynomial_transform_scalar(c0, c1, c2, c3, c4, X_VAL, out_scalar, N);
    }
    double t_scalar = (get_time_sec() - t_start) / ITERATIONS * 1000.0; // ms

    // Step 2: Run SIMD Kernel
    printf("[*] Running SIMD Vector Kernel...\n");
#if defined(HAS_NEON)
    printf("    -> Using ARM NEON 128-bit Vector Engine\n");
    polynomial_transform_neon(c0, c1, c2, c3, c4, X_VAL, out_simd, N); // Warmup
    t_start = get_time_sec();
    for (int it = 0; it < ITERATIONS; ++it) {
        polynomial_transform_neon(c0, c1, c2, c3, c4, X_VAL, out_simd, N);
    }
    double t_simd = (get_time_sec() - t_start) / ITERATIONS * 1000.0; // ms
#elif defined(HAS_AVX2)
    printf("    -> Using x86_64 AVX2 256-bit Vector Engine\n");
    polynomial_transform_avx2(c0, c1, c2, c3, c4, X_VAL, out_simd, N); // Warmup
    t_start = get_time_sec();
    for (int it = 0; it < ITERATIONS; ++it) {
        polynomial_transform_avx2(c0, c1, c2, c3, c4, X_VAL, out_simd, N);
    }
    double t_simd = (get_time_sec() - t_start) / ITERATIONS * 1000.0; // ms
#else
    printf("    -> No native hardware vector ISA detected, fallback scalar.\n");
    double t_simd = t_scalar;
#endif

    // Step 3: Strict Parity Verification
    printf("\n[*] Verifying 100%% Differential Parity across all %zu outputs...\n", N);
    bool parity_ok = verify_parity(out_scalar, out_simd, N, 1e-3f);
    if (!parity_ok) {
        fprintf(stderr, "[-] CRITICAL: SIMD verification failed!\n");
        return 1;
    }
    printf("[+] SUCCESS: Differential parity confirmed! (Max absolute delta < 1e-3)\n\n");

    // Step 4: Report Benchmark Metrics
    double speedup = t_scalar / t_simd;

    printf("==================== BENCHMARK RESULTS ====================\n");
    printf("Scalar Baseline Time:   %8.3f ms\n", t_scalar);
    printf("SIMD Vector Time:       %8.3f ms\n", t_simd);
    printf("Performance Speedup:    %8.2fx\n", speedup);
    printf("===========================================================\n");

    free(c0);
    free(c1);
    free(c2);
    free(c3);
    free(c4);
    free(out_scalar);
    free(out_simd);

    return 0;
}
