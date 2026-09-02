---
name: typescript-engineering
description: Engineer TypeScript or TSX code and configuration. Use for .ts/.tsx, runtime type boundaries, async behavior, modules, tests, or measured performance; not visual design or framework-specific UI behavior.
---

# TypeScript Engineering

## 1. Establish the executable contract

Before changing code, inspect the repository instructions and the smallest set of files that define how the code actually runs:

- package manager and lockfile;
- `package.json` scripts, `type`, `exports`, `imports`, `engines`, and dependencies;
- the active `tsconfig` chain, project references, and include/exclude boundaries;
- runtime and module loader (Node, browser/bundler, another runtime, or library consumers);
- formatter, linter, test runner, build tool, and generated-code ownership.

Use the repository's pinned versions and canonical commands. Do not replace its toolchain, module system, test runner, formatter, or established conventions as an incidental cleanup. Keep type-checking, linting, tests, build/emit, and the real runtime entry point distinct: one green gate does not imply the others.

This skill owns TypeScript language, API, runtime-boundary, project-configuration, async-lifecycle, and measured-performance decisions. For UI, browser-framework, game-engine, or other platform-specific behavior, also consult that framework or platform's repository guidance and documentation. Apply Node-specific APIs only when Node executes the code; do not transfer Node assumptions to browsers, Deno, Bun, edge workers, or another runtime by analogy.

## 2. Non-negotiable defaults

- Keep `strict` enabled; enable it for new projects. Never loosen compiler safety to make a change pass.
- Design flat, cohesive feature modules: colocate domain models, business logic, and direct database/I/O queries in feature modules rather than scattering across redundant layers. Do not create multi-layer service/manager/repository wrappers (`Controller -> Service -> Manager -> Repository -> DAO`) where intermediate layers merely forward calls without transformation.
- Apply the Rule of Three: write concrete logic and types first; do not extract an interface, abstract class, or generic parameter unless at least 3 distinct concrete implementations exist in the repository or an established framework contract requires it.
- Ban builder patterns for simple objects or interfaces (< 5 fields); use direct object literals with `satisfies` or typed parameter objects.
- Perform single-path atomic in-place refactoring: cleanly replace old implementations and atomically update all call sites, internal usages, and tests in the same change wave. Never introduce forwarding shims, zombie decoders, preemptive `@deprecated` staging, paranoid dual-writing, ghost code, or array/prototype monkey-patching.
- Treat external data as `unknown`. Parse or validate it once at the trust boundary, then pass a trusted domain type inward. Type assertions, type declarations, and generics provide no runtime validation.
- Treat persisted, queued, cached, or cross-process data that can outlive one process or deployment as a runtime protocol. Decode a supported version, validate it, migrate explicitly when required, and only then construct the current domain type. Do not let an in-memory TypeScript refactor silently redefine durable data.
- Validate operational inputs as well as object shape: paths, sizes, counts, timeouts, retry limits, and concurrency must be finite, bounded, and authorized for the operation. Static `string`/`number` types do not establish those properties.
- Avoid `any`. Quarantine unavoidable untyped interop in the smallest adapter, return a safer type, and explain the boundary. Treat `as unknown as T`, non-null `!`, and broad assertions as proof obligations, not fixes.
- Model mutually exclusive states as discriminated unions and make handling exhaustive. Do not represent a state machine as one object full of unrelated optional fields.
- Use types to expose real invariants and relationships, not to demonstrate type-system cleverness. Prefer readable runtime code and named, inspectable types over nested conditional/mapped-type puzzles.
- Prefer inference for local implementation details. Give exported APIs intentional parameter and return types when they define a contract or stabilize declaration output.
- Catch values as `unknown`; throw `Error` objects, preserve causal context, and never silently swallow failures. Model expected recoverable outcomes explicitly when callers must branch on them.
- Default to `const`. Use `readonly` when non-mutation is part of the API, while remembering it is shallow and compile-time-only.
- Keep modules cohesive and dependencies directional. Put side effects behind narrow adapters when that creates a real test or replacement seam; do not invent layers for hypothetical future consumers.
- Names should expose domain meaning and units (`timeoutMs`, `isReady`). Comments explain invariants, tradeoffs, protocol quirks, security constraints, and non-obvious *why*—never narrate the syntax.
- Treat filesystem paths, subprocess arguments, SQL values, object merges, logs, and secrets as security boundaries. Use parameterized/non-shell APIs and confine paths to an allowed root when the application requires one.

## 3. Type-design decisions

| Need | Prefer |
|---|---|
| Closed alternatives or lifecycle states | Discriminated union plus exhaustive `never` check |
| Named extensible object shape | `interface`; especially when composing object contracts |
| Union, tuple, mapped/conditional type, or alias | `type` |
| Untrusted JSON, env, CLI, DB, filesystem, or network value | `unknown` → parser/schema/guard → domain type |
| Configuration checked without widening its literals | `satisfies` when supported by the pinned TypeScript |
| Semantically distinct primitive with costly mix-ups | Opaque/branded type created only by a validating constructor; use sparingly |
| Relationship between input and output types | A constrained generic whose parameter appears in both positions |
| One input that may take several ordinary shapes | Union before overloads; overload only when call shapes or correlated returns require it |

Read [references/type-design.md](references/type-design.md) before designing public APIs, validators, error contracts, domain states, generics, or assertion-heavy interop.

Read [references/data-contracts.md](references/data-contracts.md) before changing persisted records, message or wire schemas, versioned JSON, migrations, timestamps, large integers, or serialization used for hashing/signing.

## 4. Async and runtime correctness

- Await or return every promise. Intentional background work needs an owner, an immediate rejection handler, a shutdown policy, and an explicit `void` marker.
- Do not use `forEach(async ...)`. Use a sequential `for...of`, bounded concurrency, or a deliberately sized `Promise.all` batch.
- `Promise.all` does not cancel its remaining work after a rejection. A timeout implemented only with `Promise.race` does not stop the losing operation.
- Pass `AbortSignal` through long-running or externally controlled operations when the runtime/API supports it. Cancellation, timeout, cleanup, and partial effects are part of the contract.
- Bound concurrency, queues, caches, listeners, and retries. Respect stream backpressure; use pipeline-style composition when available.
- Keep CPU-heavy work and synchronous I/O off an event-loop hot path. Workers are for substantial CPU work and should be pooled, not spawned per request; normal asynchronous I/O stays on the runtime's I/O facilities.
- Acquire and release files, sockets, streams, subprocesses, workers, timers, and listeners in one inspectable lifetime, normally with `try/finally` or a supported disposal construct.
- Before retrying a side effect, define whether it is idempotent, how ambiguous success is resolved, and where deduplication or atomicity lives. A bounded retry loop alone is not a reliability protocol.

Read [references/async-runtime.md](references/async-runtime.md) before changing promises, cancellation, streams, subprocesses, workers, event emitters, or lifecycle cleanup.

Read [references/side-effect-reliability.md](references/side-effect-reliability.md) before adding or changing retries, webhooks, queues, durable jobs, transactions, deduplication, or concurrent storage updates.

## 5. Performance golden path

1. Name the optimization target: startup, throughput, tail latency, memory, bundle size, type-check latency, or editor responsiveness.
2. Record the runtime/compiler version, representative workload, command, inputs, warm-up, sample count, and baseline distribution.
3. Profile the relevant layer before editing: emitted JavaScript/runtime, database or I/O, bundler, `tsc`, or language service.
4. Fix unnecessary work, algorithms, queries, serialization, I/O shape, and unbounded concurrency before micro-optimizing syntax or V8 behavior.
5. Re-run the same workload after each change. Keep only wins that survive variance and do not violate correctness or resource bounds.
6. Add a regression benchmark or budget when the improvement matters operationally.

Never claim a performance improvement from code inspection alone. Type-level simplification can improve compiler performance but does not inherently speed up emitted JavaScript. Read [references/performance.md](references/performance.md) for profiling, benchmarking, event-loop/memory work, and compiler diagnostics.

## 6. Reject these anti-patterns

- Multi-layer service/manager/repository wrappers (`Controller -> Service -> Manager -> Repository -> DAO`) that merely forward parameters without adding real domain logic or distinct polymorphism.
- Speculative generic helper abstractions (custom type-level metaprogramming toolkits, complex recursive mapped types) and builder classes for simple objects (< 5 fields) when direct object literals with `satisfies` suffice.
- Array monkey-patching, prototype pollution, or mutating global objects and prototypes (`Array.prototype`, `Object.prototype`) with custom helper methods.
- Shim multiplication (retaining deprecated forwarding wrappers), zombie decoders/dual-format fallbacks without explicit multi-version requirements, preemptive `@deprecated` staging, paranoid dual-writing, and ghost code retention.
- `JSON.parse(text) as T`, `process.env.X as Mode`, or database rows asserted directly into domain types without validation.
- Durable or wire data whose schema is inferred from an in-memory type, silently changed without a compatibility decision, or serialized without deciding how timestamps, large integers, `undefined`, and non-finite numbers are represented.
- User-controlled paths used without root-confinement/authorization, interpolated shell or SQL strings, or unbounded numeric options such as concurrency and retry counts.
- Blanket `any`, double assertions, unexplained non-null assertions, `@ts-ignore`, or broad lint disables used to silence a design problem.
- Boolean-flag-heavy public calls or optional-property bags whose combinations encode invalid states.
- Generics used once, phantom type parameters, enormous inferred public types, or conditional-type machinery that obscures the runtime behavior.
- Floating promises, async promise executors, `forEach(async ...)`, unbounded `Promise.all`, detached retries, or fire-and-forget work with no owner.
- Blindly retrying a non-idempotent effect, treating a timeout as proof that nothing happened, or using process-local deduplication for a contract that must survive crashes or multiple instances.
- Empty `catch`, loss of the original error/cause, thrown strings, or treating every Node callback/event/stream failure as a promise rejection.
- Synchronous filesystem/crypto/compression or large CPU loops on a latency-sensitive event loop.
- ESM/CJS or `moduleResolution` changes that type-check but are not exercised through the actual runtime/package consumer path.
- Barrel files that create cycles or expose internals, speculative project references, speculative abstractions, and catch-all `utils.ts` growth.
- Microbenchmarks presented as application wins without a representative before/after measurement.

## 7. Verification and handoff

Run tiered verification proportionate to the scope and risk of changes:

- **Tier 1 (Fast-Path - TDD & Localized Edits)**: Run targeted test suites and fast typechecks during rapid TDD iteration:
  - Vitest: `vitest run <file> -t "<pattern>"`
  - Jest: `jest <file> -t "<pattern>"`
  - Node test runner: `node --test --test-name-pattern="<pattern>" <file>`
  - Targeted typecheck: `tsc -p <tsconfig> --noEmit` or `tsc --noEmit`
- **Tier 2 (Full Verification - Architectural / Boundary Changes)**: Run whole-workspace test suites, configured linting (`eslint .`), format verification, declaration and bundle builds (`tsc --build`, `npm run build`), and exercise the real runtime entry point (CLI, server, browser, or package consumer).

For a library API, inspect emitted declarations and test an intended consumer import when practical. For performance work, report the exact before/after evidence and tradeoffs. Report unrelated problems without changing them.

For a durable-data change, test every supported version, unknown and malformed versions, migration output, and serialization edge values through the real persistence or message path. For retry or concurrency changes, test duplicates, timeout before and after commit, concurrent attempts, cancellation, and the observable terminal outcome.

Read [references/tooling-testing.md](references/tooling-testing.md) before changing `tsconfig`, package/module metadata, declarations, lint/format setup, tests, dependencies, or CI.

## 8. Maintain this skill

When changing this skill itself, use the maintainer-only prompt corpus and behavioral rubric in [references/evaluation.md](references/evaluation.md). Do not load it for ordinary TypeScript work.
