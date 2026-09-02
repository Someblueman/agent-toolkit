# Concurrency and Async

Read this before changing Tokio or other async code, threads, channels, synchronization, atomics, cancellation, or Rayon. Choose from workload semantics first; concurrency is not automatically a performance improvement.

## Choose the execution model

| Work | Typical starting point |
|---|---|
| Mostly waiting on many independent I/O operations, with timeouts or multiplexing | Async runtime already used by the project |
| CPU data parallelism over a collection or divide-and-conquer work | Rayon |
| Small fixed set of blocking or long-lived workers | `std::thread` |
| Short-lived blocking call from async code | Runtime blocking facility such as `spawn_blocking` |

- Do not introduce async solely on an assumed speedup. It is primarily a concurrency and composition model; compare complexity, latency, throughput, cancellation, and operational needs.
- Tiny CPU work can run inline. Significant CPU work should leave executor workers for a bounded CPU pool such as Rayon or a deliberately sized worker pool.
- Long-lived blocking loops belong on dedicated threads. Tokio documents `spawn_blocking` for blocking operations that eventually finish; once started they generally cannot be aborted, and their queue does not provide backpressure. See [`spawn_blocking`](https://docs.rs/tokio/latest/tokio/task/fn.spawn_blocking.html).
- Tokio's blocking-thread limit is configurable and large by default. Bound CPU concurrency explicitly rather than treating that limit as a CPU-executor size.
- If async code sends CPU work to another pool, return results through an async-aware channel and propagate worker panic or cancellation deliberately.

## Keep executor workers cooperative

Async tasks make progress when they return `Pending` and yield control. Avoid long synchronous regions on executor threads; use measurement and the service's latency objectives rather than a universal microsecond threshold.

Common hidden blocking operations include synchronous DNS or clients, filesystem calls, contended blocking locks, compression, large serialization, and output to a slow pipe. Route only work significant enough to affect scheduling; offloading tiny operations can cost more than running them.

Tokio has a cooperative budget and exposes `consume_budget` and `yield_now`, but its internal budget value is not an application contract. Prefer chunking pure-compute loops, offloading CPU work, or using a stream that naturally yields.

For `!Send` futures, use the runtime's local-task mechanism such as Tokio `LocalSet` when single-thread confinement is intentional. Do not route around `Send` errors without understanding which value lives across `.await`.

## Locks and state ownership

- A standard or `parking_lot` mutex is often appropriate for data protected by a short critical section that never crosses `.await`. An async mutex is appropriate when acquiring must not block a worker or when the guard intentionally spans async I/O; it is more expensive, its fairness semantics may matter, and holding it across slow I/O serializes other users. See [Tokio's mutex guidance](https://docs.rs/tokio/latest/tokio/sync/struct.Mutex.html#which-kind-of-mutex-should-you-use).
- Scope blocking guards in a non-async helper or explicit block so they are dropped before `.await`. A future can otherwise become `!Send` or deadlock even when local execution compiles.
- If contention or ownership complexity dominates, consider one task owning the resource with request messages and reply channels, or shard the state. Switching mutex types alone does not remove contention.
- Wrap shared state in a type with small operations rather than exposing the lock. This constrains guard lifetime and keeps invariants local.
- Do not hold a `RefCell` borrow across `.await`; another task on the same thread can re-enter and trigger a runtime borrow panic.

## Channels and backpressure

Choose a channel from its semantics, not a blanket crate preference:

| Need | Shape |
|---|---|
| Multiple producers, one async consumer | bounded `mpsc` |
| One result or acknowledgement | `oneshot` |
| Latest state such as configuration or status | `watch` |
| Fan-out events where lag policy is explicit | `broadcast` or subscriber-specific queues |
| Synchronous multi-producer/multi-consumer or selection | a maintained channel crate matching project needs |

- Bounded queues make overload observable and allow backpressure, shedding, or timeouts. Derive capacity from burst tolerance, memory bounds, and latency goals; “small” is not universally correct.
- An unbounded channel is acceptable only when growth is bounded elsewhere or dropping/blocking at that call site is impossible and the memory consequence is explicit.
- Treat a full queue, send timeout, or lagged receiver as a designed state. Decide whether to wait, reject, coalesce, drop oldest, or disconnect.
- Bound spawned task counts and in-flight stream work as well as queues. Acquiring a semaphore permit before spawning is one common pattern.
- Use documented sync/async bridges such as Tokio `blocking_send` and `blocking_recv`; avoid nesting a runtime with ad hoc `block_on` calls.

## `Send`, `Sync`, and task lifetime

- `Send` permits moving a value across threads. `Sync` means shared references can cross threads (`T: Sync` implies `&T: Send`). They are auto traits derived from fields unless explicitly implemented or negated.
- Common non-thread-safe signals are `Rc`, `Cell`, and `RefCell`; raw pointers also require explicit reasoning. `Arc<T>` crosses threads only when the contained type satisfies the needed bounds.
- For a spawned future, the compiler cares which values remain live across `.await`. Shorten the lifetime of guards, borrows, and `Rc` values rather than cloning or wrapping them blindly.
- `unsafe impl Send` or `Sync` is a soundness proof. Document why every reachable operation remains safe under the promised cross-thread use and test the concurrency protocol.
- Dropping a Tokio `JoinHandle` detaches the task; it does not cancel it. Track, abort, or join tasks according to the shutdown contract. Do not leave detached work accidental.

## Atomics

Use atomics for a small, documented lock-free protocol, not as a reflexive mutex replacement.

- `Relaxed` supplies atomicity without ordering other memory and often fits independent metrics.
- Release/acquire can publish and observe associated state when the acquire operation reads from the relevant release sequence.
- `SeqCst` adds a single global order for sequentially consistent operations. It can simplify a correct design but cannot repair a protocol whose required happens-before relationships are unknown.
- State the ordering argument next to non-trivial atomics. Consider a mutex when the proof is harder than the measured benefit warrants.
- Model small concurrent state machines with Loom when feasible and test on real supported targets. Model checking explores the abstraction supplied; it does not validate unmodeled FFI or platform behavior.

## Cancellation and `select!`

Dropping a future at an `.await` abandons that execution. Cancellation safety usually concerns data and progress; in an unsafe abstraction, cancellation and `Drop` behavior can also be part of the soundness invariant.

- Check the current operation's documentation before placing it directly in a `select!` loop. Some queue acquisitions lose their place; partial read/write helpers can lose progress; many receive operations are designed to be cancel-safe.
- `select!` drops losing branch futures. To resume one operation across iterations, create and pin it outside the loop, then poll `&mut` that future until completion.
- Default branch order may be randomized for fairness. `biased;` gives polling priority but can starve later always-ready branches; order shutdown and data branches deliberately.
- Test paths that reach `Pending`, cancellation between partial operations, closed channels, lag, and shutdown races. Always-ready unit futures cannot expose these bugs.
- Do not leave an invalid intermediate mutation live across a cancellation point. Make the intermediate state valid, commit after the awaited work, add synchronous rollback, or move the indivisible operation into an owned task.
- Prefer explicit `async fn shutdown(self)` or a supervisor that signals and joins tasks. `Drop` is synchronous; do not block on async cleanup or assume a runtime is available for fire-and-forget cleanup.
- When shutdown must be time-bounded, define the escalation: signal, await owned tasks to a deadline, then abort cancellable tasks or report/escalate. Started `spawn_blocking` work needs its own cooperative stop mechanism because aborting its handle generally does not stop it.

## Threads and Rayon

- Use `std::thread::scope` for fork-join work that safely borrows stack data. Join or propagate panics according to the caller's contract.
- In Rayon, begin with `par_iter` or `join`, then use scoped tasks or a custom pool only when isolation or pool sizing is required.
- Parallelize chunks large enough to amortize scheduling. Find the cutoff by measurement; fixed element counts do not transfer across workloads.
- Use per-worker `fold` plus `reduce` for accumulators rather than locking a shared collection inside the hot loop.
- Avoid nesting pools or calling async `block_on` inside Rayon without an explicit architecture; both can deadlock or oversubscribe resources.

## Review checklist

1. What bounds queue size, spawned tasks, CPU parallelism, and shutdown time?
2. Which operations can block, and are they significant on the target workload?
3. Does any guard, borrow, or `!Send` value live across `.await`?
4. What happens if a future is cancelled at each await point?
5. Who owns long-lived tasks, and how are errors and panics observed?
6. Are atomic orderings justified by a written happens-before argument?
7. Have pending, overload, closure, cancellation, and shutdown paths been tested?
