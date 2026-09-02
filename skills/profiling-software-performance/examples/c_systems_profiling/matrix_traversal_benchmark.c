#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>
#include <string.h>
#include <math.h>
#include <assert.h>

#define MATRIX_DIM 4096   // 4096 x 4096 floats = 16M elements = 64 MB (exceeds L1, L2, L3 caches)
#define NUM_RUNS 5

static inline uint64_t get_time_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

// Memory barrier preventing the compiler from eliding the traversal loops
static inline void prevent_optimization(void *p) {
    __asm__ volatile("" : : "g"(p) : "memory");
}

// 1. Cache-Friendly Row-Major Traversal (Spatial Locality, Sequential Streaming)
// Reads contiguous 64-byte cache lines. Each cache line fetch loads 16 consecutive floats.
double traverse_row_major(const float *matrix, size_t dim) {
    double sum = 0.0;
    for (size_t r = 0; r < dim; r++) {
        size_t row_offset = r * dim;
        for (size_t c = 0; c < dim; c++) {
            sum += matrix[row_offset + c];
        }
    }
    prevent_optimization(&sum);
    return sum;
}

// 2. Cache-Unfriendly Column-Major Traversal (Stride = 4096 floats = 16 KB)
// Every single read jumps by 16 KB, causing an L1 cache miss and TLB miss on every element access.
double traverse_col_major(const float *matrix, size_t dim) {
    double sum = 0.0;
    for (size_t c = 0; c < dim; c++) {
        for (size_t r = 0; r < dim; r++) {
            sum += matrix[r * dim + c];
        }
    }
    prevent_optimization(&sum);
    return sum;
}

// 3. Worst-Case Random Traversal (Pointer-Chasing / Permuted Index Array)
// Simulates unordered graph node traversal with zero spatial or temporal locality.
double traverse_random(const float *matrix, const size_t *indices, size_t total_elements) {
    double sum = 0.0;
    for (size_t i = 0; i < total_elements; i++) {
        sum += matrix[indices[i]];
    }
    prevent_optimization(&sum);
    return sum;
}

int main(void) {
    size_t total_elements = (size_t)MATRIX_DIM * MATRIX_DIM;
    size_t matrix_bytes = total_elements * sizeof(float);
    printf("=== Systems Profiling: Cache Locality & Memory Hierarchy Benchmark ===\n");
    printf("Matrix Dimensions: %d x %d (%zu elements, %.2f MB memory footprint)\n\n",
           MATRIX_DIM, MATRIX_DIM, total_elements, (double)matrix_bytes / (1024.0 * 1024.0));

    // Allocate 64-byte aligned memory for cache line alignment
    float *matrix = NULL;
    if (posix_memalign((void **)&matrix, 64, matrix_bytes) != 0 || !matrix) {
        perror("posix_memalign failed");
        return 1;
    }

    // Populate matrix with deterministic test data
    for (size_t i = 0; i < total_elements; i++) {
        matrix[i] = (float)((i % 100) + 1) * 0.01f;
    }

    // Create random permutation table for random traversal
    size_t *indices = malloc(total_elements * sizeof(size_t));
    assert(indices != NULL);
    for (size_t i = 0; i < total_elements; i++) {
        indices[i] = i;
    }
    // Knuth-Fisher-Yates Shuffle
    srand(42);
    for (size_t i = total_elements - 1; i > 0; i--) {
        size_t j = ((size_t)rand() << 15 | rand()) % (i + 1);
        size_t temp = indices[i];
        indices[i] = indices[j];
        indices[j] = temp;
    }

    // Parity Verification: All traversals must yield identical mathematical sum
    double sum_row = traverse_row_major(matrix, MATRIX_DIM);
    double sum_col = traverse_col_major(matrix, MATRIX_DIM);
    double sum_rnd = traverse_random(matrix, indices, total_elements);

    double diff_col = fabs(sum_row - sum_col);
    double diff_rnd = fabs(sum_row - sum_rnd);

    printf("Parity Check:\n");
    printf("  Row-Major Sum:    %.6f\n", sum_row);
    printf("  Column-Major Sum: %.6f (delta = %.6e)\n", sum_col, diff_col);
    printf("  Random Sum:       %.6f (delta = %.6e)\n", sum_rnd, diff_rnd);
    assert(diff_col < 1e-3 && "Parity failure: Column-major traversal produced different sum!");
    assert(diff_rnd < 1e-3 && "Parity failure: Random traversal produced different sum!");
    printf("  [PASS] Mathematical parity verified across all traversal patterns.\n\n");

    // Benchmarking Loops
    printf("--- Performance Measurements (Best of %d runs) ---\n", NUM_RUNS);

    // 1. Row-major timing
    uint64_t best_row_ns = UINT64_MAX;
    for (int run = 0; run < NUM_RUNS; run++) {
        uint64_t start = get_time_ns();
        traverse_row_major(matrix, MATRIX_DIM);
        uint64_t elapsed = get_time_ns() - start;
        if (elapsed < best_row_ns) best_row_ns = elapsed;
    }
    double row_ms = (double)best_row_ns / 1e6;
    double row_gb_s = ((double)matrix_bytes / 1e9) / ((double)best_row_ns / 1e9);
    printf("1. Row-Major (Cache-Friendly):      %8.3f ms  | Throughput: %6.2f GB/s\n", row_ms, row_gb_s);

    // 2. Column-major timing
    uint64_t best_col_ns = UINT64_MAX;
    for (int run = 0; run < NUM_RUNS; run++) {
        uint64_t start = get_time_ns();
        traverse_col_major(matrix, MATRIX_DIM);
        uint64_t elapsed = get_time_ns() - start;
        if (elapsed < best_col_ns) best_col_ns = elapsed;
    }
    double col_ms = (double)best_col_ns / 1e6;
    double col_gb_s = ((double)matrix_bytes / 1e9) / ((double)best_col_ns / 1e9);
    double col_slowdown = col_ms / row_ms;
    printf("2. Column-Major (Stride-4096 Miss): %8.3f ms  | Throughput: %6.2f GB/s (%.1fx slower)\n",
           col_ms, col_gb_s, col_slowdown);

    // 3. Random timing
    uint64_t best_rnd_ns = UINT64_MAX;
    for (int run = 0; run < NUM_RUNS; run++) {
        uint64_t start = get_time_ns();
        traverse_random(matrix, indices, total_elements);
        uint64_t elapsed = get_time_ns() - start;
        if (elapsed < best_rnd_ns) best_rnd_ns = elapsed;
    }
    double rnd_ms = (double)best_rnd_ns / 1e6;
    double rnd_gb_s = ((double)matrix_bytes / 1e9) / ((double)best_rnd_ns / 1e9);
    double rnd_slowdown = rnd_ms / row_ms;
    printf("3. Random (Pointer-Chasing / TLB):  %8.3f ms  | Throughput: %6.2f GB/s (%.1fx slower)\n",
           rnd_ms, rnd_gb_s, rnd_slowdown);

    printf("\n=== Systems Architectural Diagnosis ===\n");
    printf("- Row-major traversal streams contiguous 64-byte cache lines; hardware prefetcher predicts stride perfectly.\n");
    printf("- Column-major traversal causes 100%% L1 D-Cache misses per element, incurring L2/L3 access latency on every iteration.\n");
    printf("- Random traversal invalidates TLB page translations and L3 cache lines, stalling CPU execution units on DRAM latency.\n");

    free(indices);
    free(matrix);
    return 0;
}
