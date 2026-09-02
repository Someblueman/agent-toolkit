# TypeScript Engineering Skill Evaluation

This is maintainer-only material for evaluating changes to the skill. Do not load it during ordinary TypeScript work. It tests activation and observable engineering decisions, not whether an answer repeats preferred wording.

## 1. Evaluation protocol

1. Run cases in an isolated temporary repository with pinned package/runtime metadata appropriate to the prompt.
2. For implicit-trigger cases, do not name the skill. Inspect the product trace or skill-use notice when available. If activation is not observable, compare with an explicit `$typescript-engineering` run and score the behavioral differences conservatively.
3. Give the evaluating agent the prompt, skill path, and raw fixture repository only. Do not reveal the rubric, expected answer, prior failure, or proposed fix.
4. Use an independent evaluator or fresh isolated session when available and authorized. The maintainer reviews commands, diffs, tests, and final claims personally.
5. Record the model/runtime, date, case ID, activation result, changed files, commands run, and rubric result. Preserve failures that motivate a skill change.
6. Do not grade exact prose, headings, or regex matches. Grade actions, artifacts, evidence, and whether the result respects the request.

For a narrow edit, run the cases directly related to it plus `TRIGGER-01` through `TRIGGER-04`. For a substantial revision, run every case at least once and rerun any nondeterministic failure before changing the skill.

## 2. Shared rubric

Score each applicable item `pass`, `fail`, or `not-applicable`:

| Dimension | Passing evidence |
|---|---|
| Activation | The skill activates for TypeScript-centered work and stays out of unrelated or framework-only work |
| Repository truth | The agent inspects instructions, pinned runtime/toolchain, config, and canonical commands before prescribing changes |
| Scope | It performs only the requested implementation/review/diagnosis and avoids incidental migrations or dependencies |
| Runtime boundary | External values are validated and platform-specific APIs match the actual executing runtime |
| Durable contract | Persisted/wire changes have an explicit version, compatibility decision, codec, and migration evidence when applicable |
| Effect protocol | Retries, duplicates, ambiguous outcomes, atomicity, and concurrency ownership are addressed when applicable |
| Verification | Focused tests and the real runtime, package-consumer, persistence, message, or UI path are exercised as needed |
| Claim ceiling | Correctness and performance claims do not exceed the observed evidence |

Any failure in an applicable runtime-boundary, durable-contract, effect-protocol, or claim-ceiling dimension fails the case. Do not compensate for a critical failure with stylistic quality elsewhere.

## 3. Trigger cases

### TRIGGER-01: ordinary TypeScript implementation

Prompt: `Add a parser for this .ts CLI command and cover malformed arguments with tests.`

Expected: implicit activation. The agent should inspect repository commands and treat CLI values as runtime input.

### TRIGGER-02: TypeScript configuration

Prompt: `Our Node package type-checks but its built ESM entry fails to import. Diagnose the tsconfig and package exports.`

Expected: implicit activation. The agent should distinguish compiler, emitted artifact, and actual package-consumer behavior.

### TRIGGER-03: framework-only UI work

Prompt: `The spacing and colors on this React page do not match the supplied screenshot. Fix the visual design without changing behavior.`

Expected: the TypeScript skill should not be the primary workflow merely because the repository contains TSX. If selected alongside visual/framework guidance, it should stay confined to TypeScript-relevant edits.

### TRIGGER-04: unrelated language

Prompt: `Optimize this Rust iterator and add Criterion benchmarks.`

Expected: no TypeScript-skill activation.

## 4. Behavior cases

### BEHAVIOR-01: bounded filesystem concurrency

Prompt: `In this Node 22 TypeScript CLI, implement scan-json <root> --concurrency <n>. It may scan 10,000 files, should stop on abort, and should report malformed files without losing their paths.`

Required observations:

- validates `n` as a finite positive integer with a justified cap;
- confines discovered and user-controlled paths to the allowed root if that is the CLI's trust boundary;
- starts work only when a bounded slot is available rather than constructing every promise first;
- propagates cancellation, owns resource cleanup, and preserves path context plus the original error cause;
- runs the actual CLI path and malformed/abort tests.

### BEHAVIOR-02: durable JSON evolution

Prompt: `Version 1 memory records are stored as JSON with numeric sequence and createdAt fields. The new TypeScript domain model wants bigint sequence and Date createdAt. Update persistence without losing existing records.`

Required observations:

- separates the domain model from versioned encoded schemas;
- does not pass `bigint` or `Date` through ordinary JSON serialization as if types survive;
- defines explicit encodings, validates v1, migrates deterministically, and emits an intentional current version;
- preserves only the compatibility the request requires and rejects unknown versions safely;
- tests golden v1/current fixtures, unsafe integers, invalid dates, and the real persistence path.

### BEHAVIOR-03: ambiguous webhook retry

Prompt: `A TypeScript worker POSTs a billing webhook. Calls sometimes time out after the receiver has committed. Add three retries so events are never lost or duplicated.`

Required observations:

- rejects the premise that a timeout proves failure or that retries alone prove no duplication;
- discovers whether the receiver supports stable idempotency keys or reconciliation;
- reuses one logical-operation key, binds it to the request, and durably records the relevant outcome when in scope;
- retries only transient failures within one bounded deadline and reports any remaining uncertainty honestly;
- tests timeout before and after commit plus concurrent duplicates.

### BEHAVIOR-04: concurrent state update

Prompt: `Two async handlers can claim the same queued job after reading status='pending'. Fix the TypeScript service so only one owns it.`

Required observations:

- identifies the read-check-write race despite JavaScript's event loop;
- uses a storage-level conditional update, constraint, compare-and-swap, or suitable transaction;
- verifies the affected row/version and defines lease/recovery behavior if ownership can outlive a process;
- tests concurrent claims and crash/retry behavior through the adapter.

### BEHAVIOR-05: browser TSX boundary

Prompt: `Fix cancellation and stale results in this React search component written in TSX. It uses browser fetch and runs in an edge-rendered app.`

Required observations:

- uses the actual browser/edge runtime contract rather than Node streams, child processes, or Node-only lifecycle assumptions;
- applies TypeScript boundary and cancellation guidance while consulting the repository's framework conventions for effect/render semantics;
- verifies the user-visible flow with the configured frontend test path.

### BEHAVIOR-06: measured compiler performance

Prompt: `This TypeScript workspace feels slow in the editor. Simplify the types and tell me how much faster the application will run.`

Required observations:

- separates language-service/compiler latency from emitted JavaScript runtime performance;
- records pinned versions and a reproducible compiler/editor proxy before editing;
- uses supported diagnostics/traces to identify expensive type work;
- does not claim runtime speedup without runtime measurement;
- keeps only a measured improvement that preserves declarations and behavior.

### BEHAVIOR-07: flat cohesive module vs multi-layer wrapper sprawl

Prompt: `Refactor the user profile update workflow in this TypeScript project. Currently it passes through UserController -> UserService -> UserManager -> UserRepository -> UserDao with empty forwarding interfaces at each step.`

Required observations:

- collapses the ceremonial multi-layer wrapper stack into a cohesive feature module with direct database queries and concrete domain logic;
- eliminates speculative single-implementation interfaces and abstract classes (Rule of Three);
- avoids builder classes for simple records (< 5 fields) and uses direct object literals with `satisfies`;
- verifies the refactored module directly against existing behavioral tests.

### BEHAVIOR-08: single-path clean replacement vs shims/zombies

Prompt: `Update the internal BillingRecord interface to replace legacy string timestamp fields with numeric epochMs and add a mandatory currency code across the codebase.`

Required observations:

- performs clean atomic in-place replacement across all internal usages, codecs, and test fixtures in the same change wave;
- does not introduce forwarding shims, dual-format fallback decoders, or zombie parsers for internal types;
- avoids preemptive `@deprecated` scaffolding, paranoid dual-writing, or ghost code branches;
- updates all affected call sites and runs targeted tests to confirm clean transition.

### BEHAVIOR-09: fast-path test execution during localized TDD

Prompt: `Fix an edge-case bug in calculateTax where zero-rate exemptions throw an unexpected error, using TDD in this large monorepo.`

Required observations:

- runs targeted Fast-Path test runner commands (e.g. `vitest run <file> -t "<pattern>"`, `jest <file> -t "<pattern>"`, or `node --test --test-name-pattern="<pattern>" <file>`) and targeted `tsc --noEmit` during red-green-refactor cycles;
- avoids executing whole-monorepo test suites or heavy global linters during rapid localized iteration;
- writes focused, high-signal tests targeting the boundary condition without combinatorial test matrix sprawl or deep mocking of internal objects;
- executes Tier 2 acceptance verification only before final handoff.

## 5. Regression discipline

When a case fails, determine whether the cause is the skill, missing fixture context, repository instructions, or ordinary model variance. Make the narrowest supported change and rerun the failed case plus adjacent trigger cases. Do not add a universal rule from one contrived prompt, and do not weaken an existing safety boundary merely to improve activation rate.
