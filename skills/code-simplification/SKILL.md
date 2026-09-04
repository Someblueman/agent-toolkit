---
name: code-simplification
description: Simplify code, remove accidental complexity, flatten control flow, or reduce over-engineering while preserving the required behavior. Use for requested simplification and refactoring; use existing domain tests and proportionate differential checks.
---

# Code simplification

Simplify accidental complexity while preserving the required observable behavior. First identify the behavior contract and the smallest concrete transformation. Preserve useful domain types, validation boundaries and repository conventions.

1. Inspect the affected call sites and tests. Establish return values, errors, mutations, serialized data and any ordering or numeric precision requirements.
2. Prefer direct control flow and existing library operations. Remove patterns only when they add no current value; do not replace every class, trait or pipeline mechanically.
3. Verify with existing tests and representative boundary cases. Choose randomized testing when the input space warrants it; there is no fixed case quota. Passing cases establish evidence for that corpus, not universal equivalence.

## Helpers

Resolve `SKILL_DIR` to the absolute directory containing this loaded skill, independent of the target repository's working directory.

```bash
python3 "$SKILL_DIR/scripts/complexity_budget_analyzer.py" path/to/python --no-fail
python3 "$SKILL_DIR/scripts/invariant_regression_checker.py" --baseline baseline.py --candidate candidate.py
```

The analyzer supports Python only. Its numeric defaults are review heuristics, not required refactoring targets. Empty or unsupported input is an error.

Python differential mode requires baseline `TEST_CASES = [((arg1,), {"keyword": value})]` and the selected function (`run` by default). Inputs must support deepcopy; independent copies and post-call mutations are compared. External state, I/O and alias relationships are outside this helper's coverage and require domain tests. Exact types/integers and outputs are preserved; no identifiers or timestamps are silently masked.

CLI mode requires `--cases cases.json`, a nonempty JSON array of strings, each passed as one literal argument. Command strings are split with shell-style quoting but are not shell programs. Runs have a 30-second timeout. Golden mode requires nonempty `test_cases` with `id`, `input`, and `expected`; unexpected exceptions fail. Use repository tests for explicit error contracts or richer invocation shapes. Timings here are diagnostic, not performance evidence.

## References

- [Complexity diagnosis](references/accidental-complexity-rubric.md)
- [Pattern stripping](references/pattern-stripping-and-flattening.md)
- [Control flow and pipelines](references/control-flow-and-data-pipelines.md)
- [Complexity review](references/complexity-budgeting-framework.md)
- [Language transformations](references/language-simplification-patterns.md)
- [Behavioral verification](references/behavioral-invariance-testing.md)
