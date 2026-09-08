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

A skill is not a scheduler. Stay with active authorized work, but do not promise
future monitoring after the turn ends. When the user asks for recurring or later
follow-up, use the app's thread heartbeat automation within that authorization.

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
