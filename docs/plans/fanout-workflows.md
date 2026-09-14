# Named fanout workflows

Status: implemented, 14 September 2026, following the user's request to implement this
plan end to end. The CLI, canonical skill package, installer refresh, automated checks,
and bounded live trials are complete. Provider qualification has the specific limits
recorded in [delivery evidence](../fanout-workflows-validation-20260914.md).

## Outcome and decisions

Let a calling agent turn requests such as “fanout review this plan”, “fanout implement
these changes”, “fanout hunt bugs here”, or “get constructive criticism of my work”
into an explicit team with suitable models, distinct assignments, evidence requirements,
and bounded execution.

User-agreed direction:

- Workflows should select different model mixes for different kinds of work, including
  stronger models for plan review and a mixture for bug hunting.
- Implementation means several workers implement separate owned parts, rather than
  only advising the caller or appointing one implementation worker.
- Constructive criticism should use strong models to give actionable feedback directly
  to the agent that invoked fanout, helping that agent improve its current work.
- Workflows must be model-agnostic. Users must be able to add, replace, or remove models
  through configuration, including adding a future GLM-5.3 reviewer without code or prompt edits.

The sections below record the delivered design and its operating contract.
The [workflow guide](../../skills/fanout/references/workflows.md) is the usage reference.

Use model-agnostic workflow recipes over the existing fanout executor. A workflow
defines purpose, roles, expected evidence, and the caller's handoff procedure. A separate
configurable roster assigns those roles to harnesses and models. The executor
runs one bounded round of independently assigned workers. The calling agent handles
decomposition, verification, integration, and any explicitly requested next round.
Do not build a general graph scheduler, recursive agent team, or autonomous repair loop.

## Starting contracts preserved or extended

- `tools/fanout/bin/fanout` selects one harness/model/prompt/working directory for an
  entire invocation; defaults are four workers, concurrency four, all results required.
  That plain invocation remains available. Workflow mode now resolves a mixed roster
  or individual work assignments through shared native dispatch.
- Agy runs in plan/sandbox mode and returns bounded string findings/uncertainties.
  OpenCode, Muse, Pi, and Claude Code use a completed/blocked/failed receipt with a
  task-specific JSON object. Merely changing model defaults cannot make these contracts
  express equivalent workflow evidence.
- `tools/fanout/lib/structured_worker.py` owns shared receipt validation and subprocess
  deadlines/cancellation. Existing harness adapters must remain the execution boundary.
- `packet.json` schema version 3 has run-level harness/model and numeric quorum. This is
  a documented cross-process interface, even though the inspected repository consumers
  are primarily tests, docs, and skill instructions. External consumers are unknown.
- Pi and OpenCode default to `opencode-go/deepseek-v4.1-flash`. Claude Code and Muse use
  native defaults unless overridden. All five harnesses are present in the fanout skill.
- Live `agy models` lists `gemini-3.8-flash-high` and `gemini-3.8-flash-medium`, not the
  abbreviated `gemini-3.8-high`. Listing establishes a route, not task quality or a live
  inference qualification. The prior Claude live test reported `claude-fable-5-1`.
- Agy and Claude expose native effort controls. Model names and effort are harness-specific;
  do not assume a universal “high” suffix works everywhere. See the native
  [Claude model configuration](https://code.claude.com/docs/en/model-config).
- `skills/team-leader/SKILL.md` already describes ownership in authorized worktrees and
  caller-owned integration. Reuse those principles; do not introduce another team lifecycle.
- Fanout process isolation is not filesystem isolation. Pi/Claude retain normal tools and
  settings. Even read-oriented tasks can create files through tools or plugins. Claude
  print mode also skips native workspace trust prompts.

## Delivered workflows

| Workflow | Model-independent assignments | What makes it distinct | Completion evidence |
| --- | --- | --- | --- |
| `review-plan` | Reviewers examine architecture, assumptions, feasibility, missing requirements, and verification; optional individual focus comes from roster configuration | Independent reviews of the same plan and relevant source; all reviewers can flag critical issues outside their focus | Concrete gaps tied to plan sections or source, consequences, proposed revisions, unresolved assumptions, and disagreement preserved |
| `implement` | Implementers receive separate owned work items and agreed interfaces; caller selects a configured roster member for each item | Each worker has its own checkout, acceptance checks, and shared interface agreement | Task-owned diff/commit, actual checks and results, remaining blockers; caller subsequently verifies the integrated result |
| `bug-hunt` | Investigators trace code paths, probe boundaries, and test suspected causes; optional individual focus comes from roster configuration | Independent hypotheses with deliberately different focus; findings distinguish observation, reproduction, and inference | File/line or stable symbol, trigger, expected/actual behavior, reproduction or explicit evidence gap; caller verifies and deduplicates |
| `critique` | Critics assess assumptions, alternatives, usefulness, clarity, and completeness; optional individual focus comes from roster configuration | Models advise the calling agent on its current answer, design, code, or approach against the user's objective | Strengths to retain, prioritized concerns with evidence and suggested improvements, tradeoffs, and uncertainties; caller records its response and verifies revisions |

Ship editable starter rosters: Gemini High plus Claude Fable for plan review and critique;
a DeepSeek/Gemini/Claude mix for bug hunting; a DeepSeek and medium-cost Claude pool for
implementation. These are editable starter defaults, not required model families or
proven rankings. Any supported harness/model can fill the appropriate workflow role.
An added reviewer gets the workflow's complete review instructions automatically; a focus
is optional and does not require inventing a new role or updating a prompt template.

Keep explicit model routes in roster data. Record requested aliases and observed models
when available. Live trials observed `claude-fable-5-1` and the `sonnet` alias resolving
to `claude-sonnet-5`; provider availability is not guaranteed. Model names must
not appear in workflow logic, result schemas, completion rules, or role prompts.

Do not route two workers through Pi and OpenCode to the same DeepSeek model and describe
that as independent model-family coverage. Harness diversity and model diversity are
separate facts. Extra duplicate workers should buy a deliberate additional perspective.

For bug hunting, a review round can complete with no verified bugs or unresolved leads;
finding a bug is not required for a successful run. For plan review, completing the
review is distinct from approving the plan. Agreement between workers never proves a claim.

### Constructive criticism returned to the calling agent

Route “constructive criticism”, “critique my approach”, and “get stronger-model feedback”
to `critique`. Use `review-plan` for the narrower question of a plan's readiness for
execution. Critique can also apply to a draft answer, partial implementation, proposed
decision, or synthesis from an earlier fanout run; it does not require a plan document.

The caller supplies the user's objective and constraints, the actual work being critiqued,
relevant evidence, a concise explanation of its choices, and any specific uncertainty.
Critics receive the same material independently. They cannot assume access to the calling
agent's conversation or infer unseen work from its self-description. Missing material
must be identified, not replaced with invented context.

Return structured feedback addressed to the caller: `strengths` worth preserving,
`improvements` with priority, target passage/file/decision, observation, rationale or
evidence, a concrete suggested change and its tradeoff, plus `uncertainties`. Distinguish
required corrections from optional suggestions. No quota of criticisms or praise;
empty lists are valid when justified. Evaluate the work against its purpose, not a
generic preference for more complexity, more tests, or more process.

The caller reads the critique packet before its next revision or final response. For
each material suggestion it records accept, reject, or defer with a short reason; it
checks claims and applies accepted improvements within its existing authorization.
Suggestions do not expand task scope or grant permission to edit, publish, or change
policy. For read-only work, return recommendations rather than applying edits.
The user sees the consequential improvements and unresolved disagreements, without
requiring a transcript of the exchange. Preserve the detailed disposition with the run
artifacts so feedback consumption is reviewable.

Require feedback from every configured critic for full coverage by default, while
retaining partial feedback when one fails. The critic roster may contain any positive
number of members; no Gemini/Claude pair is mandatory. Separate critique delivery from
the caller's subsequent revision and verification. Default to one critique round.
Do not loop until the critics approve,
allow recursive fanout, or transfer final responsibility to a critic.

## Product surface and configuration

Natural language remains the main entry point through `skills/fanout/SKILL.md`:

> “Use fanout to review docs/plans/cache.md.”
>
> “Use fanout to implement this approved plan across separate owned parts.”
>
> “Use fanout to hunt bugs in the retry and cancellation paths.”
>
> “Get constructive criticism from strong models on your current approach, then use
> that feedback to improve it.”
>
> “Add GLM-5.3 through my Pi provider to future plan-review runs.”

The last request edits the selected user roster configuration, preserving other members
and workflows. It does not alter workflow instructions or launch a review. Resolve an
ambiguous provider route before saving it; do not guess an endpoint or provision credentials.

CLI, retaining the existing invocation form:

```sh
tools/fanout/bin/fanout request.md --workflow review-plan --describe
tools/fanout/bin/fanout request.md --workflow review-plan --output /tmp/plan-review
tools/fanout/bin/fanout request.md --workflow bug-hunt --output /tmp/bug-hunt
tools/fanout/bin/fanout critique-context.md --workflow critique --output /tmp/critique
tools/fanout/bin/fanout request.md --workflow implement \
  --assignments /tmp/owned-work.json --output /tmp/implementation
```

`--describe` resolves and displays the roster, roles, native model/effort options,
workspaces, deadlines, concurrency, and completion rules without spawning workers or
creating output/worktree state. It can report missing executables; it cannot promise
authentication, quota, or model availability without a real provider call. This is an
inspection feature, not a mandatory approval step for already-authorized execution.

### Configuring models independently

Store canonical workflow definitions, role prompts, schemas, and starter rosters together
under `skills/fanout/`, but as separate files. The tool reads those canonical sources from
its known toolkit root. Installed copies remain installer outputs. User roster configuration
lives outside the package and must survive toolkit updates without being overwritten.

User file: `${XDG_CONFIG_HOME:-~/.config}/agent-toolkit/fanout.json`, resolving
`~` as the user's home, not as literal text. `--config /path/to/fanout.json` selects an
alternative complete user configuration instead of that default path. Do not stack both
files or automatically discover repository-local configuration.

A user file overrides only the workflows it names. For each named workflow its `members`
list replaces the entire starter roster; never concatenate, merge by array position, or
implicitly retain a removed default. Unspecified workflows use shipped starter rosters.
A present but invalid file fails visibly; only an absent default file uses all defaults.
An explicitly selected missing file is an error. Display the effective config source in
`--describe` and retain its resolved content/hash in the run packet.

Illustrative user config after adding GLM to plan review:

```json
{
  "version": 1,
  "workflows": {
    "review-plan": {
      "members": [
        {"id": "gemini", "harness": "agy", "model": "gemini-3.8-flash-high"},
        {"id": "claude", "harness": "claude", "model": "claude-fable-5-1"},
        {"id": "glm", "harness": "pi", "model": "YOUR_PROVIDER/glm-5.3"}
      ]
    }
  }
}
```

`YOUR_PROVIDER/glm-5.3` is a placeholder for a future authenticated native route, not a
claim that this model/provider combination is available today. Adding this member is the
whole workflow configuration change once the chosen harness supports that route. No
fanout code, skill instructions, schemas, or completion logic should need editing.

Members have a unique stable id, harness, native model route, optional supported native
settings (effort or OpenCode agent profile), and optional focus. The workflow supplies
the common role and evidence contract.
Same-harness different-model members and repeated models with distinct ids/focus are
valid. Do not maintain an allowlist of model names in fanout: adapters pass opaque native
routes through. Validate harness support and configuration shape locally; model/provider
availability remains a native runtime concern and cannot be established by a syntax check.
Adding an entirely new harness still requires an adapter; adding a model to an existing
harness must not. Never embed credentials, arbitrary argv, or executable paths in rosters.
Respect harness capabilities: a read-only Agy worker cannot fill an implementation
assignment. Reject incompatible assignments before dispatch rather than changing permissions.

For `implement`, the roster is the available implementer pool. Each work assignment names
one member id; only assigned items spawn workers. An unselected pool member is not a
missing result. For the other workflows, each configured member spawns one worker with
the shared target plus its optional focus. Validate unique ids and nonempty rosters.

Workflow mode owns its roster: reject ambiguous global `--harness`, `--model`, `--workers`,
`--agent`, and `--min-results` overrides. Concurrency and timeout overrides may explicitly
replace documented limits; record resolved values in description output and packets.
Global flags keep their existing meaning outside workflow mode. Custom workflow semantics
and a configuration editor UI are deferred; ordinary JSON edits and agent-assisted roster
updates satisfy the requested model configurability without copying whole recipes.

## Execution and evidence contract

Normalize resolved work into concrete worker specifications: unique id, role, harness,
requested model/native effort settings, assignment, input identity, working directory,
and deadline. Use one shared semaphore across the entire roster, including retries.
Fail invalid recipes, rosters, assignment references, or missing required executable
dependencies before dispatch starts. Resolve configuration once per run so an edit during
execution affects the next invocation, not workers already scheduled.

Each worker receives the shared task plus its role and individual assignment. A recipe
may reuse a role for multiple owned implementation items; the number of implementation
workers comes from the actual independent items, not a fixed “four implementers” default.
Unsupported model/effort combinations fail clearly; do not silently discard options or
fall back to another model. Keep bounded native retries visible; never automatically
resubmit a mutation-capable task after transport ambiguity.

Bind reviews to the same target artifact bytes and repository revision/dirty-state identity
where applicable. If inputs change during a round, record the different inputs and do not
present them as one coherent review. Qualify native effort forwarding without changing
the user's persistent model/effort settings; reject unsupported ephemeral selection.

Workflow mode uses a common structured receipt across all harnesses, including Agy:
`worker_id`, `outcome`, `summary`, and a direct `payload` object. Plain mode retains its
existing receipt shapes. Live qualification exposed escaped JSON-string failures, so
workflow receipts deliberately avoid JSON inside a string; there is no fallback decoder.
The workflow stdout/stderr acceptance threshold is 8 MB, compared with plain mode's
unchanged 1 MB, because native incremental JSON events can exceed 1 MB for a valid report.
Supply Agy a workflow receipt schema in that mode; do not infer structured evidence by
parsing its existing free-form findings strings. Validate each workflow's payload fields
after the outer receipt, including worker identity and outcome. Native adapters should
translate protocols, not decide whether an engineering claim is true.

Preserve plain fanout's documented version-3 output and flags. Introduce an explicit
version-4 workflow packet because heterogeneous rosters and workflow completion have
different semantics. Share execution internally; use deliberate output serialization,
not duplicated runners or heuristic fallback decoders. Update skill ingestion and docs
for both contracts and test unchanged v3 behavior. Revisit universal v4 migration only
with an explicit external-consumer migration decision.

The workflow packet records recipe version/hash, selected user configuration/hash,
resolved roster, per-worker requested and observed model (unknown stays null), role,
assignment/input hash, checkout/base,
attempt artifacts, native completion, and validated payload. Actual token/cost metadata
can be incomplete; unknown is not zero. No cross-provider dollar cap is promised by v1.
Bound spend operationally through a visible finite roster and deadlines.

Completion derives from the resolved roster and assignments, never hard-coded model
names, families, or counts. In review and critique workflows, every configured member is
required by default. Adding a third GLM reviewer automatically requires its receipt;
removing a reviewer removes that requirement. Two receipts from one member cannot fill
another member's slot. Implementation requires every assigned item, regardless of which
pool member produced it. There is no minimum of two models: a one-member roster runs and
is honestly described as one perspective. Preserve per-member provenance and do not
claim model diversity just because a numeric count was met.

Retain partial reports and explicit missing member/assignment coverage when any required
worker fails. Never label a transport failure as “no issues found” or substitute another
route. Configurable partial quorum can be considered later; v1 uses all resolved workers
without introducing model-specific completion rules.

The caller produces the human synthesis: verified findings, disagreements, uncertainties,
and next actions. Do not add a paid judge by default. A stronger follow-up is justified
by a specific unresolved question and runs only within the user's scope and limits.

## Parallel implementation ownership

The calling agent decomposes the request before dispatch. Each assignment names its
configured implementer member and states owned files or modules (including allowed new
files), agreed interfaces, acceptance commands,
dependencies, an explicit working directory, and base revision. Independent items run
together; dependent items run in subsequent caller-controlled rounds.

Require separate Git worktrees/checkouts for concurrent writers. Creating those worktrees
requires applicable session authorization and happens in the caller's preparation, not
implicitly from a recipe name. Existing authorized worktrees may be supplied. Fanout
validates distinct resolved checkout paths, compatible bases, non-overlapping ownership,
and a clean starting state; a file list alone does not provide isolation. Shared-file
changes belong to one worker or the integrator, not several concurrent workers.

Before/after manifests and Git diffs must include untracked files and removals. Detect
edits outside ownership and mark that assignment nonconforming; preserve the evidence
without resetting or deleting work. This is detection, not an OS permission boundary.
Submodules, symlink escapes, ignored build products, and external side effects require
an explicit supported boundary during implementation; do not claim universal write isolation.

Workers follow applicable commit policy and never push or merge. The caller reviews
diffs, integrates serially into the authorized destination, resolves conflicts, and runs
combined acceptance checks. Reviewers examine a stable integrated candidate after edits
finish. An implementation fanout packet means assigned work was delivered; the caller
must not announce feature completion before integration and final verification succeed.

## Delivery stages and acceptance criteria

1. **Mixed worker dispatch and receipt contract.** Replace homogeneous internal construction
   with resolved worker specifications; add Agy workflow receipts and v4 serialization.
   Prove different executable/model/assignment routes in one run, a shared concurrency cap,
   retained sibling reports on failure, timeout/cancellation cleanup, and unchanged plain
   v3 behavior. Use the existing subprocess fixtures rather than a second simulated runner.
2. **Review recipes and discovery.** Add `review-plan`, `bug-hunt`, `critique`, recipe validation,
   description output, role prompts, and skill routing. Prove invalid/unknown fields fail
   before dispatch, describe performs no launches/writes, missing roles fail completion,
   and model failures cannot become substitutions or false clean reviews.
   Prove roster overrides replace only the named workflow, explicit config selection
   replaces the default user file, and malformed/empty/duplicate-id configurations fail
   before dispatch. Append a synthetic future model route through an existing harness:
   `--describe` and execution must include it without changing code or prompts. Remove
   and replace members and verify both dispatch and completion follow the resolved roster.
   Prove other workflow defaults and user edits survive a toolkit refresh. For implementation,
   reject references to absent roster members and do not spawn unassigned pool members.
   For critique, validate actionable feedback fields and permit justified empty lists;
   prove feedback and disagreements from a configurable roster survive packet ingestion.
3. **Owned implementation.** Add assignment validation and ownership evidence. Exercise
   two workers making disjoint changes in authorized temporary checkouts; reject duplicate
   checkouts, overlapping ownership, and missing dependency prerequisites. Detect an
   out-of-scope edit including an untracked file. Demonstrate caller integration and a
   combined check that can catch incompatible individually passing changes.
4. **Qualify recipes and install.** Run affected suites and repository checks. In the authorized bounded live trials, review a plan with seeded consequential omissions;
   hunt a reproduced defect plus a plausible false lead; deliver two real independent
   implementation items through integration; and critique a draft containing a real gap
   alongside a sound decision that should be preserved. Observe the calling agent consume
   the packet, make an evidenced correction, preserve sound work, and explain any rejected
   suggestion. Also verify missing context is surfaced and no second round starts implicitly.
   Compare verified coverage, false positives, useful changes, latency, and available
   cost against plain fanout. These small trials
   qualify usability, not a universal model ranking. Include one available additional model
   via configuration only and verify it returns the same workflow contract. Future GLM
   availability is not a release dependency; fixture coverage proves opaque route forwarding.
   Refresh the installed skill through
   the normal installer and pass its read-only comparison.

All four stages are implemented. Full repository quality checks passed, including 89
fanout tests, real subprocess concurrency/cancellation tests, temporary Git ownership and
integration checks, and repeated temporary installation preserving user configuration.
The normal Codex installation was refreshed and its read-only comparison passed.
See [delivery evidence](../fanout-workflows-validation-20260914.md) for live packets,
caller critique dispositions and revisions, integration checks, and provider failures.

## Boundaries and follow-up

- Models and their availability remain provider concerns. Agy hit account quota during
  final receipt qualification; OpenCode produced one valid and one malformed final-format
  plan-review report. Partial coverage remained explicit. No silent substitution occurs.
- Workflow completion requires all resolved workers. Synthesis, worktree preparation,
  integration, and verification remain the calling agent's responsibility. A fully
  unattended multistage engine is outside this change.
- No workflow-wide price ceiling is enforced. Costs are observed native estimates and
  can be partial; finite worker counts, deadlines, and output acceptance limits bound runs.
- Filesystem checks compare endpoints and preserve violations for inspection. They are
  not an OS sandbox and do not cover transient reverted edits, Git metadata, or external
  side effects. Implementation rejects symlinks and submodules.
- Future GLM support needs an available native route and a roster entry. No workflow
  redesign, prompt edit, or schema change is required.

Working repository: `/Users/sws/Code/agent-toolkit`. This implementation is committed
under repository policy; pushing remains a separate explicit user action.
