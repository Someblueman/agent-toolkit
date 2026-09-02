# Lock-Free Concurrency & Atomic Memory Orderings

Traditional multi-threaded synchronization relies on OS mutexes and condition variables. Under high thread contention, mutexes force CPU cores to yield, triggering kernel context switches (costing 1,000–5,000+ clock cycles), cache invalidations, and priority inversions.

Lock-free data structures eliminate locks entirely by using CPU atomic hardware instructions (such as `atomic_compare_exchange` and `atomic_fetch_add`) coupled with fine-grained memory consistency orderings.

---

## 1. Atomic Memory Consistency Models

Compilers and modern out-of-order CPU cores aggressively reorder independent memory reads and writes to optimize instruction pipelining. Atomic memory orderings define the exact synchronization barriers between threads.

| Memory Ordering | Hardware Barrier Cost (x86) | Hardware Barrier Cost (ARM64) | Synchronization Semantics | Typical Use Case |
|---|---|---|---|---|
| `memory_order_relaxed` | 0 cycles (Plain MOV) | 0 cycles (Plain LDR/STR) | Guarantees atomicity only. No ordering or visibility guarantees. | Incrementing simple telemetry counters. |
| `memory_order_acquire` | 0 cycles (x86 loads are acquire) | Light `LDAR` instruction | No reads/writes after this load can be reordered before it. | Reading published data, polling queue head. |
| `memory_order_release` | 0 cycles (x86 stores are release) | Light `STLR` instruction | No reads/writes before this store can be reordered after it. | Publishing data to another thread, updating queue tail. |
| `memory_order_acq_rel` | 0 cycles | Combined `LDAR`/`STLR` | Combines acquire and release semantics on Read-Modify-Write. | Lock acquisition, reference count decrement. |
| `memory_order_seq_cst` | Heavy (`MFENCE` / `LOCK`) | Heavy (`DMB ISH`) | Total global sequential consistency across all threads. | Default fallback; avoid in hot paths. |

---

## 2. Lock-Free SPSC Ring Buffer (Single-Producer Single-Consumer)

The SPSC queue is the foundational primitive for high-frequency trading, audio engines, and inter-thread messaging. With cacheline-separated indices and `acquire`/`release` orderings, it achieves sub-10ns enqueue/dequeue latencies.

```cpp
#include <atomic>
#include <cstddef>
#include <new>

template <typename T, size_t Capacity>
class LockFreeSPSCQueue {
    static_assert((Capacity & (Capacity - 1)) == 0, "Capacity must be a power of 2");

public:
    LockFreeSPSCQueue() : head_(0), tail_(0), cached_tail_(0), cached_head_(0) {}

    // Producer thread: Push element to tail
    bool push(const T& item) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        
        // Fast path: Check against cached head to avoid cross-core atomic load
        if ((current_tail - cached_head_) >= Capacity) {
            cached_head_ = head_.load(std::memory_order_acquire);
            if ((current_tail - cached_head_) >= Capacity) {
                return false; // Queue is full
            }
        }

        buffer_[current_tail & BufferMask] = item;
        // Release ordering publishes item write to consumer
        tail_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    // Consumer thread: Pop element from head
    bool pop(T& item) {
        const size_t current_head = head_.load(std::memory_order_relaxed);

        // Fast path: Check against cached tail
        if (current_head == cached_tail_) {
            cached_tail_ = tail_.load(std::memory_order_acquire);
            if (current_head == cached_tail_) {
                return false; // Queue is empty
            }
        }

        item = buffer_[current_head & BufferMask];
        // Release ordering publishes head advancement to producer
        head_.store(current_head + 1, std::memory_order_release);
        return true;
    }

private:
    static constexpr size_t BufferMask = Capacity - 1;
    T buffer_[Capacity];

    // Align head and tail to independent 64-byte cache lines to eliminate false sharing
    alignas(64) std::atomic<size_t> tail_;
    size_t cached_head_; // Private to producer thread

    alignas(64) std::atomic<size_t> head_;
    size_t cached_tail_; // Private to consumer thread
};
```

---

## 3. Treiber Stack & Compare-And-Swap (CAS)

For Multi-Producer Multi-Consumer (MPMC) stacks, the Treiber Stack uses atomic `compare_exchange_weak` in a retry loop:

```cpp
#include <atomic>

template <typename T>
class TreiberStack {
    struct Node {
        T data;
        Node* next;
        Node(const T& val) : data(val), next(nullptr) {}
    };

    std::atomic<Node*> head_{nullptr};

public:
    void push(const T& item) {
        Node* new_node = new Node(item);
        // Load head relaxed; compare_exchange_weak applies release on success
        new_node->next = head_.load(std::memory_order_relaxed);
        while (!head_.compare_exchange_weak(
            new_node->next, new_node,
            std::memory_order_release,
            std::memory_order_relaxed)) {
            // Spin loop automatically updates new_node->next on failure
        }
    }

    bool pop(T& result) {
        Node* old_head = head_.load(std::memory_order_acquire);
        while (old_head && !head_.compare_exchange_weak(
            old_head, old_head->next,
            std::memory_order_acquire,
            std::memory_order_relaxed)) {
            // Spin loop updates old_head on failure
        }
        if (!old_head) return false;
        result = old_head->data;
        // Note: old_head memory reclamation requires Hazard Pointers or Epochs
        return true;
    }
};
```

---

## 4. The ABA Problem & Safe Memory Reclamation

### The ABA Hazard
In node-based lock-free structures, if Thread 1 reads node pointer `A`, but gets suspended, and Thread 2 pops `A`, frees `A`, pops `B`, and then allocates a new node that the allocator places at the **exact same memory address `A`**, Thread 1's CAS on address `A` will succeed even though the list state has mutated. This leads to severe memory corruption.

```
Initial State:      Top -> [A] -> [B] -> [C]
Thread 1 pauses:    Observes Top == A, Next == B
Thread 2 mutates:   Pops A, Pops B, re-pushes recycled A -> Top -> [A] -> [C]
Thread 1 resumes:   CAS(Top, A, B) succeeds! Top now points to freed node [B]!
```

### ABA Mitigation Strategies
1. **Tagged Pointers (Double-Word CAS)**:
   Pack a 64-bit sequence counter alongside the 64-bit pointer (`uint128_t`). Every modification increments the tag. Even if pointer address `A` is reused, `Tag` is different (`(A, 1) != (A, 2)`), causing the stale CAS to fail safely.
2. **Epoch-Based Reclamation (EBR)**:
   Threads register their active epoch (0, 1, or 2) when entering a critical section. Nodes are retired to a limbo list and physically freed only when all active threads have advanced past the retirement epoch.
3. **Hazard Pointers**:
   Each reader thread publishes a global atomic pointer to the node it is currently reading. Reclaiming threads check all active hazard pointers before freeing memory.

---

## 5. Spinloop Backoff & CPU Pause

When an atomic CAS or spinlock experiences contention, tight polling loops saturate the CPU instruction pipeline and burn power. High-performance spinloops employ hardware pause instructions:

```cpp
#if defined(__x86_64__) || defined(_M_X64)
    #include <immintrin.h>
    #define CPU_PAUSE() _mm_pause()
#elif defined(__aarch64__)
    #define CPU_PAUSE() __asm__ volatile("yield" ::: "memory")
#else
    #define CPU_PAUSE() ((void)0)
#endif

void spin_wait_with_backoff(std::atomic<bool>& lock) {
    int backoff = 1;
    while (lock.load(std::memory_order_relaxed)) {
        for (int i = 0; i < backoff; ++i) {
            CPU_PAUSE(); // Relieves CPU pipeline congestion and lowers power
        }
        if (backoff < 64) backoff <<= 1; // Exponential backoff
    }
}
```

---

## 6. Lock-Free Checklist

- [ ] Are atomic loads and stores annotated with minimal sufficient orderings (`acquire`/`release`/`relaxed` instead of default `seq_cst`)?
- [ ] Are producer and consumer atomic indices aligned to separate 64-byte boundaries (`alignas(64)`)?
- [ ] Are cached index copies used to prevent continuous cross-core cache invalidations?
- [ ] In node-based CAS algorithms, is ABA addressed via tagged pointers or Epoch-Based Reclamation?
- [ ] Do spinloops incorporate architecture-specific pause intrinsics (`_mm_pause` / `yield`) with exponential backoff?
