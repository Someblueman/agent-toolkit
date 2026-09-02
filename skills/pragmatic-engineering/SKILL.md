---
name: pragmatic-engineering
description: Enforce pragmatic, anti-bloat software engineering across all languages and frameworks. Use when modifying existing code, designing fixes, refactoring, evaluating backwards compatibility, selecting verification tiers, calibrating test suites, or preventing ceremonial stalling and over-abstraction.
---

# Pragmatic Engineering

Deliver the smallest, most direct, and fully verified change that satisfies the user's explicit requirements. Enforce single-path execution, lean testing, tiered verification, and anti-abstraction defaults across all codebases.

## Core Axioms

1. **Clean Replacement over Compatibility**: Default to updating callers in place. Never write compatibility shims, dual decoders, or forwarding functions unless explicitly commanded by the user.
2. **Concrete over Speculative**: Write direct, concrete implementations. Never invent generic traits, interfaces, abstract classes, or builder patterns for single use cases.
3. **Calibrated Verification over Test Sprawl**: Write the minimum sufficient test coverage to verify the specific requirement. Run fast, targeted tests for localized changes (Tier 1) and reserve full acceptance suites for critical architectural changes (Tier 2).
4. **Action over Ceremony**: Cap pre-flight file reads to 3-5 files. Avoid repetitive status checks and jump straight from entry point identification to implementation.

## 1. Compatibility Decision Matrix

| Change Type | Default Action | Forbidden Anti-Pattern |
|---|---|---|
| **Internal Function / Method Signature** | In-place update of signature; atomically update all call sites in same diff | *Shim Multiplication*: Keeping old signature as wrapper forwarding to new function |
| **Internal Data Model / Struct / Type** | In-place struct mutation; migrate all instantiation sites immediately | *Dual-Format Fallback / Zombie Decoders*: Keeping old parser/codec alive "just in case" |
| **Feature Deprecation / Replacement** | Delete old code cleanly; replace with new implementation | *Preemptive Deprecation Staging*: Adding `@deprecated` annotations or staged rollout flags |
| **Internal State / Storage Mutation** | Direct write to new schema/field | *Paranoid Dual-Writing*: Concurrently mutating old and new storage representations |
| **Dead / Replaced Logic** | Immediate deletion | *Ghost Code Retention*: Commenting out old code or creating `_legacy` files |
| **Public Crate / Published Library API** | If repository is a published library with external consumers, follow project SemVer; if internal application, replace in-place | Unnecessary major version churn for internal-only APIs |
| **User Explicitly Requests Compatibility** | Implement narrow adapter with clear documentation and tests | Spreading compatibility checks throughout core domain logic |

Read [references/compatibility-matrix.md](references/compatibility-matrix.md) for detailed refactoring recipes and before/after code examples.

## 2. Fast-Path Decision Tree (Tiered Verification)

Evaluate the change scope to select the verification tier:

```text
[Change Proposed]
       |
       +---> Bug fix, localized refactor, minor feature, internal helper, doc/config?
       |        |
       |        v
       |     [Tier 1: Fast-Path]
       |     - Cap pre-flight reads to <= 3-5 files
       |     - Run ONLY targeted test command (e.g. pytest -k test_name, cargo test path::to::test)
       |     - Run targeted linter / typecheck
       |     - Complete handoff without full workspace rebuild
       |
       +---> Core architecture, crypto, auth/security, concurrency/memory invariants, schema migration, published API?
                |
                v
             [Tier 2: Full Verification]
             - Run repository acceptance command
             - Run full workspace test suite & linters
             - Run fuzz, property, or Miri checks where applicable
```

Read [references/fast-path.md](references/fast-path.md) for language-specific fast test commands and escalation rules.

## 3. Anti-Bloat, Line Budgets & TDD Calibration Heuristics

- **Quantitative Line Budgets**:
  - **500 LOC File Ceiling**: Maximum 500 lines per file. Never append code to a file that reaches or exceeds 500 lines; decompose using the God-File Decomposition Protocol.
  - **150 LOC Inline Test Limit**: Forbid Rust inline `mod tests` exceeding 150 lines. Extract to dedicated test files under `tests/` or sibling modules.
- **Ban Standalone Smoke Test Scripts**: Strictly ban throwaway scripts named `*smoke*` (e.g. `scripts/*-smoke.mjs`, `smoke.py`), `/tmp/*-smoke` directories, and black-box process spawning. Replace with targeted in-memory domain unit tests.
- **Rule of Three**: Implement concrete functions and structs first. Extract an interface, trait, or generic abstraction only when 3+ distinct concrete implementations exist in the codebase.
- **Constructor Simplicity**: Do not introduce a Builder pattern for structs with < 5 fields. Use direct struct initialization or a simple `new(...)` constructor function.
- **Lean Fixtures**: Prohibit 50-line inline mock dictionaries. Use minimal valid factory functions with field overrides and table-driven boundary tests.
- **Flat Architecture**: Forbid artificial 4-layer call chains (Controller -> Service -> Manager -> Repository -> Adapter) for basic domain logic or CRUD. Write direct, cohesive functions.
- **TDD Calibration**:
  - Write 1-3 targeted test cases per requirement: (1) reproduction / primary acceptance test, (2) critical edge/error boundary test.
  - Ban speculative combinatorial test matrices (e.g. testing 30 permutations of non-critical inputs).
  - Ban smoke test sprawl (writing 20 trivial tests that duplicate unit test assertions).
  - Avoid heavy mocking frameworks for simple internal domain structs; test real concrete values.

Read [references/anti-bloat.md](references/anti-bloat.md) for anti-pattern code catalogs, the God-File Decomposition Protocol, lean fixtures, and TDD calibration rubrics.

## 4. Subagent Restraint & Anti-Stalling Protocol

- **Zero Ceremonial Stalling**:
  - Do not run `git status` or `git diff` repeatedly without intermediate file edits.
  - Do not inspect entire directory trees when the target file path is already known.
  - Do not write lengthy conversational reassurances or speculative preambles before tool calls.
- **Subagent Restraint**:
  - Spawning subagents introduces context duplication and communication latency.
  - **Do NOT spawn subagents** for: single-file edits, localized bug fixes, linear reasoning chains, or routine code searches.
  - **Spawn subagents ONLY** for: large-scale, independent parallel audits across distinct repositories or completely isolated domain investigations.
  - Primary agent must personally review and verify all subagent diffs and surrounding code before acceptance.

Read [references/subagent-restraint.md](references/subagent-restraint.md) for delegation decision rubrics and ownership invariants.

## References

- Compatibility rules, migration recipes, and anti-pattern catalogs: read [references/compatibility-matrix.md](references/compatibility-matrix.md).
- Tiered verification workflows, test filtering commands, and fast-path execution: read [references/fast-path.md](references/fast-path.md).
- Concrete-first architecture, constructor simplicity, and calibrated TDD: read [references/anti-bloat.md](references/anti-bloat.md).
- Subagent delegation criteria, ownership invariants, and context budget management: read [references/subagent-restraint.md](references/subagent-restraint.md).
