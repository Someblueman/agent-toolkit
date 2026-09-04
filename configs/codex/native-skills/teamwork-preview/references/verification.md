# Independent Verification and Integrity

Verification is adversarial and independent. The author of a change cannot approve it, and passing tests alone does not override a substantive audit failure.

## Milestone gates

Run fresh agents after integration:

1. **Critic:** Review the approved requirement, diff, and surrounding code. Check correctness, completeness, interface conformance, regressions, error handling, project conventions, and missing focused tests. Findings must include severity, evidence, and a reproduction or reasoning chain.
2. **Challenger:** Try to falsify the implementation by executing adversarial cases: boundaries, invalid inputs, failure paths, concurrency or resource stress where relevant, and realistic combined scenarios. It may add tests only in an exclusively assigned path; otherwise it reports exact probes for the worker.
3. **Auditor:** Read the approved integrity mode directly from `REQUEST.md`. Verify that reported commands actually ran, failures were not hidden, tests were not weakened or skipped, outputs were not fabricated, and the implementation is genuine rather than a hardcoded or facade solution.

The gate passes only when all are true:

- required build and tests pass on real command output;
- no unresolved Critic veto remains;
- Challenger cannot reproduce a requirement-breaking case within the agreed bounds;
- Auditor returns `CLEAN` for the selected integrity mode;
- the primary has inspected the integrated diff and evidence.

An Auditor verdict of `INTEGRITY VIOLATION` is a binary veto. Forward its complete evidence to the next repair wave. Do not summarize away inconvenient details or weaken the test to make the result pass. If an Auditor crashes or times out, replace it; never skip the gate.

## Integrity modes

All modes prohibit fabricated logs/results, hardcoded evaluation answers, dummy/facade implementations, test disabling, and falsely claiming commands passed.

- **development:** Normal reuse and dependencies are permitted. Check authenticity, scope, and evidence.
- **demo:** Enforce the shortcut restrictions recorded in the brief. Check provenance of core logic, external delegation, and test-source access.
- **benchmark:** Enforce all recorded from-scratch, standard-library, hidden-test, or resource constraints. Treat unauthorized reuse or external execution as failure even if outputs are correct.

## Success audit

After all milestones pass, the primary first runs the end-to-end command and records its integrated criterion-by-criterion review without claiming completion. The primary then authorizes the orchestrator to spawn a fresh `teamwork_success_auditor` descendant with only the approved brief, working directory, diff/baseline information, and run-artifact paths. Do not give it the team's conclusion. The auditor verifies the recorded primary review as evidence; it must not depend on a completion claim that can occur only after its own verdict.

It must:

- map every acceptance criterion to direct evidence;
- run the full end-to-end command or equivalent independent evaluation;
- inspect the integrated result rather than milestone summaries;
- check for skipped, mocked, or stale evidence;
- return exactly one verdict: `SUCCESS CONFIRMED` or `SUCCESS REJECTED`, followed by criterion-by-criterion evidence and blocking findings.

On rejection, send the complete report to the orchestrator and resume only the necessary repair milestones. Repeat the relevant milestone gates and then use a fresh Success Auditor.

`SUCCESS CONFIRMED` is necessary but not sufficient: the primary must still compare the delivered state with the original approved brief and report any uncertainty honestly.
