# Completion and recovery

Use this for hands-off execution of an authorized assignment. The normal endpoint
is verified task-owned commits, plus integration where already authorized. Infer
acceptance from the selected roadmap item; do not make the user write a work plan.
Recovery preserves the leader's orchestration role: delegate project changes and
integration, inspect returned evidence, and keep ownership and follow-up current.
An unfinished assignment does not authorize the leader to become an implementer.

## One roster

Start `~/.codex/team-leader/<actual-leader-thread-id>/roster.md` (or the equivalent
under `CODEX_HOME`) with this JSON code fence, followed by the existing human-readable
roster. Upgrade an existing roster in place; retain its decisions and task identities.

```json
{
  "version": 1,
  "thread_id": "actual-leader-thread-id",
  "objective": "Selected roadmap item and authorized integration endpoint",
  "status": "active",
  "next_action": "Inspect the returned worker diff and delegate its missing CLI case",
  "progress": "Actual worker commit/test result or observed state change",
  "waiting_on": [],
  "deadline": 1800000000,
  "evidence": [],
  "heartbeat_id": null
}
```

Default to four hours of recovery with a heartbeat every five minutes for each
implementation assignment. Activate it before dispatching or redirecting workers;
no duration question is needed. Honor an explicit duration, stop time, cadence, or
recovery opt-out. Set `deadline` to activation time plus 14,400 Unix seconds unless
the user supplied a different bound. The example timestamp above is illustrative.
Record the duration and resolved deadline, and tell the user when recovery stops.
Reuse an unexpired deadline for the same assignment; never restart the four-hour
clock on a poll, worker handoff, interruption, or automatic recovery continuation.

`progress` changes only for new observable evidence, not another
poll, rewritten summary, or renewed intention. Keep detailed acceptance criteria,
worker IDs/checkouts, review findings, and evidence in the Markdown body.
`waiting_on` lists only IDs currently observed running through the correct tool:
native collaboration for subagents, app-task tools for threads. Record each
worker's kind in the roster body. Refresh live state on recovery; clear IDs as soon
as they finish or are no longer available. Waiting on real running
work does not consume failed-recovery attempts, but the deadline still applies.

Statuses: `active`, `complete`, `blocked`, `paused`. Complete requires evidence
covering all selected requirements, focused independent review, passing required
checks on the final combined result, and the authorized commit/integration endpoint.
Populate `evidence` with concrete paths/commits/results. A blocker needs evidence,
attempted resolution, and the external change or decision needed. Missing tests or
unfinished review alone do not establish a blocker. Paused means cancellation,
interruption, or exhausted recovery bounds; it never means success.

## Install and recover

Resolve `SKILL_DIR` to this installed skill's directory. Run:

```sh
python3 "$SKILL_DIR/scripts/completion.py" install /absolute/leader/project
```

This preserves other hooks and adds Stop/Interrupt handlers. It does not grant hook
trust or change permissions. Verify real hook execution in `completion-events.jsonl`
beside the roster; a manual CLI invocation proves only the adapter. If Codex requires
trust, report that setup boundary; never write trusted hashes or bypass it. Recovery
via the normal heartbeat can still run the same check explicitly.

Create or reactivate recovery with `automation_update` as part of assignment setup:

1. Inspect existing automations. Reuse only a heartbeat for this actual leader
   thread and assignment. A replacement leader needs its own heartbeat and roster;
   leave a previous leader's paused automation paused.
2. Create or update a thread heartbeat with `status: ACTIVE`, targeting the actual
   leader thread, every five minutes unless the user chose another cadence. Its
   prompt must reference this leader's absolute roster path and selected assignment.
   Preserve unrelated automation fields and notification preferences on updates.
3. Read it back with `automation_update` in view mode. Verify its ID, active state,
   target thread, cadence, and prompt's roster path and scope. Record the returned
   ID in `heartbeat_id`. Neither a successful hook install nor a remembered ID is
   proof that the scheduler has an active heartbeat for this leader.

Repeat this live check on follow-up or resumption. If an active assignment within
its recovery window has a missing or accidentally paused heartbeat, recreate or
reactivate it and verify again. Preserve the original deadline and recovery
counters. Do not reactivate after explicit suspension, exhausted bounds, or a user
opt-out without a new user instruction to resume. If the tool is unavailable or
setup fails, report the exact gap and keep recovery marked inactive while
continuing independent authorized work. Do not create a cron job or another
coordinator. Use a clear prompt equivalent to:

> Resume only the selected assignment recorded in [absolute roster path], using
> the team-leader skill. First honor newer user cancellation or scope changes.
> Reconcile the latest user requests, review findings and actual Git/evidence before
> trusting a complete roster or running the check. Reopen authorized unfinished
> work and invalidate stale acceptance; a status query alone is not a resume.
> Explicit user cancellation or an Interrupt-hook suspension requires user resume.
> A turn merely labelled interrupted after a crash/restart is not proof of user
> cancellation. With confirmed runtime interruption and no explicit suspension,
> continue the existing active assignment within its original recovery window.
> If the cause is unknown, report that uncertainty and pause; do not invent consent.
> Reconcile live worker states and refresh `waiting_on` without resetting counters.
> Run `python3 [installed completion.py] check [leader-thread-id]`. If the check
> exits nonzero or does not return `decision: block`, pause this heartbeat and
> report completion, the concrete blocker, or the exhausted recovery bound accurately.
> Otherwise reconcile actual worker states and Git, coordinate the next authorized
> step, consume worker handoffs, and delegate repairs, checks, commits and integration
> through the recorded endpoint. Personally inspect returned diffs and evidence.
> Use the skill's delegation rules: fresh specialist subagents for bounded new
> assignments, fresh authorized app tasks for larger independent work. Continue
> an existing worker only for its same assignment or explicit user-directed reuse.
> Do not implement project changes yourself; queue work when worker slots are full.
> Keep the roster current. Do not launch duplicate workers,
> new roadmap items, or publish. Pause this heartbeat when complete, blocked, or
> paused. Do not reset recovery counters or extend the deadline automatically.

The hook allows one continuation per turn and suspends recovery after three
unchanged recovery checks with no observed running workers, or the deadline.
Its private counter/event files are execution
bookkeeping, not another work roster. The hook cannot judge semantic completion:
the leader and focused reviewer must inspect actual implementation and evidence.
The CLI checks only the supplied roster; it cannot detect newer user messages or
prove that an evidence string represents independent review. Reconciliation must
precede it. A paused heartbeat cannot perform that reconciliation: the leader must
update the roster and reactivate the existing heartbeat when a user follow-up
authorizes resumed work, subject to the existing window or the renewal rule below.

On explicit user interruption the Interrupt hook suspends recovery. A later explicit
resume authorizes `completion.py resume <thread-id>` and reactivating the existing
heartbeat within its existing window. If that window has expired, the explicit
resume starts a new four-hour window unless the user specifies another bound or
opts out. A status query does not resume a paused assignment or renew an expired
window. A newly user-selected assignment on the same leader also permits resetting
counters once, after updating the roster with that assignment and its new bound.
Never do this automatically in a recovery continuation. Usage limits, an offline
host, untrusted hooks, and scheduler
failures may prevent execution; do not promise automatic recovery from all of them.

## Prove the cycle

Trial against one existing assignment. Observe a real incomplete handoff, the
leader's concrete repair or integration dispatch, the returned result, and its
verification without another user nudge. Also verify clean completion stops,
unregistered worker threads are untouched, and interruption/no-progress bounds stop
recovery. Report adapter tests, actual Stop execution, scheduled heartbeat execution,
and feature acceptance separately; none substitutes for the others.
