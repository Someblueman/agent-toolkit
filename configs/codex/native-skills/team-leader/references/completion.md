# Completion and recovery

Use this for hands-off execution of an authorized assignment. The normal endpoint
is verified task-owned commits, plus integration where already authorized. Infer
acceptance from the selected roadmap item; do not make the user write a work plan.

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
  "next_action": "Review the returned worker diff and run its missing CLI case",
  "progress": "Actual worker commit/test result or observed state change",
  "waiting_on": [],
  "deadline": 1800000000,
  "evidence": [],
  "heartbeat_id": null
}
```

Set `deadline` to Unix seconds: use the user's bound, otherwise four hours from
activation. State the chosen bound without asking a routine setup question. Do not
silently extend it. `progress` changes only for new observable evidence, not another
poll, rewritten summary, or renewed intention. Keep detailed acceptance criteria,
worker IDs/checkouts, review findings, and evidence in the Markdown body.
`waiting_on` lists only worker/task IDs currently observed running. Refresh it from
live state on recovery; clear IDs as soon as they finish. Waiting on real running
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

Inspect existing automations and reuse this assignment's heartbeat. For hands-off
execution, create a thread heartbeat with `automation_update`, targeting the actual
leader thread. Default to every five minutes, retaining the user's requested cadence
if any. Record its returned ID in the roster. Do not create a cron job or another
coordinator. Use a clear prompt equivalent to:

> Resume only the selected assignment recorded in [absolute roster path], using
> the team-leader skill. First honor newer user cancellation or scope changes.
> Reconcile live worker states and refresh `waiting_on` without resetting counters.
> Run `python3 [installed completion.py] check [leader-thread-id]`. If the check
> exits nonzero or does not return `decision: block`, pause this heartbeat and
> report completion, the concrete blocker, or the exhausted recovery bound accurately.
> Otherwise reconcile actual worker states and Git, carry out the next authorized
> step, consume worker handoffs, review, repair, verify, commit, and integrate through
> the recorded endpoint. Keep the roster current. Do not launch duplicate workers,
> new roadmap items, or publish. Pause this heartbeat when complete, blocked, or
> paused. Do not reset recovery counters or extend the deadline automatically.

The hook allows one continuation per turn and suspends recovery after three
unchanged recovery checks with no observed running workers, or the deadline.
Its private counter/event files are execution
bookkeeping, not another work roster. The hook cannot judge semantic completion:
the leader and focused reviewer must inspect actual implementation and evidence.

On explicit user interruption the Interrupt hook suspends recovery. A later explicit
resume authorizes `completion.py resume <thread-id>` and reactivating the existing
heartbeat, with a newly stated bound if necessary. A status query does not resume a
paused assignment. A newly user-selected assignment on the same leader also permits
resetting counters once, after updating the roster with that assignment and bound.
Never do this automatically in a recovery continuation. Usage limits, an offline
host, untrusted hooks, and scheduler
failures may prevent execution; do not promise automatic recovery from all of them.

## Prove the cycle

Trial against one existing assignment. Observe a real incomplete handoff, the
leader's concrete repair or integration action, the returned result, and its
verification without another user nudge. Also verify clean completion stops,
unregistered worker threads are untouched, and interruption/no-progress bounds stop
recovery. Report adapter tests, actual Stop execution, scheduled heartbeat execution,
and feature acceptance separately; none substitutes for the others.
