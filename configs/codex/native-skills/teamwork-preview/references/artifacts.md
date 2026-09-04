# Durable Run Artifacts

Phase 1 uses `~/.codex/teamwork-drafts/<project>-<UTC timestamp>/` for `ORIGINAL_REQUEST.md` and `prompt_draft.md`; this preserves the interview without touching the target project. After approval, create the execution coordination root at `~/.codex/teamwork-runs/<project>-<UTC timestamp>/` so an existing repository stays clean. For a greenfield project inside `~/teamwork_projects`, use `<project>/.teamwork/` unless the user chose otherwise.

Use this minimal layout:

```text
<coordination-root>/
├── ORIGINAL_REQUEST.md
├── REQUEST.md
├── PLAN.md
├── PROGRESS.md
├── VERIFICATION.md
└── agents/
    └── <role>-<milestone>-<n>/
        ├── BRIEFING.md
        ├── progress.md
        └── handoff.md
```

The coordination tree contains metadata, reports, and scratch notes only. Source code, durable tests, generated product assets, and project data belong in explicitly approved project paths.

The primary is the sole writer and authority for top-level `PLAN.md`, `PROGRESS.md`, and `VERIFICATION.md`. Coordinators and reviewers return structured proposals or findings; they do not concurrently edit those files.

## REQUEST.md

Copy the approved `prompt_draft.md` verbatim into this immutable file and record the source draft path. Keep `ORIGINAL_REQUEST.md` as the append-only verbatim user record. Never silently rewrite earlier scope; later substantive changes are appended to `ORIGINAL_REQUEST.md` and reflected as explicit amendments in `PLAN.md` and `PROGRESS.md`.

```markdown
# Approved Teamwork Request

Approved: <UTC timestamp>
Source draft: <absolute path to prompt_draft.md>

<verbatim approved brief>
```

## PLAN.md

```markdown
# Project Plan

- Working directory: <path>
- Baseline: <git commit and dirty-state summary, or non-git baseline>
- Execution path: <path>
- Integrity mode: <mode>

## Interface contracts

- <public contract shared across milestones>

## Milestones

| ID | Outcome | Dependencies | Owned paths | Verification | Status |
|---|---|---|---|---|---|
| M1 | ... | none | ... | AC1 | planned |

## Agent roster

| Agent | Role | Assignment | Status | Evidence |
|---|---|---|---|---|
```

## PROGRESS.md

Keep this current at dispatch, integration, gate, and recovery boundaries—not after every tool call.

```markdown
# Progress

Last updated: <UTC timestamp>
Current phase: <exploration | implementation | verification | repair | success-audit | complete>

## Completed
- <milestone and concrete output>

## Active
- <agent, task, and expected next evidence>

## Blocked or failed
- <failure and response; “none” when empty>

## Next
- <single next coordination action>
```

## Agent handoff

Every agent returns the following structure in its final collaboration response. A writable agent may also place the same content in its assigned `handoff.md`. For a read-only agent, the primary inspects the returned response and persists the accepted evidence in the coordination tree; never request an approval merely to make the agent write its handoff.

```markdown
# Handoff

## Observation
<facts and file/command evidence>

## Reasoning
<why the evidence supports the conclusion>

## Changes or findings
<exact paths, owned edits, or review findings>

## Caveats
<unknowns, failures, and assumptions>

## Verification
<commands run and actual outcomes>

## Recommended next action
<one concrete handoff>
```

## VERIFICATION.md

Record each gate with agent identity, baseline or diff inspected, commands actually executed, verdict, findings, and repair linkage. Finish with the Success Auditor report and the primary agent's independent conformance decision. Never record “passed” without the underlying command or evaluation evidence.
