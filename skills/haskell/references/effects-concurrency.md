# Effects, Exceptions, Resources, and Concurrency

Use this page for `IO`, resource scopes, asynchronous exceptions, worker lifecycles, STM, queues, and streaming systems.

## Effects and Failures

- Keep predictable domain failures typed when callers can make a useful decision from them.
- Use exceptions for `IO` failures, cancellation, and exceptional conditions. Catch the narrowest useful exception type.
- Catch `SomeException` for cleanup or logging only inside a clear `bracket`/mask-based ownership model. Preserve cancellation, complete bounded cleanup, and rethrow unless the abstraction explicitly owns the exception.
- A pure expression may throw only when evaluated. Place `evaluate` or `force` inside the intended exception/resource scope when timing matters.
- Document blocking, resource acquisition, threads created, exceptions thrown, and cancellation behavior at public boundaries.

## Resource Safety and Asynchronous Exceptions

- Prefer `bracket`, `bracketOnError`, `finally`, `onException`, and project `with...` APIs to hand-written acquire/use/release sequences.
- Keep acquisition and release in the same lexical abstraction. Do not let lazy results escape after their underlying handle is closed. If post-scope use assumes NF, review the `NFData` instance and force exactly the required observations before release.
- Use `mask` only to protect the state transition that would otherwise leak or corrupt a resource, and use `restore` around the interruptible body.
- Masked code, including a `bracket` release action, can still receive asynchronous exceptions at interruptible operations. Make release short and non-blocking, or define a retryable/idempotent partial-cleanup state or separately managed cleanup path.
- Avoid `uninterruptibleMask` except for a tiny operation proven not to block; a blocking operation there can make a thread unresponsive or unkillable.
- Test synchronous failure during acquisition/use/release and cancellation at the vulnerable transitions.

## Structured Concurrency

- Tie child lifetime to a lexical scope using established combinators such as `withAsync`, `concurrently`, races, or the project's structured-concurrency abstraction.
- Always observe child failure. Do not leave exceptions hidden in abandoned handles.
- Define what happens to siblings when one child succeeds, fails, or is cancelled.
- Bound fan-out, queues, retries, and outstanding work. “Concurrent” without a bound is a resource policy bug waiting to happen.
- Make shutdown order explicit: stop intake, signal/cancel workers, drain or discard according to contract, wait for termination, then release shared resources.
- Give shutdown a deadline and a stuck-worker policy. Distinguish cooperative stop from asynchronous cancellation; account for foreign calls and blocking cleanup, and specify whether the safe fallback is quarantine/leak, degraded continuation, or process termination.
- Prefer higher-level concurrency combinators to manual `forkIO` plus bespoke bookkeeping.

## STM and Shared State

- Use STM for composable updates to in-memory transactional state. Keep external `IO` and irreversible side effects outside transactions because transactions may retry.
- `retry` blocks until a transactional variable read by the transaction changes. Confirm that the read set represents the intended wake-up condition.
- `orElse` gives the left transaction priority unless it retries; review starvation and the union of wake-up dependencies.
- Maintain cross-variable invariants in one transaction. Do not split a logically atomic transition around ordinary `IO`.
- Use bounded queues such as `TBQueue` when backpressure is part of correctness.
- Choose `MVar` for ownership/rendezvous patterns and `TVar`/STM for composable state transitions; do not mix them without a clear ordering protocol.
- Keep transactions short and bounded in pure work, which limits conflicts and retries. Test that the read set wakes on exactly the intended `TVar`s and that a frequently available left `orElse` branch cannot starve required work.

## Streaming and Lazy I/O

- Prefer explicit, bracketed streaming APIs for files, sockets, databases, and large producer/consumer pipelines.
- Do not return lazy data that still depends on a resource whose lifetime has ended.
- Specify chunking, size limits, backpressure, early termination, and cleanup on parse failure or cancellation.
- If using lazy `IO`, keep consumption visibly inside the owning resource scope and force enough of the result before release.

## Concurrent Test Obligations

- Exercise success, child failure, parent cancellation, blocked operations, full/empty queues, shutdown, and timeout paths.
- Assert final invariants and thread/resource termination, not only returned values.
- Use deterministic coordination primitives for tests; timing sleeps are weak evidence and often flaky.
- Run repeated or schedule-perturbed tests for races, while recognizing that passing stress tests do not prove race freedom.
- Distinguish a timeout used as a test guard from a specified production deadline.
