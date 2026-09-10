# Phase 1: Interview and Approved Brief

The interview specifies **what must be true**, not the implementation design. Ask only questions whose answers change scope, authorization, or verification. Prefer one to three concise questions per turn and present concrete choices when ambiguity has a few plausible interpretations. Use the client's native structured-question input when it is available and the choices are mutually exclusive; otherwise ask concise prose questions. Never block progress on the absence of a particular UI tool.

At the first substantive request, create a non-project draft directory under `~/.codex/teamwork-drafts/<short-name>-<UTC timestamp>/`. Write the user's original request verbatim to `ORIGINAL_REQUEST.md` under a timestamped heading and create `prompt_draft.md` from the brief template below. Append later substantive user answers verbatim to `ORIGINAL_REQUEST.md`; never rewrite earlier entries. Update `prompt_draft.md` after each interview turn so the user can inspect the evolving artifact. These are coordination records only—Phase 1 still must not touch the target project or launch implementation agents.

## Interview sequence

1. **Goal and audience:** What should exist at the end? Is this production work, a reproducible demo, an evaluation, or exploration? Who will use or judge it?
2. **Material ambiguities:** Identify choices that change the deliverable, interfaces, scale, or risk. Do not ask about algorithms, file layout, or architecture unless the user wants to constrain them.
3. **Requirements:** Draft two to five requirement blocks from stated priorities. Each should describe observable behavior in one to three sentences.
4. **Independent verification:** Agree on an objective check for each requirement. Prefer runnable tests, benchmarks, reference inputs/outputs, or metric scripts. When automation is not reasonable, define a concrete rubric for an independent judge.
5. **Acceptance and limits:** Convert verification into checkable completion criteria. Record time, cost, network, dependency, compatibility, publication, and destructive-action boundaries.
6. **Working location:** For an existing project, use the selected repository and keep coordination artifacts outside it by default. For greenfield work, propose `~/teamwork_projects/<short_name>`. Record whether parallel writers may use isolated copies/worktrees; default to no. Never create or copy a project until the user approves the brief.

If the initial request already answers an item, do not ask it again. Still present the consolidated brief for approval.

## Integrity interview

Do not ask the user to select an abstract mode. Ask which shortcuts, if any, are off-limits:

- copying core logic from an existing open-source implementation;
- using pre-built libraries or frameworks for core functionality;
- delegating core execution to external tools or services;
- reading hidden or evaluation test source to reverse-engineer expected behavior.

Map the answer:

- **development** (default): normal engineering; established dependencies and reuse are allowed. Fabricated results, hardcoded test answers, and facade implementations remain forbidden.
- **demo:** reproducible capability demonstration; additionally forbid copying core logic, external delegation of core work, and test-source reverse engineering as selected by the user.
- **benchmark:** independent evaluation; all four shortcuts are forbidden and the implementation must follow any from-scratch or standard-library-only constraint in the approved brief.

Suggest `demo` for a capability showcase and `benchmark` for a formal evaluation, but let the user's actual restrictions control.

## Verification design

Verification is a forcing function for real iteration, not a ceremonial restatement of the goal. It should be easy to run, difficult to fake, and sufficiently discriminating that an incomplete implementation fails.

Avoid:

- the implementing agent judging itself;
- subjective criteria such as “looks good” without a rubric;
- criteria that cannot be run in the available environment;
- thresholds so broad that a facade passes or so extreme that useful completion is impossible.

Ask whether the user has existing tests, benchmark scripts, reference implementations, datasets, evaluation guidelines, or known-good outputs. Record their paths and provenance.

## Reviewable brief

Present the current `prompt_draft.md` in the conversation for review before requesting approval:

```markdown
# Teamwork Brief: <project>

<One or two sentences describing the outcome, purpose, and audience.>

- Working directory: <absolute path>
- Coordination root: <default ~/.codex/teamwork-runs/<project>-<timestamp>>
- Execution path: <general | iterative | document-review | math-proof | math-proof-large>
- Integrity mode: <development | demo | benchmark>
- Authorization boundaries: <local edits/tests allowed; external/destructive/publication limits>
- Writer isolation: <sequential shared checkout by default | explicitly authorized isolated copies/worktrees>

## Requirements

### R1. <observable requirement>
<What must be true, without prescribing how.>

## Verification resources

- <existing suite, reference, dataset, rubric, or “none supplied”>

## Acceptance criteria

- [ ] AC1: <objective check and expected result>

## Out of scope

- <explicit exclusions>
```

Validate that every requirement has at least one criterion, every criterion has a verification method, the brief contains no invented preference, and the working directory and permissions are unambiguous. Then ask for a single explicit approval such as “Approve and launch this Teamwork run?”

Treat “go”, “launch”, “approved”, or an equally clear confirmation as approval. Requested edits return to Phase 1. Ambiguous acknowledgements do not launch. After approval, copy the exact approved `prompt_draft.md` into the run's immutable `REQUEST.md`; do not reconstruct it from memory.
