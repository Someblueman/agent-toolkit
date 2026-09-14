# Named fanout workflows

Status: design proposal, 14 September 2026. Planning and this document are authorized;
implementation, worker dispatch, worktree creation, and publication are not authorized
by this planning request. Saving or committing this document does not approve the design.

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

Everything below is a recommendation unless marked as verified current behavior.
Exact rosters, routes, limits, and configuration syntax remain proposed.

Recommend named recipes over the existing fanout executor. A recipe defines purpose,
roles, model routes, expected evidence, and the caller's handoff procedure. The executor
runs one bounded round of independently assigned workers. The calling agent handles
decomposition, verification, integration, and any explicitly requested next round.
Do not build a general graph scheduler, recursive agent team, or autonomous repair loop.

## Verified current behavior

- `tools/fanout/bin/fanout` selects one harness/model/prompt/working directory for an
  entire invocation; defaults are four workers, concurrency four, all results required.
  Its separate harness branches construct otherwise similar worker calls. It does not
  currently support a mixed roster or individual work assignments.
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

## Proposed workflows

| Workflow | Initial model/role proposal | What makes it distinct | Completion evidence |
| --- | --- | --- | --- |
| `review-plan` | Agy / Gemini 3.8 Flash High challenges architecture and assumptions; Claude Code / Fable challenges feasibility, missing requirements, and verification | Independent reviews of the same plan and relevant source; each reviewer also reports any critical issue outside its assigned focus | Concrete gaps tied to plan sections or source, consequences, proposed revisions, unresolved assumptions, and disagreement preserved |
| `implement` | Allocate independent work items across Pi / DeepSeek Flash and Claude Code / a configured medium-cost model; allocate according to coupling and risk, not random assignment | Each worker receives one owned work item, its own checkout, acceptance checks, and a shared interface agreement | Task-owned diff/commit, actual checks and results, remaining blockers; caller subsequently verifies the integrated result |
| `bug-hunt` | Pi / DeepSeek traces code paths and coverage; Agy / Gemini High probes boundary cases; Claude Code / Fable examines suspected causes and counterexamples | Independent hypotheses with deliberately different focus; findings must distinguish observation, reproduction, and inference | File/line or stable symbol, trigger, expected/actual behavior, reproduction or explicit evidence gap; caller verifies and deduplicates |
| `critique` | Agy / Gemini 3.8 Flash High challenges assumptions and alternatives; Claude Code / Fable examines usefulness, clarity, completeness, and concrete improvements | Strong models advise the calling agent on its current answer, design, code, or approach; feedback addresses the user's objective and preserves sound work | Specific strengths to retain, prioritized concerns with evidence and suggested improvements, tradeoffs, and uncertainties; caller records its response and verifies any revisions |

These are starting hypotheses for qualification, not model rankings. Keep the model mix
editable without rewriting role instructions. Pin explicit routes in shipped workflows;
where a native alias is used, record both the requested alias and observed model when
available. The exact Fable generation and medium-cost Claude model need selection and
native validation before shipping. Do not silently substitute today's native default.

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

Require both proposed critic roles for full coverage, while retaining partial feedback
when one fails. Separate critique delivery from the caller's subsequent revision and
verification. Default to one critique round. Do not loop until both models approve,
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

Proposed CLI, retaining the existing invocation form:

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

Store canonical named JSON recipes and their role prompts within `skills/fanout/`, with
versioned recipe fields and relative references. The tool reads them from its known toolkit
root; installed skill copies remain installer outputs. Follow the existing package ownership
contract. Keep model selection, role prompts, and result schemas in the same package.

Permit an explicit `--workflow-file /absolute/path.json` for a user's complete custom
recipe. Do not automatically execute repository-local presets, load shell snippets, or
introduce layered global/project/environment merging. Harness adapters accept validated
native fields, not arbitrary argv fragments or executable paths supplied by recipes.

Workflow mode owns its roster: reject ambiguous global `--harness`, `--model`, `--workers`,
`--agent`, and `--min-results` overrides. Concurrency and timeout overrides may lower or
explicitly replace documented limits, and the resolved values must appear in the plan
and packet. Global flags keep their existing meaning outside workflow mode. Add targeted
per-role model overrides only if actual use demonstrates a need beyond an explicit recipe.

## Execution and evidence contract

Normalize resolved work into concrete worker specifications: unique id, role, harness,
requested model/native effort settings, assignment, input identity, working directory,
and deadline. Use one shared semaphore across the entire roster, including retries.
Fail invalid recipes or missing required executable dependencies before dispatch starts.

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

Workflow mode needs a common structured receipt across all harnesses, including Agy.
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

The workflow packet records recipe version/hash, resolved roster, per-worker requested
and observed model (unknown stays null), role, assignment/input hash, checkout/base,
attempt artifacts, native completion, and validated payload. Actual token/cost metadata
can be incomplete; unknown is not zero. No cross-provider dollar cap is promised by v1.
Bound spend operationally through a visible finite roster and deadlines.

Completion rules follow required roles/assignments, not just a count. For `review-plan`,
both distinct review roles are required; two reports from one route cannot satisfy the
other. Implementation requires every assigned item. Bug-hunt requires its configured
perspectives; critique requires both critic roles. Retain partial reports and explicit
missing coverage when any required role fails. Never label a transport failure as
“no issues found” or substitute a cheaper route.

The caller produces the human synthesis: verified findings, disagreements, uncertainties,
and next actions. Do not add a paid judge by default. A stronger follow-up is justified
by a specific unresolved question and runs only within the user's scope and limits.

## Parallel implementation ownership

The calling agent decomposes the request before dispatch. Each assignment states owned
files or modules (including allowed new files), agreed interfaces, acceptance commands,
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

## Cohesive delivery stages and proposed acceptance

1. **Mixed worker dispatch and receipt contract.** Replace homogeneous internal construction
   with resolved worker specifications; add Agy workflow receipts and v4 serialization.
   Prove different executable/model/assignment routes in one run, a shared concurrency cap,
   retained sibling reports on failure, timeout/cancellation cleanup, and unchanged plain
   v3 behavior. Use the existing subprocess fixtures rather than a second simulated runner.
2. **Review recipes and discovery.** Add `review-plan`, `bug-hunt`, `critique`, recipe validation,
   description output, role prompts, and skill routing. Prove invalid/unknown fields fail
   before dispatch, describe performs no launches/writes, missing roles fail completion,
   and model failures cannot become substitutions or false clean reviews.
   For critique, validate actionable feedback fields and permit justified empty lists;
   prove feedback from both critics and their disagreement survive packet ingestion.
3. **Owned implementation.** Add assignment validation and ownership evidence. Exercise
   two workers making disjoint changes in authorized temporary checkouts; reject duplicate
   checkouts, overlapping ownership, and missing dependency prerequisites. Detect an
   out-of-scope edit including an untracked file. Demonstrate caller integration and a
   combined check that can catch incompatible individually passing changes.
4. **Qualify recipes and install.** Run affected suites and repository checks. In a bounded,
   separately authorized live trial, review a plan with seeded consequential omissions;
   hunt a reproduced defect plus a plausible false lead; deliver two real independent
   implementation items through integration; and critique a draft containing a real gap
   alongside a sound decision that should be preserved. Observe the calling agent consume
   the packet, make an evidenced correction, preserve sound work, and explain any rejected
   suggestion. Also verify missing context is surfaced and no second round starts implicitly.
   Compare verified coverage, false positives, useful changes, latency, and available
   cost against plain fanout. These small trials
   qualify usability, not a universal model ranking. Refresh the installed skill through
   the normal installer and pass its read-only comparison.

No trials or workflow implementation have been executed as part of this design request.

## Remaining decisions and handoff

- Recommend the initial model/role mixes above. Confirm the exact Claude Fable route and
  the medium-cost implementation model during qualification; Gemini's requested high
  route resolves to the locally listed `gemini-3.8-flash-high`.
- Recommend deterministic required-role completion, caller-owned synthesis, and caller-owned
  checkout preparation/integration. A fully unattended multistage workflow engine is a
  separate scope decision, not implied by named fanout workflows.
- No workflow-wide price ceiling has been specified. Keep limits explicit and costs
  observational until a real common enforcement mechanism exists.

Working repository: `/Users/sws/Code/agent-toolkit`. Only this plan is task-owned in the
planning iteration. Other quality-hook work appeared concurrently; preserve it and stage
only this document. No runner, app task, agent, or automation should start from this plan
until the user authorizes implementation or a concrete trial.
