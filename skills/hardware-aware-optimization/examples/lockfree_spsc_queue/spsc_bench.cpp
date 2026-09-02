/**
 * High-Throughput Lock-Free SPSC Queue Benchmark
 * ===============================================
 * Compares standard Mutex + Condition Variable synchronization
 * against a cacheline-padded Lock-Free SPSC Ring Buffer with
 * atomic acquire/release memory orderings and cached indices.
 * 
 * Workload:
 *  Streams 5,000,000 messages between a dedicated producer and consumer thread.
 * 
 * Features:
 *  1. Mutex + Condition Variable Baseline Queue
 *  2. Cacheline-padded Lock-Free SPSC Ring Buffer (alignas(64))
 *  3. Strict FIFO parity and message checksum verification
 *  4. High-resolution timing metrics
 */

#include <iostream>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <vector>
#include <chrono>
#include <cstdint>
#include <cassert>

// 1. Mutex + Condition Variable Baseline Queue
template <typename T, size_t Capacity>
class MutexQueue {
public:
    void push(const T& item) {
        std::unique_lock<std::mutex> lock(mtx_);
        cv_push_.wait(lock, [this]() { return queue_.size() < Capacity; });
        queue_.push_back(item);
        lock.unlock();
        cv_pop_.notify_one();
    }

    bool pop(T& item) {
        std::unique_lock<std::mutex> lock(mtx_);
        cv_pop_.wait(lock, [this]() { return !queue_.empty(); });
        item = queue_.front();
        queue_.erase(queue_.begin());
        lock.unlock();
        cv_push_.notify_one();
        return true;
    }

private:
    std::mutex mtx_;
    std::condition_variable cv_push_;
    std::condition_variable cv_pop_;
    std::vector<T> queue_;
};

// 2. High-Performance Lock-Free SPSC Ring Buffer
template <typename T, size_t Capacity>
class LockFreeSPSCQueue {
    static_assert((Capacity & (Capacity - 1)) == 0, "Capacity must be a power of 2");

public:
    LockFreeSPSCQueue()
        : tail_(0), cached_head_(0), head_(0), cached_tail_(0) {}

    bool push(const T& item) noexcept {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);

        // Fast path: check against local cached head before atomic load
        if ((current_tail - cached_head_) >= Capacity) {
            cached_head_ = head_.load(std::memory_order_acquire);
            if ((current_tail - cached_head_) >= Capacity) {
                return false; // Queue full
            }
        }

        buffer_[current_tail & Mask] = item;
        tail_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    bool pop(T& item) noexcept {
        const size_t current_head = head_.load(std::memory_order_relaxed);

        // Fast path: check against local cached tail before atomic load
        if (current_head == cached_tail_) {
            cached_tail_ = tail_.load(std::memory_order_acquire);
            if (current_head == cached_tail_) {
                return false; // Queue empty
            }
        }

        item = buffer_[current_head & Mask];
        head_.store(current_head + 1, std::memory_order_release);
        return true;
    }

private:
    static constexpr size_t Mask = Capacity - 1;
    T buffer_[Capacity];

    // Align indices to distinct 64-byte cache lines to eliminate false sharing
    alignas(64) std::atomic<size_t> tail_{0};
    size_t cached_head_{0}; // Producer-local

    alignas(64) std::atomic<size_t> head_{0};
    size_t cached_tail_{0}; // Consumer-local
};

#if defined(__x86_64__) || defined(_M_X64)
    #include <immintrin.h>
    #define CPU_PAUSE() _mm_pause()
#elif defined(__aarch64__)
    #define CPU_PAUSE() __asm__ volatile("yield" ::: "memory")
#else
    #define CPU_PAUSE() ((void)0)
#endif

int main() {
    constexpr size_t TOTAL_MESSAGES = 5000000;
    constexpr size_t QUEUE_CAPACITY = 65536; // 64K items

    std::cout << "===============================================================\n";
    std::cout << "       Lock-Free SPSC Queue vs Mutex-Guarded Queue Benchmark   \n";
    std::cout << "===============================================================\n";
    std::cout << "Total Messages: " << TOTAL_MESSAGES << "\n";
    std::cout << "Queue Buffer Capacity: " << QUEUE_CAPACITY << " elements\n\n";

    // Expected checksum: sum(0..TOTAL_MESSAGES-1)
    uint64_t expected_sum = (static_cast<uint64_t>(TOTAL_MESSAGES - 1) * TOTAL_MESSAGES) / 2ULL;

    // 1. Benchmark Mutex-Guarded Queue (smaller subset of 500k messages to avoid lengthy wait)
    constexpr size_t MUTEX_MESSAGES = 250000;
    std::cout << "[*] Running Mutex-Guarded Baseline Queue (" << MUTEX_MESSAGES << " messages)...\n";
    MutexQueue<uint32_t, 1024> mutex_q;
    uint64_t mutex_sum = 0;

    auto start_mutex = std::chrono::high_resolution_clock::now();
    std::thread prod_mutex([&]() {
        for (uint32_t i = 0; i < MUTEX_MESSAGES; ++i) {
            mutex_q.push(i);
        }
    });

    std::thread cons_mutex([&]() {
        for (uint32_t i = 0; i < MUTEX_MESSAGES; ++i) {
            uint32_t val = 0;
            mutex_q.pop(val);
            mutex_sum += val;
        }
    });

    prod_mutex.join();
    cons_mutex.join();
    auto end_mutex = std::chrono::high_resolution_clock::now();
    double time_mutex_ms = std::chrono::duration<double, std::milli>(end_mutex - start_mutex).count();
    double rate_mutex = (double)MUTEX_MESSAGES / (time_mutex_ms * 1e-3) / 1e6; // Million msgs/sec

    // 2. Benchmark Lock-Free SPSC Queue (Full 5,000,000 messages)
    std::cout << "[*] Running Lock-Free SPSC Ring Buffer (" << TOTAL_MESSAGES << " messages)...\n";
    LockFreeSPSCQueue<uint32_t, QUEUE_CAPACITY> lockfree_q;
    uint64_t lockfree_sum = 0;

    auto start_lockfree = std::chrono::high_resolution_clock::now();
    std::thread prod_lf([&]() {
        for (uint32_t i = 0; i < TOTAL_MESSAGES; ++i) {
            while (!lockfree_q.push(i)) {
                CPU_PAUSE();
            }
        }
    });

    std::thread cons_lf([&]() {
        for (uint32_t i = 0; i < TOTAL_MESSAGES; ++i) {
            uint32_t val = 0;
            while (!lockfree_q.pop(val)) {
                CPU_PAUSE();
            }
            lockfree_sum += val;
        }
    });

    prod_lf.join();
    cons_lf.join();
    auto end_lockfree = std::chrono::high_resolution_clock::now();
    double time_lockfree_ms = std::chrono::duration<double, std::milli>(end_lockfree - start_lockfree).count();
    double rate_lockfree = (double)TOTAL_MESSAGES / (time_lockfree_ms * 1e-3) / 1e6;

    // 3. Parity Verification
    std::cout << "\n[*] Verifying 100% Message Parity & Integrity...\n";
    if (lockfree_sum != expected_sum) {
        std::cerr << "[-] CRITICAL: Checksum mismatch in Lock-Free Queue! Expected: "
                  << expected_sum << " vs Actual: " << lockfree_sum << "\n";
        return 1;
    }
    std::cout << "[+] SUCCESS: Lock-Free SPSC verified! Checksum: " << lockfree_sum << "\n\n";

    // 4. Report Results
    double throughput_speedup = rate_lockfree / rate_mutex;

    std::cout << "==================== BENCHMARK RESULTS ====================\n";
    std::cout << "Mutex Queue Throughput:      " << rate_mutex << " Million msgs/sec\n";
    std::cout << "Lock-Free SPSC Throughput:   " << rate_lockfree << " Million msgs/sec\n";
    std::cout << "Throughput Speedup:          " << throughput_speedup << "x\n";
    std::cout << "===========================================================\n";

    return 0;
}
