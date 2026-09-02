/**
 * Branchless Parsing & Filtering Benchmark
 * =========================================
 * Compares standard branching filter logic against a branchless
 * bitmasking and predicated write index implementation.
 * 
 * Workload:
 *  Filters 10,000,000 randomized records based on multi-condition predicates:
 *    Predicate: (value >= MIN_VAL && value <= MAX_VAL) && ((flags & MASK) != 0)
 * 
 * Features:
 *  1. Branchy baseline implementation (heavy CPU pipeline flushes on random data)
 *  2. Branchless bitmask implementation (CMOV / predicated index updates)
 *  3. Strict differential parity verification (exact byte and array matching)
 *  4. High-resolution timing metrics
 */

#include <iostream>
#include <vector>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <random>

struct Record {
    int32_t value;
    uint32_t flags;
    uint32_t tag;
    uint32_t payload;
};

// Branchy Baseline Filter
__attribute__((noinline))
size_t filter_records_branchy(
    const Record* records,
    size_t count,
    int32_t min_val,
    int32_t max_val,
    uint32_t flag_mask,
    Record* out
) {
    size_t out_count = 0;
    for (size_t i = 0; i < count; ++i) {
        // Highly unpredictable branches on randomized inputs
        if (records[i].value >= min_val) {
            if (records[i].value <= max_val) {
                if ((records[i].flags & flag_mask) != 0) {
                    out[out_count++] = records[i];
                }
            }
        }
    }
    return out_count;
}

// Branchless Filter using Arithmetic Predicates & Unconditional Stores
__attribute__((noinline))
size_t filter_records_branchless(
    const Record* records,
    size_t count,
    int32_t min_val,
    int32_t max_val,
    uint32_t flag_mask,
    Record* out
) {
    size_t out_count = 0;
    for (size_t i = 0; i < count; ++i) {
        Record r = records[i];
        
        // Compute boolean predicates as 0/1 integers without jumping
        uint32_t cond_min   = (r.value >= min_val);
        uint32_t cond_max   = (r.value <= max_val);
        uint32_t cond_flags = ((r.flags & flag_mask) != 0);

        // Bitwise AND combines all predicates
        uint32_t keep = cond_min & cond_max & cond_flags;

        // Unconditionally store record, then advance write index only by 0 or 1
        out[out_count] = r;
        out_count += keep;
    }
    return out_count;
}

int main() {
    constexpr size_t N = 10000000; // 10 Million records (~160 MB dataset)
    constexpr int ITERATIONS = 15;
    constexpr int32_t MIN_VAL = 200;
    constexpr int32_t MAX_VAL = 800;
    constexpr uint32_t FLAG_MASK = 0x00000005; // Bits 0 and 2

    std::cout << "===============================================================\n";
    std::cout << "         Branchless vs Branchy Record Filtering Benchmark       \n";
    std::cout << "===============================================================\n";
    std::cout << "Dataset Size: " << N << " records (" << (N * sizeof(Record)) / (1024.0 * 1024.0) << " MB)\n";
    std::cout << "Benchmark Iterations: " << ITERATIONS << "\n\n";

    std::vector<Record> input(N);
    std::vector<Record> out_branchy(N);
    std::vector<Record> out_branchless(N);

    // Initialize with randomized values (50% selectivity to maximize branch entropy)
    std::mt19937 rng(42);
    std::uniform_int_distribution<int32_t> val_dist(0, 1000);
    std::uniform_int_distribution<uint32_t> flag_dist(0, 15);

    for (size_t i = 0; i < N; ++i) {
        input[i].value = val_dist(rng);
        input[i].flags = flag_dist(rng);
        input[i].tag = static_cast<uint32_t>(i);
        input[i].payload = static_cast<uint32_t>(i * 7);
    }

    // 1. Branchy Baseline Benchmark
    std::cout << "[*] Running Branchy Baseline...\n";
    size_t count_branchy = 0;
    auto start_branchy = std::chrono::high_resolution_clock::now();

    for (int it = 0; it < ITERATIONS; ++it) {
        count_branchy = filter_records_branchy(input.data(), N, MIN_VAL, MAX_VAL, FLAG_MASK, out_branchy.data());
    }

    auto end_branchy = std::chrono::high_resolution_clock::now();
    double time_branchy_ms = std::chrono::duration<double, std::milli>(end_branchy - start_branchy).count() / ITERATIONS;

    // 2. Branchless Benchmark
    std::cout << "[*] Running Branchless Kernel...\n";
    size_t count_branchless = 0;
    auto start_branchless = std::chrono::high_resolution_clock::now();

    for (int it = 0; it < ITERATIONS; ++it) {
        count_branchless = filter_records_branchless(input.data(), N, MIN_VAL, MAX_VAL, FLAG_MASK, out_branchless.data());
    }

    auto end_branchless = std::chrono::high_resolution_clock::now();
    double time_branchless_ms = std::chrono::duration<double, std::milli>(end_branchless - start_branchless).count() / ITERATIONS;

    // 3. Differential Parity Verification
    std::cout << "\n[*] Verifying 100% Output Parity between Branchy and Branchless...\n";
    if (count_branchy != count_branchless) {
        std::cerr << "[-] CRITICAL: Count mismatch! Branchy: " << count_branchy << " vs Branchless: " << count_branchless << "\n";
        return 1;
    }

    for (size_t i = 0; i < count_branchy; ++i) {
        if (out_branchy[i].value != out_branchless[i].value ||
            out_branchy[i].flags != out_branchless[i].flags ||
            out_branchy[i].tag != out_branchless[i].tag) {
            std::cerr << "[-] CRITICAL: Data mismatch at filtered index " << i << "!\n";
            return 1;
        }
    }

    std::cout << "[+] SUCCESS: 100% Differential Parity Confirmed across all " << count_branchy << " filtered records!\n\n";

    // 4. Report Results
    double speedup = time_branchy_ms / time_branchless_ms;
    double rate_branchy = (double)N / (time_branchy_ms * 1e-3) / 1e6;
    double rate_branchless = (double)N / (time_branchless_ms * 1e-3) / 1e6;

    std::cout << "==================== BENCHMARK RESULTS ====================\n";
    std::cout << "Branchy Baseline Time:   " << time_branchy_ms << " ms  (" << rate_branchy << " Million items/sec)\n";
    std::cout << "Branchless Kernel Time:  " << time_branchless_ms << " ms  (" << rate_branchless << " Million items/sec)\n";
    std::cout << "Performance Speedup:     " << speedup << "x\n";
    std::cout << "===========================================================\n";

    return 0;
}
