---
name: team-leader
description: Coordinate separate Codex app tasks across project worktrees from one main thread. Use when the user asks for a team leader, ongoing worktree coordination, or a single point of contact for multiple tasks; ordinary implementation and status questions do not authorize dispatch.
---

# Team Leader

Keep the current thread as the user's point of contact and integration owner.
Use separate app tasks for independently useful work, and take responsibility
for following up until the agreed work is verified or concretely blocked.
This skill works across projects; discover each repository's instructions,
toolchain, and acceptance checks instead of assuming project-specific commands.

Selecting a roadmap item defines the work: derive its requirements, dependencies,
checks, and endpoint from the roadmap, repository, and existing authorization.
Own implementation, review, repair, verification, commit, and authorized integration.
Do not ask the user to redispatch completed workers or repeat settled integration
instructions. Do not select the next roadmap item without authorization.
Implementation under this workflow includes bounded idle recovery for the selected
assignment. Status questions and read-only reviews do not enroll new assignments.

## Establish ownership

Resolve the requested projects and scope with `list_projects` and `list_threads`.
Read relevant existing tasks before creating replacements. Adopt only tasks
within the user's requested scope; unrelated tasks remain outside the roster.
Check each adopted task's current assignment, checkout, dirty state, and latest
evidence before steering it. If another leader owns it, settle ownership before
dispatching competing instructions.

Agree only the missing decisions that affect execution: outcome, permitted
projects, worktree/task creation, integration destination and authority, and
any requested concurrency or time limit. An explicit request to dispatch work
across worktrees authorizes those tasks and worktrees within that scope. Merely
loading this skill or asking for status does not. Do not repeat settled questions.
Default to at most three active worker tasks if no limit is specified; keep
dependent or overlapping changes sequential.

Before activating recovery, ask what recovery window the user wants unless they
already supplied one for this assignment. Ask for a duration or stop time, explain
that it limits how long automatic recovery can continue, and wait for the answer;
there is no default recovery window. Continue independent planning or implementation
while waiting, but do not activate the heartbeat or choose a deadline yourself.
Record the agreed window and its resolved deadline in the roster. If an expired
window needs renewal, ask again unless the user already specified the new window.

## Keep one roster

Maintain one small Markdown coordination file outside project checkouts, under
`$CODEX_HOME/team-leader/` (default `~/.codex/team-leader/`), in a directory unique
to this leader. Record its location in the main thread. Reuse it when resuming.
The leader alone writes it; workers return evidence through their task threads.

Record the objective and authorization boundaries, then one row per assignment:
project, actual thread/host ID, worktree and branch, starting commit, owned scope,
dependencies, current status, latest evidence, and next action. Record unknown
values as unknown until verified. Distinguish queued, starting, working, blocked,
ready for review, verified, and integrated; a finished turn is not acceptance.
Keep a short section for decisions and the next actions, not a second transcript.
After interruption, reconcile the roster with live threads and Git before acting.

For hands-off execution, use [completion and recovery](references/completion.md).
Its JSON header belongs in this same roster, not a second task ledger. Update the
roster whenever a worker hands back, review finds a defect, or integration changes.
Keep actual app task identities; do not switch to shared-process subagents halfway
through a wave merely because the leader resumed in a different turn.

## Dispatch through app tasks

Use `create_thread` with the saved project ID and a worktree environment for
authorized isolated Git work. Follow the tool's starting-state rules; do not
invent branches or silently omit dirty changes the task depends on. For an
existing task, use `send_message_to_thread` instead of creating a duplicate.
Preserve requested models and effort; otherwise retain the app/task defaults.

Every assignment should specify:

- The concrete outcome and relevant context or source references.
- Exclusive edit ownership and dependencies; workers are not alone and must
  preserve other people's changes.
- Focused acceptance checks and the expected handoff: actual checkout/branch,
  commit, changed files, checks with results, and unresolved issues.
- Applicable integration/publication boundaries. Workers must not independently
  merge into the shared destination or launch extra tasks unless delegated.

Record the returned identifier immediately. A pending `clientThreadId` is not
a ready `threadId`; resolve setup through the available app tools before sending
follow-ups or waiting on it. Do not label a requested launch as running.
If app task tools are unavailable, report the capability gap; do not silently
substitute shared-checkout subagents or detached CLI processes.

## Follow through

Use `wait_threads` for completion/attention and `read_thread` for relevant
evidence. Use bounded waits of at most 60 seconds while actively coordinating,
and avoid repeatedly rereading unchanged status. Answer user steering in this
main thread and route the resulting changes to affected workers.

On completion, inspect the actual diff and checks. Send concrete repair requests
to the same task for defects within scope. Dispatch newly unblocked assignments
as capacity becomes available. For a repeated blocker without new evidence,
stop retrying and report the decision or external change needed. Honor agreed
time and cost bounds; do not manufacture additional work to keep workers busy.

Continue waiting after a repair request, consume the repaired result, and recheck
the affected acceptance criteria. Before closing the selected item, obtain one
focused independent review against its original requirements and actual evidence.
The reviewer identifies unmet requirements with evidence; it does not open a general
cleanup campaign. The leader personally checks the integrated result. A worker
handoff, review report, repair dispatch, or status answer is not the task endpoint.
Answer status questions in commentary and resume the outstanding authorized work.
Missing local tool setup and failures caused by this work are repair steps when
repair is within scope, not automatic reasons to return the task to the user.

A skill is not a scheduler. Stay with active authorized work. A request for
hands-off completion authorizes bounded recovery of that selected assignment:
install its completion check and create/reuse a heartbeat on this leader thread
as described in the recovery reference. Confirm the heartbeat exists before
promising recovery. It does not authorize other roadmap items or publication.

## Integrate and report

Keep one writer to the integration destination. Integrate only within the user's
authorized destination and scope, inspect conflicts, and run checks against the
combined result. Worker checks do not establish that independently changed
branches work together. If integration is not authorized, present verified
commits and the concrete integration proposal instead.

Preserve dirty changes and existing worktrees. Creating a worktree does not
authorize its deletion, pushing, or publication. Follow repository commit policy
and record the verified commit separately from integration and remote status.

Report concise changes in outcome, blockers, and decisions needed from the user.
At handoff, state what is verified and integrated, what remains active or blocked,
the relevant task identifiers, and Git publication state. The user should not
need to visit worker threads to discover what needs their attention.
