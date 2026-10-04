# Concurrency, Context, and Goroutine Lifecycles

Read this for goroutine lifecycle guarantees, leak prevention and detection, context propagation and cancellation, channel versus mutex selection, worker pools, bounded concurrency, `errgroup`, and testing concurrent code with `testing/synctest`.

---

## 1. Goroutine Lifecycle & Leak Prevention

A goroutine starts with a small stack and is cheap to create, but a goroutine that never exits keeps its stack and everything it references alive, along with any file descriptors, sockets or locks it holds, for the life of the process.

### The Invariant of Goroutine Ownership

> **Make it clear when, or whether, every goroutine exits.** Each goroutine has an owner that starts it, can stop it, and waits for it.

### Common Leak Vectors & Prevention Rules

1. **Send with no receiver**: A goroutine sends on an unbuffered channel after the receiver has returned (for example on timeout).
   - *Fix*: Give single-result channels a buffer of 1, or select on `<-ctx.Done()` alongside the send.
2. **Receive on a channel nobody closes**: A worker ranges over an input channel the producer never closes.
   - *Fix*: The producer closes the channel when done; workers also select on `<-ctx.Done()`.
3. **Blocking I/O without cancellation**: Requests, queries or socket reads without a context or deadline hang indefinitely on a network partition.
   - *Fix*: Use context-aware APIs (`http.NewRequestWithContext`, `db.QueryContext`) or deadlines (`net.Conn.SetDeadline`). A plain `select` on `ctx.Done()` cannot interrupt a blocked read.

### Detecting Leaks

- **Tests**: Run time- and goroutine-dependent tests inside `synctest.Test` (Go 1.25+, section 6). It waits for every goroutine started in the bubble to exit and fails the test if they deadlock. Outside a bubble, `go.uber.org/goleak` checks for unexpected goroutines at test end.
- **Running programs**: The `goroutineleak` profile (Go 1.27; experimental in 1.26 behind `GOEXPERIMENT=goroutineleakprofile`) reports goroutines blocked forever on unreachable concurrency primitives, and is served at `/debug/pprof/goroutineleak`. Before 1.27, compare goroutine counts and stacks over time with `/debug/pprof/goroutine?debug=2`.

---

## 2. Context Propagation & Cancellation

`context.Context` carries deadlines, cancellation signals and request-scoped values across API and goroutine boundaries.

### Context Rules of Engagement

1. **First parameter**: Name it `ctx` and put it first:
   ```go
   func FetchUser(ctx context.Context, id string) (*User, error)
   ```
2. **Don't store it in a struct**: A stored context obscures which call its deadline and cancellation apply to and stops callers from setting them per call. Pass it to each method instead. The Go blog's one sanctioned exception is keeping an existing API backward compatible, as `http.Request` does (<https://go.dev/blog/context-and-structs>).
3. **`defer cancel()` immediately**: After `context.WithCancel`, `WithTimeout` or `WithDeadline`, defer the cancel function at once; forgetting it leaks the child context until the parent is canceled. `go vet`'s `lostcancel` check catches many misses.
   ```go
   ctx, cancel := context.WithTimeout(parentCtx, 5*time.Second)
   defer cancel()
   ```
4. **Record why**: `context.WithCancelCause` (1.20) and `WithTimeoutCause`/`WithDeadlineCause` (1.21) attach an error retrievable with `context.Cause(ctx)`.
5. **Other helpers (1.21+)**: `context.WithoutCancel` keeps values but detaches cancellation (for work that must outlive the request, such as an audit write); `context.AfterFunc` runs a function when a context is done. `signal.NotifyContext` turns SIGINT/SIGTERM into cancellation for a command's root context.
6. **Never pass `nil`**: Use `context.Background()` at the root (`main`, tests on Go < 1.24) and `context.TODO()` while plumbing is incomplete. In tests on Go 1.24+, use `t.Context()`.

---

## 3. Channels vs. Mutexes vs. Atomics

### Concurrency Primitives Decision Matrix

| Primitive | Primary Use Case | When to Choose | Cautions |
|---|---|---|---|
| **`sync.Mutex`** | Protecting shared state | Caches, maps, counters, multi-field invariants. | Don't hold it across I/O or other blocking calls. Don't copy a struct containing one (`go vet` `copylocks`). |
| **`sync.RWMutex`** | Read-mostly state | Reads dominate and profiling shows contention on a plain `Mutex`. | Costs more than `Mutex` per operation. A waiting `Lock` blocks new `RLock` calls, so never read-lock recursively. |
| **`sync/atomic` types** | Single independent values | Counters, flags, pointer swaps (`atomic.Int64`, `atomic.Bool`, `atomic.Pointer[T]`). | Invariants spanning several fields need a mutex. Contended atomics still contend on the cache line. |
| **Channels** | Ownership transfer & signaling | Handing data between goroutines, pipelines, work queues, done signals. | Overkill for protecting a shared map; decide who closes each channel. |
| **`sync.WaitGroup`** | Waiting for goroutines that don't return errors | Fan-out where each goroutine handles its own failures. Go 1.25+: `wg.Go(f)`. | Call `Add` before starting the goroutine (`wg.Go` does this for you). |
| **`errgroup.Group`** | Concurrent subtasks with errors | Parallel work where the first error should cancel the rest. | The context from `errgroup.WithContext` is canceled when `Wait` returns; don't use it afterwards. |

---

## 4. Structured Concurrency with `errgroup`

`golang.org/x/sync/errgroup` runs subtasks, returns the first error, bounds concurrency with `SetLimit`, and cancels its derived context on the first error.

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
        g.SetLimit(maxConcurrency) // Go blocks until a slot is free
    }

    for _, item := range items { // per-iteration item since go 1.22; no copy needed
        g.Go(func() error {
            if err := ctx.Err(); err != nil {
                return err // another task failed; skip remaining work
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

For goroutines that don't return errors, Go 1.25's `sync.WaitGroup.Go` removes the `Add`/`Done` bookkeeping:

```go
var wg sync.WaitGroup
for _, s := range shards {
    wg.Go(func() { s.Flush() })
}
wg.Wait()
```

---

## 5. Anti-Patterns vs Pragmatic Concurrency

| Anti-Pattern | Failure Mode | Pragmatic Solution |
|---|---|---|
| **Fire-and-forget goroutines** | `go func() { ... }()` with no owner: errors vanish, shutdown can't wait for it, leaks go unnoticed. | Own it with `errgroup`, `sync.WaitGroup`, or a worker pool with a stop signal. |
| **Holding a mutex across I/O** | Serializes throughput and stalls every other user of the lock behind the slowest request. | Copy what you need under the lock, release it, then do the I/O. |
| **Channel leak on early return** | The worker blocks forever sending a result nobody will receive. | Buffer single-result channels (`make(chan Result, 1)`) or select on `ctx.Done()`. |
| **Context in a struct field** | Deadlines and cancellation no longer belong to a specific call. | Pass `ctx` as the first argument to each method. |
| **Unbounded goroutine spawning** | One goroutine per item for a million items exhausts memory or file descriptors. | `errgroup.SetLimit(n)` or a fixed worker pool. |
| **`time.Sleep` in tests to "let goroutines run"** | Slow and flaky. | `synctest.Test` with `synctest.Wait`, or explicit synchronization. |

---

## 6. Concrete Code Comparisons

### Goroutine Leak Prevention in Single-Result Operations

#### ❌ ANTI-PATTERN: Leaked Goroutine on Caller Timeout
```go
// BAD: if ctx is done before slowQuery returns, the goroutine blocks forever on the send.
func QueryAsync(ctx context.Context, query string) (*Result, error) {
    ch := make(chan *Result) // unbuffered

    go func() {
        ch <- slowQuery(query) // nobody receives after the caller returns
    }()

    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    case res := <-ch:
        return res, nil
    }
}
```

#### ✅ PRAGMATIC: Buffered Channel + Context-Aware Work
```go
// GOOD: the buffer lets the goroutine finish its send and exit even if the caller left.
// Passing ctx lets slowQuery stop early instead of running to completion unobserved.
func QueryAsync(ctx context.Context, query string) (*Result, error) {
    ch := make(chan *Result, 1)

    go func() {
        ch <- slowQuery(ctx, query)
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

### Shared Counter: Mutex or Atomic

Both are correct. For a single independent counter, the atomic type is simpler and avoids a lock; switch to a mutex once the counter must change together with other fields.

```go
// Mutex: correct, and the right choice when several fields change together.
type Stats struct {
    mu       sync.Mutex
    requests int64
    bytes    int64
}

func (s *Stats) Record(n int64) {
    s.mu.Lock()
    defer s.mu.Unlock()
    s.requests++
    s.bytes += n
}

// Atomic: simpler for one independent value.
type Counter struct {
    n atomic.Int64
}

func (c *Counter) Inc()         { c.n.Add(1) }
func (c *Counter) Value() int64 { return c.n.Load() }
```

---

### Testing Time-Dependent Code with `testing/synctest` (Go 1.25+)

Inside `synctest.Test`, goroutines run in a bubble with a fake clock. Time advances only when every goroutine in the bubble is durably blocked, so `time.Sleep(time.Minute)` returns instantly and deterministically. Durably blocking operations are: sends and receives on channels created inside the bubble, a `select` whose cases all use such channels, `sync.Cond.Wait`, `sync.WaitGroup.Wait` when `Add` was called inside the bubble, and `time.Sleep`. Channels and WaitGroups created outside the bubble, `sync.Mutex`/`RWMutex` locking, I/O and syscalls are not; create concurrency primitives inside the bubble and use in-memory fakes for I/O (on Go 1.27, `httptest.NewTestServer` provides an in-memory network for HTTP).

```go
func TestCacheExpiry(t *testing.T) {
    synctest.Test(t, func(t *testing.T) {
        c := NewCache(time.Minute) // starts a background expiry goroutine
        defer c.Close()
        c.Put("k", "v")

        time.Sleep(time.Minute + time.Second) // fake clock: returns immediately
        synctest.Wait()                       // let the expiry goroutine finish its work

        if _, ok := c.Get("k"); ok {
            t.Fatal("entry did not expire")
        }
    })
}
```

---

## 7. Concurrency Verification Recipes

```bash
# Targeted test with the race detector
go test -race -run '^TestConcurrency' ./internal/worker

# Stress a racy test (bypasses the cache because -count > 1)
go test -race -count=100 -run '^TestWorkerPoolRace$' ./internal/worker

# Fail fast with a full goroutine dump if a test hangs (does not detect leaks by itself)
go test -timeout 30s -run '^TestDeadlockScenario$' ./internal/worker

# Vet checks relevant to concurrency (copylocks, lostcancel, waitgroup/waitgroupgo) run by default
go vet ./internal/worker
```
