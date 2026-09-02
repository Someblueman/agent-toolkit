# Reliable Side Effects, Retries, and Concurrent State

Use this reference for operations whose effects escape the current call: writes, payments, emails, webhooks, queue acknowledgements, durable jobs, external commands, or updates shared with another request/process. The goal is an explicit outcome protocol, not simply more retries.

## 1. Classify the effect before retrying

For each operation, identify:

- what external state can change;
- whether repeating the same logical request is safe;
- the point after which success may have occurred even if the caller receives an error or timeout;
- who owns cancellation, retry, reconciliation, and the terminal record;
- the total attempt/deadline budget and which failures are transient.

Distinguish:

- **Read-only:** no externally visible mutation, though load and rate limits still matter.
- **Naturally idempotent:** repeating the same intended operation produces the same externally visible state.
- **Idempotent by protocol:** a stable operation key and durable result/deduplication record make repeats safe.
- **Non-idempotent:** repetition can duplicate or compound effects; do not retry automatically without a compensating or reconciliation design.

A timeout means the outcome is unknown, not that the effect failed. If the remote side may have committed, query/reconcile the outcome, reuse a supported idempotency key, or surface an explicit `unknown`/`pending_reconciliation` result instead of guessing.

Source: [HTTP idempotent methods and retry semantics](https://www.rfc-editor.org/rfc/rfc9110.html#name-idempotent-methods).

## 2. Place idempotency at the durable boundary

When the contract requires deduplication:

- derive or accept one stable logical-operation key; do not generate a new key on every retry;
- bind the key to the normalized operation parameters so accidental key reuse with different input fails;
- store the key and terminal result durably for the required replay window;
- make claiming the key and committing the local effect atomic when the storage system supports it;
- return or reconstruct the prior result for a completed duplicate;
- define behavior for an in-progress duplicate, expired key, failed attempt, and abandoned owner;
- keep deduplication scope explicit: process-local, single database, one service, or end-to-end.

An in-memory `Set` does not provide crash-safe or multi-instance idempotency. A queue's delivery mode alone does not prove an end-to-end exactly-once effect. State which boundary is transactional or deduplicated and which duplicates remain possible.

For a database plus an external publisher, consider a repository-established outbox/inbox or reconciliation pattern when a transaction cannot cover both systems. Do not introduce that machinery unless the actual failure window requires it.

## 3. Make retries bounded and selective

- Retry only classified transient failures. Validation, authorization, invariant, and permanent protocol failures should fail immediately.
- Honor the caller's cancellation signal and one total deadline across attempts and backoff.
- Cap attempts, elapsed time, queued retries, and concurrency. Persist retry state when it must survive process exit.
- Use backoff with jitter when synchronized callers could create a retry storm; honor an authoritative server retry hint within the caller's deadline and policy.
- Avoid multiplying retries across layers. Choose one owner or ensure nested budgets compose within the total limit.
- Preserve the final cause plus attempt metadata without logging secrets or duplicating the same error at every layer.
- Send exhausted durable work to an explicit terminal/dead-letter state with enough provenance to inspect and replay safely.

Do not retry a transaction closure blindly unless it can be re-executed safely. A callback may have changed process-local state or invoked an external system before the database asks for a retry.

## 4. Prevent lost updates and ordering bugs

JavaScript's single event loop does not make multi-step async operations atomic. An `await` allows another task to observe or change shared state between a read and write.

- Prefer one atomic storage statement, uniqueness constraint, compare-and-swap/version predicate, or transaction over a read-check-write sequence.
- Check affected-row counts or returned versions so an optimistic-concurrency conflict is observable.
- Choose an isolation level from the invariant and database behavior; do not assume `transaction` means serial execution.
- Keep transactions short and avoid holding locks while awaiting unrelated network calls.
- Define whether messages may be duplicated, delayed, or reordered. Carry a sequence/version when ordering matters and specify how gaps or stale updates behave.
- Make ownership transitions and leases conditional on the expected owner/version. Use a time source and expiry policy appropriate to the coordination contract.
- Do not use a process-local mutex to claim safety across worker processes, hosts, or independent services.

Source: [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html).

## 5. Test failure windows, not only happy retries

Use controlled fakes or a faithful local adapter to place failure at each meaningful boundary:

- before sending, while sending, after the remote commit but before the response, and after receiving the response;
- two concurrent attempts with the same idempotency key and with different parameters under one key;
- process crash/restart after claiming work and after committing the effect;
- duplicate, delayed, stale, and reordered messages;
- optimistic-concurrency conflict, transaction retry, deadlock/serialization failure, and uniqueness conflict where the adapter exposes them;
- cancellation during the attempt and during backoff;
- retry exhaustion and replay from the terminal/dead-letter state.

Assert durable and externally observable outcomes: how many effects occurred, which result was recorded, whether work remains owned or retryable, and whether a later reconciliation can determine the truth. A test that only checks the returned promise can miss the duplicate or orphaned effect.
