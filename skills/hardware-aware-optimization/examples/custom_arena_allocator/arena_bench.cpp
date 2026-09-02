/**
 * Custom Monotonic Bump Arena Allocator Benchmark
 * ===============================================
 * Compares standard heap allocation (malloc/free, new/delete) against
 * a contiguous 64-byte cache-aligned Monotonic Arena Allocator.
 * 
 * Workload:
 *  Constructs, traverses, and deallocates a tree/graph of 1,000,000 AST nodes.
 *  Features:
 *  1. Baseline system heap allocator
 *  2. Custom 64-byte aligned monotonic bump arena allocator
 *  3. Differential node traversal checksum verification
 *  4. High-resolution timing metrics
 */

#include <iostream>
#include <vector>
#include <chrono>
#include <cstdint>
#include <cstddef>
#include <cstdlib>
#include <cassert>
#include <new>

// AST Node Structure (32 bytes)
struct ASTNode {
    uint32_t id;
    int32_t value;
    uint32_t type_tag;
    uint32_t flags;
    ASTNode* left;
    ASTNode* right;

    ASTNode(uint32_t i, int32_t val, uint32_t tag)
        : id(i), value(val), type_tag(tag), flags(0), left(nullptr), right(nullptr) {}
};

// 64-Byte Cache-Aligned Monotonic Bump Arena Allocator
class MonotonicArena {
public:
    explicit MonotonicArena(size_t capacity_bytes)
        : capacity_(capacity_bytes), offset_(0) {
        buffer_ = static_cast<uint8_t*>(std::aligned_alloc(64, capacity_bytes));
        assert(buffer_ != nullptr && "Failed to allocate memory for Arena");
    }

    ~MonotonicArena() {
        std::free(buffer_);
    }

    // Fast O(1) aligned bump allocation
    void* allocate(size_t size, size_t alignment = 8) noexcept {
        size_t current_addr = reinterpret_cast<size_t>(buffer_ + offset_);
        size_t aligned_addr = (current_addr + (alignment - 1)) & ~(alignment - 1);
        size_t new_offset = (aligned_addr - reinterpret_cast<size_t>(buffer_)) + size;

        if (new_offset > capacity_) {
            return nullptr; // Out of arena memory
        }

        offset_ = new_offset;
        return reinterpret_cast<void*>(aligned_addr);
    }

    template <typename T, typename... Args>
    T* create(Args&&... args) {
        void* mem = allocate(sizeof(T), alignof(T));
        if (!mem) return nullptr;
        return new (mem) T(std::forward<Args>(args)...);
    }

    // Instantaneous O(1) bulk reset
    void reset() noexcept {
        offset_ = 0;
    }

    size_t bytes_used() const noexcept { return offset_; }
    size_t capacity() const noexcept { return capacity_; }

private:
    uint8_t* buffer_{nullptr};
    size_t capacity_{0};
    size_t offset_{0};
};

// Recursive AST Tree Construction Helper
ASTNode* build_tree_heap(int depth, uint32_t& id_counter) {
    if (depth <= 0) return nullptr;
    uint32_t id = ++id_counter;
    ASTNode* node = new ASTNode(id, static_cast<int32_t>(id * 3 - 7), depth);
    node->left = build_tree_heap(depth - 1, id_counter);
    node->right = build_tree_heap(depth - 1, id_counter);
    return node;
}

void free_tree_heap(ASTNode* node) {
    if (!node) return;
    free_tree_heap(node->left);
    free_tree_heap(node->right);
    delete node;
}

ASTNode* build_tree_arena(int depth, uint32_t& id_counter, MonotonicArena& arena) {
    if (depth <= 0) return nullptr;
    uint32_t id = ++id_counter;
    ASTNode* node = arena.create<ASTNode>(id, static_cast<int32_t>(id * 3 - 7), depth);
    node->left = build_tree_arena(depth - 1, id_counter, arena);
    node->right = build_tree_arena(depth - 1, id_counter, arena);
    return node;
}

// Tree Traversal and Checksum Calculation
uint64_t compute_tree_checksum(const ASTNode* node) {
    if (!node) return 0;
    uint64_t current = (static_cast<uint64_t>(node->id) * 31ULL) ^ static_cast<uint64_t>(node->value);
    return current + compute_tree_checksum(node->left) + compute_tree_checksum(node->right);
}

int main() {
    constexpr int TREE_DEPTH = 20; // 2^20 - 1 = 1,048,575 nodes (~33.5 MB data)
    constexpr int ITERATIONS = 10;
    const size_t ARENA_SIZE = 64 * 1024 * 1024; // 64 MB

    std::cout << "===============================================================\n";
    std::cout << "   Monotonic Bump Arena vs System Heap Allocator Benchmark     \n";
    std::cout << "===============================================================\n";
    std::cout << "Tree Depth: " << TREE_DEPTH << " (1,048,575 AST nodes per cycle)\n";
    std::cout << "Node Size: " << sizeof(ASTNode) << " bytes\n";
    std::cout << "Benchmark Iterations: " << ITERATIONS << "\n\n";

    // 1. Heap Baseline Benchmark
    std::cout << "[*] Running System Heap Allocator (new / delete)...\n";
    uint64_t heap_checksum = 0;
    auto start_heap = std::chrono::high_resolution_clock::now();

    for (int it = 0; it < ITERATIONS; ++it) {
        uint32_t id_gen = 0;
        ASTNode* root = build_tree_heap(TREE_DEPTH, id_gen);
        heap_checksum = compute_tree_checksum(root);
        free_tree_heap(root);
    }

    auto end_heap = std::chrono::high_resolution_clock::now();
    double time_heap_ms = std::chrono::duration<double, std::milli>(end_heap - start_heap).count() / ITERATIONS;

    // 2. Monotonic Arena Allocator Benchmark
    std::cout << "[*] Running Monotonic Bump Arena Allocator...\n";
    MonotonicArena arena(ARENA_SIZE);
    uint64_t arena_checksum = 0;
    auto start_arena = std::chrono::high_resolution_clock::now();

    for (int it = 0; it < ITERATIONS; ++it) {
        arena.reset(); // Instantaneous O(1) bulk free!
        uint32_t id_gen = 0;
        ASTNode* root = build_tree_arena(TREE_DEPTH, id_gen, arena);
        arena_checksum = compute_tree_checksum(root);
    }

    auto end_arena = std::chrono::high_resolution_clock::now();
    double time_arena_ms = std::chrono::duration<double, std::milli>(end_arena - start_arena).count() / ITERATIONS;

    // 3. Differential Parity Check
    std::cout << "\n[*] Verifying Differential Parity between Heap and Arena...\n";
    if (heap_checksum != arena_checksum) {
        std::cerr << "[-] CRITICAL: Checksum mismatch! Heap: " << heap_checksum << " vs Arena: " << arena_checksum << "\n";
        return 1;
    }
    std::cout << "[+] SUCCESS: 100% Differential Parity Confirmed! Checksum: " << arena_checksum << "\n\n";

    // 4. Results
    double speedup = time_heap_ms / time_arena_ms;
    double alloc_rate_heap = (1048575.0) / (time_heap_ms * 1e-3) / 1e6; // M allocs/sec
    double alloc_rate_arena = (1048575.0) / (time_arena_ms * 1e-3) / 1e6;

    std::cout << "==================== BENCHMARK RESULTS ====================\n";
    std::cout << "System Heap Time:      " << time_heap_ms << " ms  (" << alloc_rate_heap << " Million alloc+free/sec)\n";
    std::cout << "Monotonic Arena Time:  " << time_arena_ms << " ms  (" << alloc_rate_arena << " Million alloc+free/sec)\n";
    std::cout << "Arena Speedup:         " << speedup << "x\n";
    std::cout << "===========================================================\n";

    return 0;
}
