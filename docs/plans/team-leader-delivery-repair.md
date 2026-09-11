# Team leader delivery repair

Status: proposed, 12 September 2026. Investigation and this document are authorized;
implementation, installation, and changes to the running Hydra leader are not.

## Outcome and scope

Make a delegated assignment converge to a usable, verified, locally committed result
without repeated user intervention, avoidable worker churn, or repeated invalid checks.
Keep the leader as the user's point of contact and accountable reviewer.

Implement the repair in the canonical `skills/team-leader/` package, with related
documentation and affected tests. Keep it usable across repositories. Hydra is the
observed failure case and a possible later acceptance trial, not a dependency.

The user clarified the intended model: recurring app tasks together with native subagents.
That hybrid is confirmed intent. The routing and ownership rules below are proposed ways
to implement it; they have not yet been approved for execution.

Preserve the current orchestration-only leader role, independent review, repository
acceptance requirements, publication boundaries, and default four-hour recovery window.
Replace the blanket fresh-worker default with explicit lifecycle rules: continuing an owned
workstream uses its recurring task; a new bounded specialist assignment uses a fresh
subagent. Keep the prohibition on opportunistically repurposing unrelated old tasks.
Changing the leader into an implementer is a separate design choice. No new scheduler,
agent framework, global permission changes, or increased agent limits are proposed.

## Verified diagnosis

Inspected task: `01a08fe3-16c1-7212-8401-cb2c1ea37c8d`, titled
“extend the recovery, and help drive these to completion”, in `/Users/sws/Code/hydra`.
Observations cover 11 September through 23:49 UTC; the task was still active, so these are
dated observations rather than its eventual outcome.

The strongest explanation is excessive coordination around incomplete deliverables and
late discovery of acceptance failures. Recovery alone does not solve that problem.

| Observed evidence | Implication |
| --- | --- |
| In the I2/I3 window from 18:15 to 22:19 UTC, the leader issued 38 native spawn attempts, 72 follow-up calls, and 112 worker messages. Twenty calls failed with `agent thread limit reached`: 12 spawns, six follow-ups, two messages. | Capacity failures affected continuation as well as creation. These are call counts, not unique successful workers or a measured percentage of wasted time. Repeated dispatch attempts need a different response. |
| At 19:45:23 UTC the user authorized old-agent cleanup and new tasks. At 19:45:49 and 19:50:56 the leader still described that permission as pending. | Authorization reconciliation failed despite the skill already requiring it. The leader should update the current decision before acting on older questions. |
| The public producer and consumer disagreed on boolean versus string `navigable`; approval identities bound to the wrong step/attempt; the native view initially lost unseen state. | File ownership alone did not establish a correct shared interface or complete user behavior. |
| A purported 513-unique-item fixture reused an identity; refresh tests could match an older frame; a recipe-change test accepted arbitrary JSON. | Passing counts did not establish the assigned behavior. Handoff evidence needed to demonstrate a discriminating stimulus and observation. |
| An independent native check ran an older binary; another omitted the required crash fixture. The parent corrected both. | Build identity and invocation environment were missing from usable handoffs, causing avoidable reruns and false findings. |
| Later public tests found an actual cancellation leak. The first measurement pass did not exercise several labelled cases. | Independent review remains valuable. Public behavior and measurement feasibility were tested too late. |
| Five accepted local checkpoints were recorded, including `2af1dce`, `e20fb95`, `89dc61e`, and `f74aa9d`; I2/I3 remained unfinished at the first deadline. | This was real progress with costly rework, not total inactivity. Earlier success does not establish whole-item acceptance. |

The current skill reinforces the bottleneck: `SKILL.md` requires delegating all project
changes, tests, repairs, commits, and integration, including when slots are full. It also
defaults to fresh workers for new assignments without clearly distinguishing a workstream
from its individual implementation steps. Continuing an existing workstream is allowed,
but the ambiguous unit of assignment encourages routing every bounded step to another
subagent. Recurring app tasks consequently become an exception or a capacity workaround
instead of the durable owners of larger work. This conflicts with the user's clarified
hybrid intent. The earlier prohibition on using arbitrary old tasks must not prevent
continuation of this leader's deliberately established workstream tasks.

The roster had grown to 511 lines, 34 third-level headings, and 64 evidence strings spanning
earlier CI/publication work and current interaction work. It retains useful evidence, but
the current decision and completion state are buried among historical milestones.

### Recovery findings and limits

- Repository baseline: `9f04a54` on `main`, initially clean. The read-only Codex installer
  comparison reports the installed team-leader package unchanged.
- All ten real completion CLI tests pass. They exercise status, bounds, interruption,
  inert sessions, and hook installation; they do not exercise delegated delivery quality.
- The inspected heartbeat is `ACTIVE`, targets the correct task and roster, and uses the
  expected five-minute schedule. The renewed deadline is 12 September 02:24:03 UTC
  (03:24:03 London). No automation was changed during this investigation.
- The current roster event log contained 22 `Recovery` entries and no `Stop` or `Interrupt`
  entries. These entries prove explicit checker calls, not scheduled delivery or native
  hook execution. Neither is independently established for this current task here.
- Read-only calls to the pure evaluator confirmed that any nonempty `waiting_on` list
  bypasses unchanged-progress counting, rewritten progress prose resets that count, and
  `complete` with one evidence string is accepted structurally. These are trust boundaries,
  not proof that this leader falsely completed or bypassed a stop.
- Official Codex configuration describes capacity in terms of open spawned-agent threads,
  not just actively working assignments. The effective cause of this session's intermittent
  capacity failures is unresolved; do not assume a finished or interrupted agent releases
  capacity. See the [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

## Proposed repair

### 1. Establish one current delivery contract

Before dispatch, derive the selected outcome and its real acceptance from the repository.
Use the existing roster for a short current block: authorized scope and exclusions,
unresolved user decisions, complete behavioral slices, owners, acceptance commands and
fixtures, and the next dependency. Update this block when user steering arrives, before
responding to any older pending question. Record where the authorization came from.

For each slice, specify what the user can do after it lands and the failure cases that
would disprove it. Identify required performance or visual evidence at this point and
check whether its fixture/tooling exists. Do not discover that an entire measurement
harness is missing at the final acceptance stage.

Maintain the current block in place. Keep earlier accepted milestones as concise references
outside current completion evidence; do not append a new operational plan at every handoff.
Preserve historical evidence and decisions without treating earlier authorization as
permission for a new objective.

### 2. Separate recurring task ownership from specialist assignments

Use this routing model explicitly:

| Unit | Owner and lifetime | Continuation |
| --- | --- | --- |
| Selected project outcome | The leader coordinates scope, dependencies, acceptance, and recovery. | Keep the same leader and current roster. |
| Larger workstream with related implementation cycles | An authorized app task owns its deliverables, implementation, tests, repairs, and scoped commits. | Return to the same recorded task for subsequent slices within its authorized scope. A finished turn or committed slice does not retire it. |
| Bounded specialist job | A native subagent investigates, writes an independently owned change, reproduces a defect, tests, or independently reviews a named result. | Continue the same specialist for repairs to that job; use a fresh one for a different job. Its handoff does not replace the workstream owner. |

Here, recurring means returning to the same task when related work is ready. It does not
add a scheduled automation to every worker. Keep the existing single leader heartbeat.
Do not create idle role tasks speculatively: establish an app task when an authorized
workstream needs one, then retain its identity and ownership through that workstream.

Record the workstream owner separately from any temporary specialist and its current file
ownership. The leader routes a related next step to the existing owner before considering
a fresh dispatch. Reopening the task is subject to current scope and live ownership, not a
requirement to obtain repeated permission for the same authorized work. Reusing that task
does not authorize a new roadmap item, worktree, publication, or access to unrelated work.

Do not introduce a mandatory second orchestration layer. The app task implements its
workstream. The leader can assign a specialist alongside it only with a specific boundary
and useful independent work; no writer may simultaneously own the same files. Any delegated
subagent use must remain inside the agreed team concurrency and ownership limits.

For example, a task owning the selected interaction work keeps its identity while it
implements an attention slice, repairs review findings, commits it, and moves to the next
already-authorized navigation slice. A temporary reviewer independently checks the named
revision. The leader sends resulting defects back to the interaction task, rather than
creating separate replacement implementation, repair, and commit tasks. An unrelated old
CI task is not reused merely because it exists.

Assign one implementation owner the related source, tests, necessary documentation, and
repairs for a usable slice. Use separate workers only for work that can make independent
progress with nonoverlapping ownership. Do not split writing and basic self-verification
into a relay of mandatory specialist tasks.

For a producer/consumer feature, agree the existing wire contract and prove one public
producer-to-consumer path before widening coverage. Parallel ownership of different files
does not remove this dependency. For example, an attention slice must carry the same exact
identity from the public projection into the TUI and prove client-local acknowledgement;
“add the parser” alone is not its acceptance endpoint.

For an isolated bounded change without a larger workstream, a native specialist can own
the complete change directly. Do not force it through an app task merely to fit the table.
After acceptance, the implementation owner can make its authorized scoped commit under the
serialized Git lease; a commit-only worker is unnecessary. Preserve the existing default
of at most three active workers, not a target to keep three busy. Separately record actual
runtime capacity errors; a saved recurring task is not necessarily actively executing.

### 3. Gate handoffs on usable evidence and stop repetitive repair dispatch

An implementation handoff is ready for independent review only after its owner has run the
assigned behavioral checks and relevant quality gates, or reported a concrete external
blocker. A partially implemented path or a missing assigned test remains the owner's work.
Require a compact handoff with changed scope, source revision or dirty-file fingerprint,
actual binary/build path, exact command and required environment, results/log location,
and remaining gaps. Reuse native repository commands rather than reconstructing their
environment separately for every reviewer.

The leader personally checks whether the evidence covers the contract before dispatching
review. A count alone is insufficient: a malformed-input case must start from valid state
and show rejection of the new input; a refresh case must observe the new refresh; a
measurement must actually apply its labelled stimulus and record missing observations.

After a second materially incomplete repair handoff for the same gap, stop sending another
incremental checklist. Reconcile the actual diff, missing contract, test validity, and owner
capability, then issue one consolidated remaining assignment. Continue with the same owner
when viable; replace only after confirming it cannot still write and preserving its edits.
This is a change-of-approach trigger, not permission to drop requirements or stop early.

Use one focused independent review per cohesive accepted slice. Continue that review for
the same assignment's repair deltas. Reuse evidence when its source, dependencies, command,
environment, and acceptance still apply; rerun affected checks after changes. Run broader
combined acceptance when required by the repository or integration risk. Do not repeatedly
restart the full matrix merely because another worker returned.

### 4. Make capacity failures a state transition

On the first capacity failure, record the failed operation and reconcile live ownership.
Do not retry spawn/message/follow-up with alternate names or agent types without evidence
that capacity or the relevant worker state changed. A failed dispatch is not a live worker.

Use only lifecycle operations actually exposed by the runtime. Do not invent a close tool
or assume interrupting or archiving releases a slot. Continue the same viable assignment
when supported. An existing app-task owner remains responsible for its workstream when a
temporary specialist is unavailable; return work within its ownership to it once conflicting
writers are ruled out. If the blocked operation is independent review, the author cannot
substitute for that reviewer. For a misplaced larger assignment, use an already-authorized
app task when that lifecycle fits, explicitly record the transition, and prevent overlapping
writers. Otherwise wait for a meaningful state change or report the exact missing
capability/authorization once while continuing independent authorized work.

### 5. Keep recovery honest and qualify delivery separately

Retain the existing bounded heartbeat and cancellation rules. Reconcile live worker state
before writing `waiting_on`; count progress only when new evidence closes or advances a
specific requirement. Recovery keeps an unfinished leader available; it cannot validate
semantic completion or guarantee throughput.

Do not add a new durable schema or evidence-validation subsystem in the first repair.
The current evaluator's trust limits are explicit above, and no reproduced runtime bug
requires that expansion. Update its continuation message only where necessary to reflect
the revised handoff/capacity behavior; retain its CLI and version-1 roster contract.
If a live trial still demonstrates false progress or stale-wait recovery, design a bounded
runtime correction against that reproduction rather than adding guessed liveness fields.

## Work stages and acceptance

1. **Revise the canonical workflow.** Update `skills/team-leader/SKILL.md` and
   `references/completion.md`; align `scripts/completion.py` continuation wording only if
   needed. Update `docs/catalog.md` or adapter documentation only where behavior descriptions
   become inaccurate. Rewrite ownership, dispatch, follow-up, reviewer reuse, and recovery
   together so no blanket fresh-assignment rule contradicts recurring workstream ownership.
   Keep the policies coherent and concise. Do not edit installed outputs directly.
2. **Verify compatibility.** Run the ten completion tests, affected configured lint/format
   checks if Python changes, relevant installer tests, and `git diff --check`. Exercise
   temporary installation and repeat installation; compare the live install read-only.
   If installer code changes, run the repository's full required installer acceptance.
   Refresh the live install only when authorized. Unit and installation success must not
   be reported as proof of improved delivery.
3. **Observe a bounded real assignment after explicit execution/trial authorization.**
   Use a selected cohesive slice with a real CLI/TUI boundary, a meaningful negative case,
   independent review, and a local commit endpoint. Prefer existing remaining work if still
   suitable; re-inspect Hydra first because it is changing. Do not manufacture another
   feature or interrupt its active owners just to test the workflow.

The delivery trial must show:

- A workstream task keeps the same actual task ID through a slice, any repair, and the next
  related already-authorized slice. A temporary specialist can finish without retiring or
  replacing that owner. No arbitrary old task is repurposed and no new scope is inferred.
- Current user authorization is reflected before the next dependent action; a status query
  alone does not expand scope or renew recovery.
- A cohesive owner returns public-path and failure evidence plus applicable quality results;
  any repaired handoff reaches re-verification without another user nudge.
- Review uses the designated current artifact and canonical environment. Repeated checks
  have a recorded source change, failed check, unresolved risk, or repository requirement.
- If capacity failure occurs, there is no blind retry before a meaningful state change.
  If it does not occur, label the runtime capacity path untested rather than simulating a
  success claim. Do not intentionally exhaust the user's active session.
- The leader personally accepts the final combined evidence and the authorized commit,
  preserves unrelated work, and stops recovery at the real endpoint.
- Report elapsed time to the first accepted slice and final endpoint, dispatch/repair counts,
  capacity failures, and causes of repeated checks. The Hydra counts above are a diagnostic
  baseline, not a matched speed benchmark. Do not promise a numeric speedup without one.

## Handoff and next decision

The confirmed direction is recurring app tasks plus bounded specialist subagents. The
recommended implementation makes the workstream task the continuing delivery owner and
uses specialists where they add independent value. It also repairs authorization
reconciliation, handoff quality, and capacity handling. A working leader that directly
implements remains an optional separate choice; the hybrid does not require that change.

This plan is not approved for execution. Do not message the Hydra leader, change its roster
or heartbeat, clean up its workers, edit its checkout, or install the proposed workflow from
this planning request. No subagents were launched for the investigation.

Evidence locations for later verification:

- Toolkit: `skills/team-leader/{SKILL.md,references/completion.md,scripts/completion.py}`,
  `scripts/test_leader_completion.py`, and `docs/team-leader-completion-trial.md`.
- Current Hydra records: `/Users/sws/.codex/team-leader/01a08fe3-16c1-7212-8401-cb2c1ea37c8d/`,
  especially `roster.md`, `interaction-handoff.md`, `interaction-review/native-parent-final.md`,
  `interaction-review/native-checkpoint-final-review.md`, and `completion-events.jsonl`.
- Public task messages were checked against the locally saved 11 September conversation;
  the app's recent-task view did not expose the newest active turn's messages during the
  initial inspection. The newest authorization and status came from the saved public messages.
