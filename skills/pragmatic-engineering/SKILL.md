---
name: pragmatic-engineering
description: Enforce pragmatic, anti-bloat software engineering across all languages and frameworks. Use when modifying existing code, designing fixes, refactoring, evaluating backwards compatibility, selecting verification tiers, calibrating test suites, or preventing ceremonial stalling and over-abstraction.
---

# Pragmatic engineering

Use the repository's requirements and the applicable AGENTS.md to choose the smallest cohesive change. This skill adds implementation judgment, not another approval gate.

- Replace internal interfaces and callers together. Published APIs, persisted records and cross-process protocols have contracts that may require migration; establish those before removing compatibility.
- Prefer concrete code. An abstraction is justified by a current boundary, invariant or reduction in complexity, not an implementation-count quota. Use constructors or builders according to validation and call-site clarity, not field count.
- Treat 500 source lines and 150 inline test lines as review thresholds. Split along cohesive responsibilities when useful; avoid unrelated restructuring for a small fix.
- Test changed behavior and meaningful failure boundaries. A real subprocess or browser test is appropriate when that boundary is the feature. Names such as `smoke` do not determine test quality.
- Start with the smallest useful inspection. Escalate verification for security, memory safety, concurrency, durable data or published contracts even when the diff is short.
- Continue repairing the authorized change until acceptance. Do not expand into unrelated cleanup or use a skill as permission to publish or delegate.

## References and helper

- [Compatibility decisions](references/compatibility-matrix.md)
- [Focused verification](references/fast-path.md)
- [Complexity review](references/anti-bloat.md)
- [Delegation boundaries](references/subagent-restraint.md)

Resolve `SKILL_DIR` to the absolute directory of this loaded skill. Run `python3 "$SKILL_DIR/scripts/check_anti_bloat.py" <affected-path>` for advisory size findings. `--strict` is only for limits explicitly enforced by the target project. A clean report is not a correctness verdict.
