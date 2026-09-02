# Global Engineering Policy

Cross-agent principles that any coding assistant in this toolkit should follow. Vendors install this file at the location their agent reads at session start (Codex: `~/.codex/AGENTS.md`, etc.).

## Implementation Principles

- **Single-Path Execution & Clean Replacement**: Do not preserve backwards compatibility unless the current requirements explicitly require it. When refactoring or updating an interface, data structure, or function, perform a clean in-place replacement and atomically update all call sites, internal usages, and tests in the same change wave.
- **Forbidden Legacy Retention Anti-Patterns**: Never introduce or retain:
  - *Shim Multiplication*: Keeping deprecated functions/methods as pass-through forwarding wrappers around new implementations.
  - *Dual-Format Fallback & Zombie Decoders*: Retaining obsolete serialization/deserialization logic or parsers alongside new formats without explicit user instruction.
  - *Preemptive Deprecation Staging*: Introducing `@deprecated` annotations, feature flags, or staged migration scaffolding when an immediate clean replacement is feasible.
  - *Paranoid Dual-Writing*: Mutating both legacy and new stores, fields, or endpoints concurrently during single-agent refactors.
  - *Ghost Code Retention*: Commenting out old implementations, leaving unused fallback branches, or parking dead code in `_legacy` files.
- **Anti-Abstraction Mandate**: Choose the simplest concrete implementation that fully meets current requirements.
  - Apply the *Rule of Three*: Write concrete logic first; do not extract a trait, interface, abstract class, or generic parameter unless at least 3 distinct concrete implementations exist in the repository or an established framework contract requires it.
  - Ban speculative abstractions, anticipatory refactoring, builder patterns for simple structs (< 5 fields), multi-layer service wrappers, and unrequested helper utilities.
- **TDD Calibration & Anti-Bloat**: Calibrate test coverage strictly to the requirement scope. Write focused, high-signal tests that verify specified behavior and direct failure boundaries. Forbid speculative test matrices, combinatorial permutation sprawl, redundant smoke tests that duplicate unit assertions, and deep mocking of internal structs.
- **Ban Standalone Smoke Test Scripts**: Formally prohibit creating throwaway scripts or synthetic integration runners named `*smoke*` (e.g. `scripts/*-smoke.mjs`, `smoke.py`), creating ephemeral `/tmp/*-smoke` workspaces, or using shallow process-invoking smoke tests as a substitute for domain unit tests.
- **Hard File Length Ceiling (500 LOC)**: Impose an explicit quantitative line budget (maximum 500 lines per source or test file). Whenever modifying a file that exceeds or would exceed 500 lines, modularly decompose it into cohesive submodules rather than appending code to it.
- **Inline Test Budget (150 LOC)**: Forbid inline `mod tests` exceeding 150 lines within production source files. Any test suite exceeding 150 lines must be extracted into dedicated test files under `tests/` or sibling modules.
- **Code Density & Anti-Verbosity**: Prohibit repetitive, sprawling mock fixtures, multi-line ceremonial boilerplate, and redundant defensive layers where standard idiomatic logic suffices. Write compact, high-density domain logic and lean fixtures.
- **Library Selection**: Prefer established, well-maintained libraries over custom implementations when they reduce overall complexity and their dependency cost is justified.
- **Out-of-Scope Findings**: When work reveals an issue outside the current task, report it clearly in the final handoff instead of changing unrelated code. Add a `TODO` or `FIXME` only when the issue is directly relevant to code already being changed and the marker would be useful to future maintainers.

## Session Protocol

- **Pre-Flight Inspection Cap**: Before editing, resolve the repository root, read active instructions, and inspect `git status --short --branch`. Cap pre-flight reading to the minimum set of directly relevant files (target 3-5 files). Avoid ceremonial stalling (e.g. repetitive status/diff commands without intervening edits, re-reading unchanged files, or lengthy conversational preambles before tool execution).
- **Scope Discipline**: Treat the user-named repository, skill, and deliverable as the controlling scope; do not substitute an adjacent project or implementation.
- **State Preservation**: Preserve existing dirty changes. Do not create worktrees, commits, or pushes unless the user authorizes them.
- **Tiered Verification by Scope**: Match verification effort directly to the risk and scope of the change:
  - *Tier 1 (Fast-Path)*: For bug fixes, localized refactors, minor feature additions, internal helpers, documentation, or config changes: run ONLY the targeted test suite/filter for the affected module and fast linter/typecheck. Do not run whole-workspace test suites or heavy integration benchmarks for localized edits.
  - *Tier 2 (Full Verification)*: For core architectural modifications, cryptographic primitives, authentication/authorization boundaries, concurrency/memory-safety invariants, durable data schema migrations, or public library published APIs: run the full repository acceptance command, complete test suite, linters, and any relevant fuzz/property tests.
- **Audits Do Not Authorize Repairs**: An audit, review, diagnosis, or status request is read-only unless the user separately authorizes implementation. Report findings without beginning a repair wave.
- **Prove Before Generalizing**: Demonstrate one real end-to-end workflow before extracting a framework, general platform, or reusable orchestration layer from it.
- **One Review/Fix Wave**: Do not begin a second review-and-repair cycle without the user's explicit direction. Report remaining findings instead of recursively expanding the work.
- **Handoff Transparency**: At handoff, report user-visible capability or knowledge gained separately from operational work, verification, remaining uncertainty, and Git publication state.

## Multi-Agent Ownership & Subagent Restraint

- **Subagent Restraint**: Spawning subagents incurs significant context and latency overhead. Do NOT use subagents for straightforward single-file edits, localized bug fixes, linear reasoning chains, or routine reconnaissance.
- **Authorized Delegation**: Use subagents only for concrete, bounded, parallel investigations (e.g. searching across distinct, unrelated repositories or disjoint domains) that can proceed independently.
- **Primary Ownership**: The primary agent remains the implementation and acceptance owner. Subagent reports, reviews, and edits are advisory until the primary agent personally inspects the resulting diff and the relevant surrounding code.
- **Sequential Review**: For code-changing subagent work, the primary agent must review each returned change before treating that task as complete or beginning another implementation wave.
- **Non-Delegable Judgment**: The primary agent may solicit advisory reviews, but must personally perform the final integrated code review and compare the implementation with the original request or plan. Final plan conformance and the decision to claim completion must not be delegated.
- **Evidence Standard**: Passing tests and subagent consensus are supporting evidence, not substitutes for the primary agent's own code-level and end-to-end judgment.
- **Phased Decomposition**: If the integrated change is too large to review within the available context, divide the work into smaller phases and report partial completion rather than claiming success.