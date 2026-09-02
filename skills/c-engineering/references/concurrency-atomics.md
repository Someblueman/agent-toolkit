# Concurrency, C11 Atomics, Memory Ordering, and Thread Safety

Read this for POSIX threads (`pthreads`), C11 `<stdatomic.h>` primitives, memory ordering models, lock-free SPSC queues, and ThreadSanitizer data race detection. SIMD vectorization belongs in `performance-simd.md`; memory ownership in `memory-arenas.md`; sanitizer setup in `tooling-sanitizers-ci.md`.

---

## Concurrency Tool Selection

| Concurrency Pattern | Primary Primitive | Synchronization Mechanism | Use Case |
|---|---|---|---|
| **Mutual Exclusion** | `pthread_mutex_t` | OS lock / futex | Complex multi-step critical sections, shared state mutation |
| **Signaling & Waiting** | `pthread_cond_t` | Condition variable with predicate loop | Worker thread coordination, event notification |
| **Lock-Free Single Producer Single Consumer** | `atomic_size_t` with Acquire/Release | Memory ordering barriers | High-throughput telemetry, audio ring buffers, packet queues |
| **Atomic Counters / Flags** | `atomic_int`, `atomic_bool` | `memory_order_relaxed` or `memory_order_seq_cst` | Statistics counters, cancellation flags |

---

## POSIX Threads (`pthreads`) Discipline

### 1. Condition Variable Predicate Loop
A thread waking up from `pthread_cond_wait()` may experience a **spurious wakeup** (waking without a corresponding signal) or another thread may consume the state first. You must always wait in a `while` loop, never an `if` statement.

#### ❌ ANTI-PATTERN: `if` Check for Condition Variable
```c
// Anti-pattern: Vulnerable to spurious wakeup; proceeds even when queue is empty
pthread_mutex_lock(&queue->lock);
if (queue->count == 0) { // ❌ Bug: if spurious wakeup occurs, queue is still empty!
    pthread_cond_wait(&queue->not_empty, &queue->lock);
}
item_t item = queue->items[--queue->count]; // May read uninitialized memory!
pthread_mutex_unlock(&queue->lock);
```

#### ✅ PRAGMATIC: `while` Predicate Loop
```c
// Pragmatic: Re-checks condition after wakeup, completely immune to spurious wakeups
pthread_mutex_lock(&queue->lock);
while (queue->count == 0 && !queue->shutdown) {
    pthread_cond_wait(&queue->not_empty, &queue->lock);
}

if (queue->shutdown && queue->count == 0) {
    pthread_mutex_unlock(&queue->lock);
    return -1; // Graceful termination
}

item_t item = queue->items[--queue->count];
pthread_mutex_unlock(&queue->lock);
```

### 2. Strict Mutex Acquisition Order
To prevent deadlocks when acquiring multiple mutexes, establish and document a strict global lock hierarchy (e.g. acquire `lock_A` before `lock_B`).

---

## C11 Atomics (`<stdatomic.h>`) & Memory Ordering

C11 atomics provide hardware-supported atomic operations without heavyweight mutexes.

### Memory Ordering Reference

| Memory Order | Semantics | Typical Use Case |
|---|---|---|
| `memory_order_relaxed` | Atomic load/store/RMW with NO synchronization or ordering guarantees with other variables | Metrics counters, statistical IDs |
| `memory_order_acquire` | Prevents subsequent reads/writes from being reordered *before* this load | Reading published head/tail index, reading lock flag |
| `memory_order_release` | Prevents prior reads/writes from being reordered *after* this store | Writing published head/tail index, publishing initialized payload |
| `memory_order_acq_rel` | Combines both acquire and release semantics on Read-Modify-Write (RMW) operations | Reference count decrements, CAS loops |
| `memory_order_seq_cst` | Total globally consistent ordering across all threads | Default atomic operations where performance is not critical |

---

## Lock-Free SPSC Ring Buffer

A Single-Producer Single-Consumer (SPSC) queue uses `memory_order_release` when publishing items and `memory_order_acquire` when consuming items, avoiding all mutex overhead.

To prevent **false sharing** (cache thrashing when producer and consumer write to the same 64-byte cache line), pad the `head` and `tail` indices with `alignas(64)`.

### Lock-Free SPSC Implementation (`spsc_queue.h`)

```c
#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdalign.h>

#define CACHE_LINE_SIZE 64

typedef struct spsc_queue {
    // Shared immutable configuration
    void **buffer;
    size_t capacity; // Must be a power of two
    size_t mask;

    // Producer state (cache-line isolated)
    alignas(CACHE_LINE_SIZE) atomic_size_t tail; // Written by producer, read by consumer

    // Consumer state (cache-line isolated)
    alignas(CACHE_LINE_SIZE) atomic_size_t head; // Written by consumer, read by producer
} spsc_queue_t;

// Producer: Push item to queue
bool spsc_queue_push(spsc_queue_t *q, void *item) {
    size_t tail = atomic_load_explicit(&q->tail, memory_order_relaxed);
    size_t head = atomic_load_explicit(&q->head, memory_order_acquire);

    // Queue full check
    if ((tail - head) >= q->capacity) {
        return false;
    }

    // Write payload before publishing tail index
    q->buffer[tail & q->mask] = item;

    // Release ordering ensures item is written to memory before tail is visible to consumer
    atomic_store_explicit(&q->tail, tail + 1, memory_order_release);
    return true;
}

// Consumer: Pop item from queue
bool spsc_queue_pop(spsc_queue_t *q, void **out_item) {
    size_t head = atomic_load_explicit(&q->head, memory_order_relaxed);
    size_t tail = atomic_load_explicit(&q->tail, memory_order_acquire);

    // Queue empty check
    if (head == tail) {
        return false;
    }

    // Read payload before advancing head index
    *out_item = q->buffer[head & q->mask];

    // Release ordering signals producer that slot is now available
    atomic_store_explicit(&q->head, head + 1, memory_order_release);
    return true;
}
```

---

## Anti-Pattern Summary

| Anti-Pattern | Consequence | Pragmatic Replacement |
|---|---|---|
| `volatile bool flag;` for thread sync | Compiler/CPU reorders operations; data race | Use `atomic_bool` with explicit memory orderings |
| `pthread_cond_wait()` inside `if` | Spurious wakeup leads to invalid state | Always use `while (!condition)` predicate check |
| Adjacent atomic variables in struct without padding | False sharing; severe L1/L2 cache contention | `alignas(64)` between producer/consumer variables |
| `memory_order_seq_cst` everywhere | Unnecessary memory fence overhead on ARM/x86 | Use targeted `acquire`/`release` semantics |
| Holding mutex across long I/O or sleep | Severe thread starvation and latency spikes | Lock only critical state updates; perform I/O outside lock |

---

## Fast-Path Verification Recipes

Detect data races and synchronization bugs using ThreadSanitizer (TSan):

```bash
# Compile and run concurrent test with ThreadSanitizer
clang -std=c11 -fsanitize=thread -g -Wall -Wextra -Werror -pedantic -pthread \
  -Iinclude src/spsc_queue.c tests/test_spsc_queue.c -o /tmp/test_spsc && /tmp/test_spsc

# Run stress test under high thread contention
/tmp/test_spsc --threads=8 --iterations=1000000
```
