# Async, Concurrency, and Resource Lifetimes

Use this reference for promises, cancellation, streams, event emitters, timers, subprocesses, workers, backpressure, and event-loop behavior. The ownership, bounding, cancellation, and cleanup invariants apply across runtimes; the concrete Node APIs and sources below apply only when Node executes the code. For browsers, Deno, Bun, edge workers, or another runtime, verify the equivalent platform API and lifecycle against the pinned version rather than importing Node assumptions.

## 1. Choose the execution model

| Work | Use | Avoid |
|---|---|---|
| Ordinary network/file/database I/O | Native async API | Worker thread merely to wait on I/O |
| Independent small bounded batch | Deliberate `Promise.all` | Sequential waits with no dependency |
| Large or input-controlled batch | Concurrency limiter/worker queue | Creating every promise before applying the limit |
| Large byte/object flow | Stream or async iterator with backpressure | Buffering the entire input/output |
| Substantial CPU-bound JavaScript | Bounded worker pool | One worker per item/request |
| External executable | `spawn`/`execFile` with argv and lifecycle ownership | Shell interpolation or detached child without cleanup |

`async` does not move CPU work off the event loop. Code runs synchronously until it reaches an actual asynchronous boundary, and the continuation runs on the event loop again.

Sources: [Node: do not block the event loop](https://nodejs.org/en/learn/asynchronous-work/dont-block-the-event-loop), [worker threads](https://nodejs.org/api/worker_threads.html), [child processes](https://nodejs.org/api/child_process.html).

## 2. Promise ownership

- Every promise is awaited, returned, or deliberately detached.
- Deliberate detachment uses an explicit `void` and attaches a rejection handler immediately. It also needs an owner that can observe completion and decide shutdown behavior.
- Never pass an `async` executor to `new Promise`; the constructor does not assimilate exceptions from that executor in the way authors usually expect. Wrap only callback APIs, and settle exactly once.
- `array.forEach(async item => ...)` discards callback promises. Use `for...of` for sequential work or create a bounded parallel batch.
- Start work only when its concurrency slot is available. Limiting after `items.map(doWork)` is too late because the promises have already started.
- Validate a configurable concurrency limit as a finite positive integer and cap it to a justified maximum. Defaults such as 16 or 32 are starting hypotheses, not universal optima.
- `Promise.all` is fail-fast but does not cancel siblings. Use cancellation/cleanup for partial failure. Use `allSettled` only when every result must be observed and that behavior is intentional.
- Do not catch merely to return a sentinel that makes failure indistinguishable from a real value. Model partial success explicitly.

## 3. Cancellation and deadlines

Use `AbortSignal` as the common cancellation channel when supported:

- accept a caller-owned signal for externally controlled or long-running work;
- propagate it through every supporting I/O layer;
- check before irreversible work and at appropriate boundaries in long loops;
- remove abort listeners and release resources on every exit path;
- preserve or normalize the abort reason according to the public error contract.

A `Promise.race([operation, timeout])` only stops waiting. The operation continues unless the timeout aborts it or the API has another cancellation mechanism. This can leak sockets, subprocesses, writes, or work into the next test/request.

Prefer one deadline budget propagated downward over unrelated per-layer timeouts that can multiply total latency. When retrying, honor cancellation during both the attempt and backoff, cap attempts and elapsed time, and distinguish retryable from permanent failures.

Sources: [AbortController](https://nodejs.org/api/globals.html#class-abortcontroller), [timers with AbortSignal](https://nodejs.org/api/timers.html#cancelling-timers), [Node streams](https://nodejs.org/api/stream.html).

## 4. Structured resource lifetimes

The code that acquires a resource owns its release unless ownership is explicitly transferred.

- Use `try/finally` or a runtime-supported disposal construct for files, sockets, streams, temporary directories, database transactions, subprocesses, workers, timers, and event listeners.
- Make `close`/`dispose` idempotent when multiple failure paths may invoke it.
- Preserve the primary failure when cleanup also fails; report cleanup failure as context rather than replacing the original blindly.
- Long-lived background components expose a ready state, failure channel, cancellation/shutdown method, and completion promise. Construction must not hide an unobservable failing task.
- Do not let timers/listeners retain request-scoped data beyond the request. Clean them up when the operation settles.

When an API uses EventEmitter or streams, read its exact error contract. An emitted `'error'`, callback error, synchronous throw, and rejected promise are different channels; a type signature alone does not unify them.

Sources: [Node errors](https://nodejs.org/api/errors.html), [events](https://nodejs.org/api/events.html), [streams](https://nodejs.org/api/stream.html).

## 5. Streams and backpressure

- Prefer pipeline composition for multi-stage streams so completion and errors are observed together.
- When manually writing, stop when `writable.write()` returns `false` and resume on `'drain'`.
- Bound transforms and queues; a stream wrapper does not guarantee bounded memory if a stage accumulates all chunks.
- Decide object mode versus byte mode intentionally; their high-water marks have different units.
- Make partial-output semantics explicit. Cancellation or downstream failure may leave an external destination partially written; use temp-and-rename or transactions when atomicity matters.
- Avoid mixing event, callback, async-iterator, and promise consumption styles on the same stream unless the API explicitly supports it.

Source: [Node stream API and backpressure](https://nodejs.org/api/stream.html).

## 6. Event-loop and worker discipline

Treat latency-sensitive event-loop callbacks as bounded work whose complexity is known as a function of input size.

- Avoid synchronous filesystem, crypto, compression, child-process, and large JSON operations in request/task hot paths.
- Bound regex and parsing work on untrusted input; vulnerable complexity is a denial-of-service risk.
- Batch or yield long CPU loops only if that meets the latency goal; move substantial parallel CPU work to a worker pool.
- Pool workers. Creating a worker per task often costs more than the task and can exhaust memory/threads.
- Transfer large `ArrayBuffer`s when ownership can move; copying large messages can dominate the computation. Share mutable memory only with a deliberate synchronization design.
- Do not use workers for ordinary asynchronous I/O; Node explicitly documents them as a CPU tool.

Sources: [worker threads](https://nodejs.org/api/worker_threads.html), [event-loop guidance](https://nodejs.org/en/learn/asynchronous-work/dont-block-the-event-loop).

## 7. Async tests

- Return or await the promise under test. An assertion inside an unobserved promise cannot fail the test reliably.
- Await nested subtests; Node's test runner cancels unfinished children when the parent completes.
- Test abort before start, abort in flight, timeout, sibling failure, cleanup failure, double close, and late events where the contract exposes them.
- Use deterministic fake clocks only through the repository's supported mechanism; restore them in cleanup.
- Assert resource outcomes, not only return values: no live child, listener, timer, lock, temp file, or queued task remains.

Source: [Node test runner](https://nodejs.org/api/test.html).
