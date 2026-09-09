# Team leader completion trial

Implementation: `7177c84`, installed with `scripts/install.sh codex` on 9 September
2026. The installed skill and repository matched after installation. No push.

## Adapter and installation checks

- Ten real CLI tests passed: incomplete/repair/complete cycle; one continuation;
  unchanged recovery bounds; deadline; interruption/resume; real-worker waiting;
  corrupt state; malformed bounds; unrelated sessions; preserved hook installation.
- Seven existing installer tests passed.
- Existing quality suite: 28 passed, eight optional native-tool trials skipped.
- Ruff lint/C901, formatting, skill validation, and `git diff --check` passed.
- Independent review found missing-session and malformed-state handling issues;
  both were fixed with regression cases before commit.

Later concurrent quality-engine edits belong to another task; they are not part
of this commit or its qualification.

## Real Hydra lifecycle

The existing leader `01a08317-27ac-7680-a095-17e98d95764b` retained ownership of
V2/9C/H2 and local integration into `codex/release-next`. No new roadmap item,
replacement coordinator, push, or release was authorized by the trial.

The leader upgraded its existing roster in place and consumed actual corrections.
It reported independently passing 9C native plan checks and H2's two repaired
public enrollment cases, then sent remaining acceptance gaps to the same workers.
Those checks are partial feature evidence, not full milestone acceptance.

At a deliberately requested incomplete handoff, the leader ended its turn at
21:48:58 UTC. No native Stop event was recorded. The new hook definitions lack
persisted trust; trust and permissions were left unchanged. Native Stop execution
remains unqualified until the hooks are reviewed through Codex's normal hook UI.

The `hydra-leader-completion-trial` heartbeat resumed the SAME leader automatically
at 21:57:32 UTC (turn `01a0882d-19b8-7a32-be9b-70f05efc3315`). Its explicit recovery
check logged `decision: block` at 21:58:05 UTC. The roster then recorded newly
returned V2 `f933143` and H2 `1c730b5`, with 9C still running. No user nudge or
coordinator message triggered that scheduled turn. Native Stop and explicit
Recovery events are distinguished in `completion-events.jsonl` beside the roster.

This establishes actual idle recovery and continued consumption of worker results.
It does not establish native Stop enforcement or completion/integration of the
entire Hydra wave. The existing heartbeat remains bounded by the roster deadline
(10 September 2026, 01:42:23 UTC), cancellation, and no-progress checks. It must
pause on completion, a concrete blocker, or exhausted recovery bounds.
The recovery prompt also checks for an interrupted preceding turn, so it must not
treat its own scheduled invocation as authorization to undo a user's stop.

The scheduler's stored next-run time, rather than an estimate from the interval,
was used to verify execution. Do not promise exact five-minute wall-clock recovery.

Sources: local roster and completion event log under
`$CODEX_HOME/team-leader/01a08317-27ac-7680-a095-17e98d95764b/`, app thread status,
and the app's read-only automation run metadata. Codex documents hook trust in
[Hooks](https://learn.chatgpt.com/docs/hooks) and same-chat scheduled follow-ups in
[Scheduled tasks](https://learn.chatgpt.com/docs/automations).
