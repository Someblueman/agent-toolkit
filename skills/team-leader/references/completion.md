# Completion and recovery

Use this for hands-off execution of an authorized assignment. The normal endpoint
is verified task-owned commits, plus integration where already authorized. Infer
acceptance from the selected roadmap item; do not make the user write a work plan.
Recovery preserves delivery ownership: continue workstreams through their owners,
inspect returned evidence, and finish authorized integration and closing repairs.
It does not create a new assignment or additional publication authority.

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
  "next_action": "Inspect the returned commit and integrate it into the authorized destination",
  "progress": "Actual worker commit/test result or observed state change",
  "waiting_on": [],
  "deadline": 1800000000,
  "evidence": [],
  "heartbeat_id": null
}
```

Recovery belongs to the leader roster: one shared deadline and one heartbeat cover
all of its worker assignments. Default to four hours of recovery with a heartbeat
every five minutes, activated before the first worker dispatch; no duration question
is needed. Honor an explicit duration, stop time, cadence, or recovery opt-out.
Set `deadline` to activation time plus 14,400 Unix seconds unless the user supplied
a different bound. The example timestamp above is illustrative. Record the duration
and resolved deadline, and tell the user when recovery stops. Adding or replacing
workers does not create more heartbeats or extend the window. Never restart the
clock on a poll, worker handoff, interruption, or automatic recovery continuation.

`progress` changes only for new observable evidence, not another
poll, rewritten summary, or renewed intention. Keep detailed acceptance criteria,
workstream owner and specialist IDs/checkouts, review findings, and evidence in the
current delivery block of the Markdown body. A recurring owner's completed slice does
not retire the workstream or create a new recovery window. Keep its identity for related
authorized work; a status question does not invalidate applicable evidence.
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

Create or reactivate recovery with `automation_update` as part of leader setup:

1. Inspect existing automations. Reuse the heartbeat matching this actual leader
   thread and absolute roster path, regardless of which worker needs attention.
   Verify the stored automation's actual target and roster path before any mutation;
   an ID copied from an old roster is not ownership. Never retarget, resume or pause an
   automation belonging to another leader. If several belong to this same leader and
   roster, retain one and pause only those duplicates before continuing. A replacement leader needs its own heartbeat and roster; leave a
   previous leader's paused automation paused.
2. Create or update a thread heartbeat with `status: ACTIVE`, targeting the actual
   leader thread, every five minutes unless the user chose another cadence. Its
   prompt must reference this leader's absolute roster path and authorized objective.
   Update that prompt when the objective changes; retain the same heartbeat ID.
   Preserve unrelated automation fields and notification preferences on updates.
3. Read it back with `automation_update` in view mode. Verify its ID, active state,
   target thread, cadence, and prompt's roster path and scope. Record the returned
   ID in `heartbeat_id`. Neither a successful hook install nor a remembered ID is
   proof that the scheduler has an active heartbeat for this leader.

A view call can render an automation card in the current conversation; that is not proof
of scheduled delivery into this task. Prefer a read-only inspection that avoids a misleading
card, or explain the card before displaying it. Copied worker context does not transfer
ownership of the leader's heartbeat or roster.

Repeat this live check on follow-up or resumption. If an active leader roster within
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
> Otherwise reconcile actual worker states and Git, consume handoffs and finish the
> next authorized delivery step. Personally inspect diffs and evidence, integrate
> verified work, resolve small closing repairs and check the combined result.
> Route related implementation, tests, repairs and commits back to the recorded app-task
> workstream owner. Use fresh specialists for bounded new jobs; continue the same specialist
> for that job's repair. Do not replace an owner because a turn or slice finished.
> On a capacity failure, record the operation and reconcile live state; retry only after
> a meaningful capacity/worker change. Do not assume another tool has spare quota.
> Do not duplicate an active writer. Preserve each owner's authorized worktree and
> base; do not collapse parallel work into a shared checkout. Send follow-ups only
> for concrete dependencies, defects or changed requirements. On usage exhaustion,
> pause recovery and preserve partial work; do not keep scheduling retries.
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

On explicit user interruption the Interrupt hook suspends recovery. When the user
explicitly resumes recovery, perform these steps in order:

1. Reconcile the authorized objective and unfinished work. Write `status: active`
   to the roster. Retain an unexpired deadline; if it has expired, write a new
   `deadline` of current Unix time plus 14,400 seconds, unless the user specified
   another bound. Record the renewal and resolved stop time before proceeding.
2. Run `completion.py resume <thread-id>` once. This command clears suspension
   and counters only; it does not change the roster's deadline or status.
3. Run `completion.py check <thread-id>` and require `decision: block` before
   reactivating and verifying the same roster heartbeat as described above.

If the user opts out of recovery, leave it inactive. A status query does not resume
a paused roster or renew an expired window. A newly user-selected leader objective
also permits this sequence with a new deadline and updated roster scope, retaining
the heartbeat ID. New worker assignments within that objective do not. Never renew
or reset counters automatically in a recovery continuation. Usage limits, an offline
host, untrusted hooks, and scheduler
failures may prevent execution; do not promise automatic recovery from all of them.

## Prove the cycle

Trial against one existing assignment. Observe a real incomplete handoff, the
leader's concrete repair or integration action, the returned result, and its
verification without another user nudge. Also verify clean completion stops,
unregistered worker threads are untouched, and interruption/no-progress bounds stop
recovery. Report adapter tests, actual Stop execution, scheduled heartbeat execution,
and feature acceptance separately; none substitutes for the others.

## Limits and live qualification

The deadline is checked only when this adapter runs. A running worker is not stopped
by it, and a scheduler can still attempt delivery while the model is unavailable.
The no-progress counter trusts roster text and observed `waiting_on` IDs; it is not
a work-quality or cost detector. Refresh those IDs from actual runtime state. Never
rewrite progress merely to reset the counter. There is no enforced token budget.
Give workers the same stop time and require bounded commands and a preserved handoff
at expiry. Pause the owned heartbeat when possible; report any inability to stop
running work. Do not claim that pausing recovery cancels workers.

A source/adapter test pass is not delivery qualification. Before claiming this workflow
is reliable, use an authorized small representative assignment with independent
worktrees and an actual shared integration requirement. Record elapsed time, owner
identities, available leader/worker usage (including cache accounting limitations),
coordination calls, accepted commits and combined behavioral checks. Observe a real
repair, completion without another user nudge, and recovery pause. Exercise cancellation
and exhausted bounds separately. Judge whether delegation reduced user coordination
without disproportionate overhead; do not infer that from test counts. A simulation
or document review alone cannot establish this. Do not resume an old campaign or launch
a costly trial solely because the skill source was updated.
