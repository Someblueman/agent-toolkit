# Concurrency, Context, and Goroutine Lifecycles

Read this for goroutine lifecycle guarantees, leak prevention, context propagation and cancellation, channel versus mutex selection, worker pools, bounded concurrency, and `errgroup`.

---

## 1. Goroutine Lifecycle & Leak Prevention

A goroutine is cheap (~2 KB initial stack), but an abandoned goroutine leaks memory, open file descriptors, mutex locks, and network sockets permanently for the life of the process.

### The Invariant of Goroutine Ownership

> **Every goroutine must have a deterministic creator, a known supervisor, and a guaranteed termination condition.**

### Common Leak Vectors & Prevention Rules

1. **Unbuffered Channel Send Without Receiver**: A goroutine sends to an unbuffered channel when the receiver has already exited or timed out.
   - *Fix*: Use a buffered channel of capacity 1 for single-result worker goroutines, or select on `<-ctx.Done()`.
2. **Unread Channel Receive on Forgotten Channel**: A worker goroutine waits forever for incoming work on a channel that is never closed.
   - *Fix*: Always close input channels from the producer side, or listen on `<-ctx.Done()`.
3. **Blocking Network / I/O Without Context / Deadlines**: Goroutines executing HTTP requests, database queries, or socket reads that lack timeouts will hang indefinitely on network partition.
   - *Fix*: Always use `http.NewRequestWithContext`, `db.QueryContext`, or set read/write socket deadlines.

---

## 2. Context Propagation & Cancellation

`context.Context` is the standard Go mechanism for carrying deadlines, cancellation signals, and trace data across API and goroutine boundaries.

### Context Rules of Engagement

1. **Always the First Parameter**: Name it `ctx context.Context` and place it as the very first parameter:
   ```go
   func FetchUser(ctx context.Context, id string) (*User, error)
   ```
2. **Never Store in a Struct**: Storing context inside a struct creates ambiguous lifecycles, race conditions, and disconnects method execution from caller lifecycles. (The only standard exception is `http.Request`).
3. **Always Invoke `defer cancel()`**: When deriving a context with `context.WithTimeout`, `context.WithDeadline`, or `context.WithCancel`, call the cancel function via `defer` immediately to release timer resources:
   ```go
   ctx, cancel := context.WithTimeout(parentCtx, 5*time.Second)
   defer cancel()
   ```
4. **Use `context.WithCancelCause` (Go 1.20+)**: When canceling due to a specific domain or network error, use `WithCancelCause` to preserve the causal error for inspection via `context.Cause(ctx)`.
5. **Never Pass `nil` Context**: Use `context.Background()` for root entrypoints and `context.TODO()` when context plumbing is temporarily underway.

---

## 3. Channels vs. Mutexes vs. Atomics

Choosing the right synchronization primitive is critical for simplicity and performance.

### Concurrency Primitives Decision Matrix

| Primitive | Primary Use Case | When to Choose | When to Avoid |
|---|---|---|---|
| **`sync.Mutex`** | State Protection | Guarding in-memory data structures, caches, counters, and internal struct invariants. | Long-running I/O or network calls while holding lock. |
| **`sync.RWMutex`** | Read-Heavy Invariants | Read-to-write ratio > 10:1 with fast read operations. | Write-heavy paths or very short reads where RWMutex overhead exceeds Mutex. |
| **`sync/atomic`** | Lock-Free State / Flags | Single primitive integers (e.g. `atomic.Int64`), booleans (`atomic.Bool`), or pointer swaps (`atomic.Pointer`). | Multi-field invariants requiring atomic coordination. |
| **Channels** | Ownership Transfer & Signaling | Transferring data ownership between goroutines, streaming pipelines, task queues, and stop/cancellation signals. | Simple shared in-memory state or cache protection. |
| **`errgroup.Group`** | Structured Concurrent Tasks | Running parallel subtasks where errors must be collected and cancellation propagated. | Long-lived background daemon loops. |

---

## 4. Structured Concurrency with `errgroup`

The `golang.org/x/sync/errgroup` package provides idiomatic structured concurrency: it coordinates parallel tasks, collects errors, bounds concurrency, and propagates context cancellation.

```go
package worker

import (
    "context"
    "fmt"
    "golang.org/x/sync/errgroup"
)

func ProcessItems(ctx context.Context, items []string, maxConcurrency int) error {
    g, ctx := errgroup.WithContext(ctx)
    if maxConcurrency > 0 {
        g.SetLimit(maxConcurrency) // Bounded concurrency limit
    }

    for _, item := range items {
        item := item // Safe loop capture
        g.Go(func() error {
            // Check context before heavy work
            if err := ctx.Err(); err != nil {
                return err
            }
            if err := process(ctx, item); err != nil {
                return fmt.Errorf("processing item %s: %w", item, err)
            }
            return nil
        })
    }

    if err := g.Wait(); err != nil {
        return fmt.Errorf("batch processing failed: %w", err)
    }
    return nil
}
```

---

## 5. Anti-Patterns vs Pragmatic Concurrency

| Anti-Pattern | Failure Mode | Pragmatic Solution |
|---|---|---|
| **Fire-and-Forget Goroutines** | `go func() { ... }()` without error handling or lifetime tracking leads to leaked resources and silent crashes. | Manage lifecycles via `sync.WaitGroup`, `errgroup.Group`, or worker pools. |
| **Holding Mutex Across I/O** | `mu.Lock()` held during HTTP call or database query serializes throughput and causes connection pool exhaustion. | Perform I/O outside critical sections; lock only during state updates. |
| **Channel Leak on Early Return** | Worker writes to unbuffered channel; caller returns early on timeout; worker goroutine blocks forever. | Use buffered channel with capacity 1 (`make(chan Result, 1)`) for single-result tasks. |
| **Context in Struct Field** | `type Service struct { ctx context.Context }` causes stale deadlines and cross-goroutine race conditions. | Pass `ctx` as the first argument to every method. |
| **Unbounded Goroutine Spawning** | Spawning a goroutine per incoming item (`for _, item := range 1M { go handle(item) }`) exhausts OS memory/FDs. | Use `errgroup.SetLimit(N)` or a fixed worker pool. |

---

## 6. Concrete Code Comparisons

### Goroutine Leak Prevention in Single-Result Operations

#### ❌ ANTI-PATTERN: Leaked Goroutine on Caller Timeout
```go
// BAD: If parentCtx times out before slowQuery finishes,
// the spawned goroutine blocks forever trying to send to ch.
func QueryAsync(ctx context.Context, query string) (*Result, error) {
    ch := make(chan *Result) // Unbuffered!

    go func() {
        res := slowQuery(query)
        ch <- res // Leaks goroutine if caller timed out and left select!
    }()

    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    case res := <-ch:
        return res, nil
    }
}
```

#### ✅ PRAGMATIC: Buffered Channel + Context-Aware Exit
```go
// GOOD: Buffered channel allows goroutine to send and exit without blocking,
// even if caller abandons the receive due to context cancellation.
func QueryAsync(ctx context.Context, query string) (*Result, error) {
    ch := make(chan *Result, 1) // Buffer size 1 guarantees send will not block

    go func() {
        // Alternatively, pass context into query if supported
        res := slowQuery(query)
        ch <- res
    }()

    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    case res := <-ch:
        return res, nil
    }
}
```

---

### Protecting Shared State: Mutex vs Atomic

#### ❌ ANTI-PATTERN: Heavy Mutex on Simple Counter
```go
// BAD: Mutex contention overhead on high-frequency increment
type MetricTracker struct {
    mu    sync.Mutex
    count int64
}

func (m *MetricTracker) Inc() {
    m.mu.Lock()
    m.count++
    m.mu.Unlock()
}
```

#### ✅ PRAGMATIC: Fast Lock-Free Atomic Primitive
```go
// GOOD: Native hardware atomic instruction, zero contention lock overhead
import "sync/atomic"

type MetricTracker struct {
    count atomic.Int64
}

func (m *MetricTracker) Inc() {
    m.count.Add(1)
}

func (m *MetricTracker) Value() int64 {
    return m.count.Load()
}
```

---

## 7. Fast-Path Concurrency Verification Recipes

```bash
# Run tests with the Go race detector enabled on targeted package
go test -race -v -run ^TestConcurrency ./internal/worker

# Stress-test a concurrent test for race conditions (100 iterations)
go test -race -count=100 -run ^TestWorkerPoolRace$ ./internal/worker

# Detect deadlocks or goroutine leaks during test execution
go test -timeout 10s -run ^TestDeadlockScenario$ ./internal/worker
```
