---
name: team-leader
description: Lead project work through recurring Codex app tasks and bounded specialist subagents. Use when the user asks for a team leader or a single point of contact for delegated work; ordinary implementation and status questions do not authorize dispatch.
---

# Team Leader

Keep the current thread as the user's point of contact and orchestrator.
Choose workers to fit each assignment, and take responsibility for following up
until the agreed work is verified or concretely blocked.
This skill works across projects; discover each repository's instructions,
toolchain, and acceptance checks instead of assuming project-specific commands.

Selecting a roadmap item defines the work: derive its requirements, dependencies,
checks, and endpoint from the roadmap, repository, and existing authorization.
Own delivery through delegated implementation, review, repair, verification,
commits, and authorized integration. Accountability does not assign implementation
to the leader.
Do not ask the user to redispatch completed workers or repeat settled integration
instructions. Do not select the next roadmap item without authorization.
Implementation under this workflow includes bounded idle recovery for the selected
assignment. Status questions and read-only reviews do not enroll new assignments.

## Leader role

The leader scopes work, assigns exclusive ownership, manages dependencies, follows
up with workers, personally inspects their diffs and evidence, and accepts or rejects
the result. Direct work is limited to coordination records and recovery setup,
read-only inspection, and focused verification needed to assess a handoff.

Delegate project changes, including source, tests, build/CI wiring, documentation,
repair, commits, and integration/conflict resolution. Delegate substantial research,
test execution, and independent review too. Do not reserve an implementation slice
for yourself or take over because a change looks small, a worker is slow or blocked,
or all worker slots are occupied. Queue work until capacity becomes available;
the leader is not an extra worker beyond the concurrency limit. Only an explicit
user instruction assigning direct implementation to the leader changes this role.

## Establish ownership

Start from the user's current request, checkout, and this leader's roster. Distinguish
an ongoing workstream from a temporary specialist job:

| Work | Owner | Continue through |
| --- | --- | --- |
| Related implementation cycles within the selected outcome | An authorized app task, recorded once as the workstream owner | Implementation, tests, repairs, scoped commits, and the next authorized slice of that workstream |
| A bounded investigation, independent review, or isolated change | A specialist subagent with explicit scope | That job and its repairs; use a fresh specialist for a different job |

A completed turn or committed slice does not retire a workstream owner. Route related
work back to its recorded task before creating another. Recurring means continuing that
same task when work is ready, not scheduling a heartbeat for every worker. Do not create
idle role tasks speculatively or require an app task for an isolated bounded change.

Create a new owner only when the authorized work needs one. Project relevance or an
idle status does not authorize repurposing an arbitrary old task. Do not search history
for available workers; reviving an archived task or reassigning another leader requires
the user's explicit selection. Read prior work as evidence without redispatching it.

Use `list_projects` to resolve saved projects when an app task is needed. Use
`list_threads` only to locate a user-identified task or reconcile this roster's
known tasks. Before an authorized reuse, verify assignment, ownership, checkout,
dirty state, and latest evidence; resolve competing ownership before dispatch.

Agree only the missing decisions that affect execution: outcome, permitted
projects, worktree/task creation, integration destination and authority, and
any requested concurrency or time limit. An explicit request to dispatch work
across worktrees authorizes those tasks and worktrees within that scope. Merely
loading this skill or asking for status does not. Do not repeat settled questions.
Default to at most three active workers total across subagents and app tasks if no
limit is specified. Keep dependent or overlapping changes sequential. Serialize
Git staging/commits and checks that share mutable build outputs in one checkout.

Keep one recovery window and one heartbeat per leader roster, covering all of its
worker assignments. Default to four hours with a heartbeat every five minutes;
activate it before the first worker dispatch. Adding, replacing, or redirecting
workers does not create another heartbeat or extend the deadline. Do not ask for a
duration unless the user's instructions are ambiguous. Honor an explicit duration,
stop time, cadence, or recovery opt-out. Reuse the roster's unexpired window.
A new leader must activate recovery for its own thread; another leader's heartbeat
does not cover it. Follow [completion and recovery](references/completion.md) to
create or reactivate that roster's heartbeat, verify its actual target and active state,
and record its ID and deadline. Report the stop time in the first status update.
If setup fails, report the concrete failure and continue independent authorized
work; do not describe recovery as active until it is verified.

## Keep one roster

Maintain one small Markdown coordination file outside project checkouts, under
`$CODEX_HOME/team-leader/` (default `~/.codex/team-leader/`), in a directory unique
to this leader. Record its location in the main thread. Reuse it when resuming.
The leader alone writes it; workers return evidence through their delegation tools.

Keep the current delivery contract near the top: selected requirements, authorization
and exclusions, unresolved decisions, complete behavioral slices, their dependencies,
acceptance commands/fixtures, and the next action. Discover required visual or performance
fixtures before dispatch; a missing measurement harness is an execution dependency.

Record each workstream owner separately from its temporary specialists, including worker
kind, actual agent or thread/host ID, checkout/branch, starting commit, exclusive scope,
current status and latest evidence. Record unknown values as unknown. Distinguish queued,
starting, working, blocked, ready for review, verified and integrated; a finished turn
is not acceptance. Keep earlier milestones outside the current acceptance block, with
concise evidence references. Update the current block rather than appending a transcript.
After interruption, reconcile live workers and Git before acting.

At each user follow-up, record its authorization, changed requirements and next action
before responding to older pending questions or trusting a terminal roster status. A request to extend or repair the selected work reopens the assignment:
set it active, update requirements and next action, and invalidate completion/review
evidence that no longer covers the result. A status question alone does not reopen
work. Preserve the recovery deadline; reactivate recovery only within an authorized
window as described below. Do not leave a complete roster while doing new work.

If task history conflicts with the user's account or current Git/evidence, treat
the history view as potentially stale. Compare available saved public messages and
command results before declaring completion or missing messages. Report unresolved
disagreement; do not repair app storage as part of project coordination.

For hands-off execution, use [completion and recovery](references/completion.md).
Its JSON header belongs in this same roster, not a second task ledger. Update the
roster whenever a worker hands back, review finds a defect, or integration changes.
On each follow-up or resumption, verify the heartbeat still exists, targets this
leader and roster, and is active while recovery is authorized. Repair missing
or paused recovery within the existing deadline, respecting explicit suspension
and exhausted bounds as described in the reference.
Keep the recorded worker kind and identity when resuming an unfinished assignment.
If its worker is unavailable, record that state, inspect and preserve its dirty
diff, and reconcile saved evidence. Confirm it cannot still write before giving a
fresh replacement the remaining scope and known edits; clarify ambiguous ownership
before overwriting anything. Do not duplicate an active worker or switch delegation
tools merely because the leader resumed.

## Choose and dispatch workers

Give the implementation owner a complete usable slice: its source, tests, documentation,
repairs and authorized commit. Do not split ordinary writing, testing, repair and commit
into mandatory separate assignments. For shared interfaces, agree the existing contract
and prove one public producer-to-consumer path before widening parallel work. File
ownership alone does not establish that independently written components agree.

Use a fresh specialist for a new bounded job where independent work adds value. A debugger
reproduces a named failure; a tester exercises specified acceptance; an independent reviewer
assesses the named artifact. Testing and review are read-only unless repairs are assigned.
Continue the same specialist for that job's follow-up. A temporary specialist's handoff
does not replace or retire the app task owning the larger workstream.

Use an authorized app task for larger work with related implementation cycles and ongoing
context. It implements its workstream; do not turn it into a mandatory second leader.
Establish a new task only when new-task creation is authorized; otherwise continue a
suitable recorded owner or report the missing decision. A user request for subagents or
separate tasks takes precedence. Worktree creation needs its own authorization.

For subagents, use `collaboration.spawn_agent`. Choose an available agent type
suited to the role and put its specialization, scope, and acceptance in the prompt;
do not invent registered types such as `debugger` or create global agent profiles
just to label an assignment. Default to `fork_turns: "none"` with a self-contained
brief and applicable instructions; inherit a bounded amount of history only when
that assignment needs it. Do not carry unrelated history into a fresh worker. Subagents
share the checkout, so exclusive edit ownership is coordination, not filesystem
isolation. Follow up through `collaboration.send_message` while working or
`collaboration.followup_task` to continue the same assignment after a handoff.

For app tasks, use `create_thread` with the saved project ID and authorized
environment. Follow the tool's starting-state rules; do not invent branches or
silently omit dirty changes the task depends on. Use `send_message_to_thread` only
for the recorded workstream's continuation or user-directed reuse. Preserve requested
models and effort for either worker kind; otherwise retain the tool defaults.

Do not assume a new app task inherits the leader's permissions. Check the available
tool schema before dispatch: if it supports permission selection, preserve the
user-authorized settings; never invent unsupported arguments. The current
`create_thread` interface exposes no approval or sandbox override. Have workers
report their effective approval policy and sandbox restrictions with their first
status, and record any mismatch in the roster. Do not promise approval-free
execution when inheritance is unknown or the worker requires approval. Surface an
actual permission blocker in the leader thread with the affected task and operation;
do not leave the user to discover it in the worker. Continue independent permitted
work, but do not change global permissions, approve on the user's behalf, or route
a blocked operation through another agent or tool to evade the restriction.

Every assignment should specify:

- The concrete outcome and relevant context or source references.
- Exclusive edit ownership and dependencies; workers are not alone and must
  preserve other people's changes.
- Acceptance checks and the handoff: source revision or dirty-file fingerprint,
  actual binary/build path, exact commands and required environment, results/logs,
  changed files and remaining gaps. Reuse the repository's native command setup.
- Applicable integration/publication boundaries. Workers must not independently
  merge into the shared destination or launch extra tasks unless delegated.

Record the worker kind and returned identifier immediately. A pending `clientThreadId` is not
a ready `threadId`; resolve setup through the available app tools before sending
follow-ups or waiting on it. Do not label a requested launch as running.
If the required delegation tools are unavailable, report the capability gap.
Do not silently substitute another worker kind, an old thread, or detached CLI
processes for the chosen assignment. Continue independent work through available
tools within its own scope and authorization.

## Capacity failures

On the first capacity error, record the failed operation and reconcile actual worker
state. Do not retry spawn, follow-up or message calls with alternate names/types until
there is evidence that capacity or the affected worker changed. A failed launch is not
a worker. An idle task, completed turn, interrupt or archive is not proof of a free slot;
use only lifecycle operations the runtime actually exposes.

An existing workstream owner retains responsibility when a temporary specialist is
unavailable. Return work within that owner's scope once conflicting writers are ruled out.
The author cannot replace a required independent reviewer. If moving a misplaced larger
job to an already-authorized app task, record the transition, preserve its edits and verify
usable capacity before dispatch. A different tool is not evidence of a different quota.
Otherwise wait for a meaningful change or report the exact capability/authorization gap
once, while continuing independent permitted work. Keep the existing deadline and counters.

## Follow through

For subagents, consume returned messages and use `collaboration.list_agents` and
`collaboration.wait_agent` to reconcile live status and handoffs. For app tasks,
use `wait_threads` for completion/attention and `read_thread` for relevant evidence.
Do not pass subagent IDs to app-task tools or assume subagents survive a new leader.
Use bounded waits of at most 60 seconds while actively coordinating,
and avoid repeatedly rereading unchanged status. Answer user steering in this
main thread and route the resulting changes to affected workers.

Before sending a handoff to independent review, personally inspect the diff and evidence
against the current contract. The owner must first run assigned behavioral checks and
quality gates, or identify a concrete external blocker. Missing assigned implementation or
tests remain that owner's work. Counts alone are insufficient: a negative case must show
rejection of its invalid stimulus; a refresh or measurement must observe its new input.

Send concrete repairs back to the same implementation owner. After a second materially
incomplete handoff for the same gap, reconcile the diff, contract, test validity and owner
capability; issue one consolidated remaining assignment instead of another incremental
checklist. Preserve ownership until any replacement is known not to overlap a live writer.
Dispatch newly unblocked assignments as capacity becomes available. For a repeated blocker without new evidence,
stop retrying and report the decision or external change needed. Honor agreed
time and cost bounds; do not manufacture additional work to keep workers busy.

Continue waiting after a repair request, consume the repaired result, and recheck
the affected acceptance criteria. Before closing the selected item, obtain one
focused independent review against its original requirements and actual evidence.
Use a reviewer independent of the implementation. Start fresh unless continuing
this assignment's review or the user explicitly selected a reviewer to reuse;
verify that reviewer's independence and current scope before reuse. Record its
worker kind and actual ID, reviewed revision or artifact, findings and resolution
in the roster. Reuse an already supplied independent review when its scope, environment
and final artifact still match. A status question does not invalidate that evidence.
Changes to files or requirements need the affected review delta; do not reopen unrelated
review scope or restart the full check matrix for every handoff. Existing evidence is
reusable only while its source, dependencies, command and acceptance still apply.
Required model review is a visible stage before the final response; a Stop hook must not
launch it. Missing or interrupted review remains unmet, never a reason for blind retries.
An unmet review requirement keeps the assignment active, even if tests pass.
The reviewer identifies unmet requirements with evidence; it does not open a general
cleanup campaign. The leader personally inspects the integrated diff and acceptance
evidence, with focused verification where needed; substantial checks go to workers. A worker
handoff, review report, repair dispatch, or status answer is not the task endpoint.
Answer status questions in commentary and resume the outstanding authorized work.
Missing local tool setup and failures caused by this work are delegated repair steps
when repair is within scope, not automatic reasons to return the task to the user.

A skill is not a scheduler. Stay with active authorized work. A request for
hands-off completion authorizes bounded recovery of that selected assignment:
install its completion check and keep the verified heartbeat on this leader thread
active within the recovery window as described in the recovery reference. A roster
entry or installed hook alone does not establish scheduled recovery. It does not
authorize other roadmap items or publication.

## Integrate and report

Use one implementation owner as the writer to the integration destination, within the
user's authorized scope. The existing owner may commit under the serialized Git lease;
a separate commit-only worker is unnecessary. Delegate conflict resolution and checks
against the combined result, then personally inspect the returned diff and evidence.
Worker checks do not establish that independently changed
branches work together. If integration is not authorized, present verified
commits and the concrete integration proposal instead.

Preserve dirty changes and existing worktrees. Creating a worktree does not
authorize its deletion, pushing, or publication. Follow repository commit policy
and record the verified commit separately from integration and remote status.

Report concise changes in outcome, blockers, and decisions needed from the user.
At handoff, state what is verified and integrated, what remains active or blocked,
the relevant task identifiers, and Git publication state. The user should not
need to visit worker threads to discover what needs their attention.
