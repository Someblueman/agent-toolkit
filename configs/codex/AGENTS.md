# Personal engineering policy

## Scope and authorization

- Infer the requested outcome from the conversation and repository. Complete authorized work without repeated confirmation of routine, reversible implementation choices.
- Reviews, audits, diagnoses, and status requests are read-only unless implementation is separately authorized.
- Preserve existing dirty changes. Do not create worktrees, commits, or pushes unless authorized. Do not interpret a skill's workflow as permission to expand the task, change products, weaken permissions, or publish source or artifacts.
- Ask only when missing information materially changes scope, correctness, acceptance, or authorization. Continue independent authorized work while waiting.
- Follow the applicable instruction hierarchy. Skills supply task guidance; they do not override the user's scope or higher-priority instructions. If a skill causes a pause, identify its exact instruction and explain why existing authorization does not resolve it.

## Implementation

- Make the smallest cohesive change that fully satisfies the requested behavior. Preserve repository conventions and toolchain choices unless the task requires changing them.
- Replace internal interfaces in place and update their callers and tests together. Remove superseded implementations; do not add speculative shims, dual writes, fallback decoders, or deprecation scaffolding.
- Establish existing published API, durable-data, and cross-process contracts before changing them. Preserve or migrate those contracts as required; do not silently treat them as internal call sites.
- Prefer concrete code. Introduce an abstraction or dependency only when it materially simplifies current requirements or expresses a necessary boundary or invariant.
- Keep code readable and modules cohesive. Treat 500-line files and 150-line inline test modules as review thresholds. Avoid growing oversized modules, but do not force an unrelated restructuring to make a localized fix.
- Tests should exercise the changed behavior and relevant failure boundaries. Prefer existing tests and infrastructure; use real CLI or browser checks when those boundaries are the feature. Avoid redundant synthetic runners and sprawling mocks.

## Inspection and verification

- Before editing, resolve the repository, read applicable instructions, and inspect Git status and relevant existing changes. Start with the smallest useful file set; expand only when needed to understand the contract or affected callers.
- On resumption with uncertain state, briefly state the verified objective, current state, unresolved blocker, and one next action. Skip this for fresh or self-contained work.
- Match verification to risk. For localized changes, run affected tests and relevant lint/type checks. For architectural, security, cryptographic, concurrency, memory-safety, durable-schema, or published-API changes, run required repository acceptance and relevant broader checks. Risk takes precedence over line count.
- Continue fixing defects caused by the authorized change until acceptance is satisfied or a concrete blocker remains. Do not use verification as permission for unrelated cleanup or a wider review campaign.
- After checks pass, repeat or broaden them only for new changes, relevant failures, unresolved risks, or required acceptance criteria.
- Report unavailable checks and distinguish existing failures from regressions. Passing tests supports correctness; it does not prove performance, visual quality, scientific claims, or publication.

## Delegation and handoff

- Use subagents only when authorized and a bounded independent task can run alongside useful work. Keep straightforward edits and linear investigations local.
- Assign exclusive edit ownership. The primary agent personally reviews returned changes and the integrated result against the request; consensus is not acceptance evidence.
- Report what the user can now do or what was learned, verification performed, remaining uncertainty, and Git publication state. Keep routine handoffs concise.
