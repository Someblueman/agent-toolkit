# Phase 2: Orchestration

## Topology

The primary thread is the persistent Sentinel and integration owner. Spawn one `teamwork_orchestrator` for the approved brief with `fork_turns="none"` as a descendant in the current collaboration tree. The role configuration selects a Sol high-effort coordinator with nested collaboration tools. The orchestrator owns decomposition, direct descendant dispatch, scheduling, waiting, and recovery; the primary alone writes the top-level plan, roster, progress, and verification artifacts, handles user-facing decisions, and performs the final integrated review.

Never use app task creation, app-thread messaging, projectless threads, or separate Codex tasks as an implicit subagent fallback. In particular, do not use `create_thread`, `send_message_to_thread`, or `list_threads` to dispatch or relay team work. Those operate on separate user-visible tasks rather than the current collaboration tree and require explicit user authorization. A dispatch is active only after the collaboration spawn call returns a real task path or agent identifier; do not pre-populate a roster with planned agents marked as running.

## Hierarchical direct dispatch

The Teamwork tree is physical, not merely logical:

```text
primary Sentinel
└── Project Orchestrator (Sol high)
    ├── explorers and test designer (Luna)
    ├── milestone workers (Luna)
    └── critic, challenger, auditor, and success auditor (Luna)
```

1. The primary gives the orchestrator the approved brief, coordination-artifact paths, repository root, authorization boundaries, and its complete role contract.
2. The orchestrator proposes the milestone plan. The primary inspects and records the accepted plan before implementation dispatch.
3. The orchestrator spawns its own descendants directly with the matching Teamwork roles and `fork_turns="none"`. Every prompt contains the complete Agent task contract below.
4. The orchestrator records only canonical task paths returned by successful spawns, waits for each wave, synthesizes results, and replaces failed or stale lanes within the approved bounds.
5. At every writer boundary, the orchestrator returns a milestone handoff to the primary. The primary personally inspects the resulting diff and surrounding code before authorizing the next dependent write wave.
6. The primary may inspect the full collaboration tree or contact a descendant by canonical path when evidence is missing, but routine dispatch and result routing remain with the orchestrator.

If the spawned orchestrator does not expose collaboration tools, stop before implementation and report a runtime capability failure. Do not flatten the team, turn the primary into a spawn relay, or create another queue, daemon, app task, or CLI subprocess as a hidden fallback.

For General projects, run two logically independent tracks:

1. **Implementation track:** Decompose by module or ownership boundary. Workers implement focused, non-overlapping milestones.
2. **E2E track:** A `teamwork_test_designer` derives opaque-box checks from requirements and acceptance criteria, not from the implementation plan. It may begin alongside exploration, but must not depend on internal design except for approved public entry points.

Do not spawn agents merely to fill capacity. Use parallelism only for independent work, and honor the live runtime limit even if the configured cap is higher. Reserve capacity for the coordinator and a verification wave.

## General execution loop

1. **Baseline:** The primary records repository root, active instructions, dirty state, and the exact approved brief. Existing user changes are out of bounds unless included in the brief.
2. **Decompose:** The orchestrator proposes three to seven milestones at one abstraction level, their dependencies, public contracts, owned file sets, and acceptance checks. The primary inspects and records the accepted plan. Tightly coupled changes stay in one milestone.
3. **Explore:** Launch one to three read-only explorers on distinct questions. Each returns evidence with paths, symbols, risks, and a recommended approach. The orchestrator synthesizes; it does not concatenate reports.
4. **Implement:** Assign each worker an exclusive write scope. In a shared checkout, run writers sequentially by default. Parallel writers require either user-approved isolated copies/worktrees or genuinely disjoint paths plus primary-agent before/after status and diff checks. Shared-interface changes happen first or are owned by one worker and consumed after landing.
5. **Integrate:** The primary reviews each returned change before starting a dependent write wave. It inspects the diff and relevant surrounding code, resolves overlap, and runs scope-calibrated checks.
6. **Verify:** Run the Critic, Challenger, and Auditor gates in [verification.md](verification.md). On failure, open a fresh explorer/worker repair wave with the full evidence, then repeat verification.
7. **Milestone close:** Update plan and progress artifacts with exact outputs and commands. A milestone is done only when its assigned criteria pass.
8. **Project close:** Run the approved end-to-end acceptance command. The primary performs and records its integrated conformance review but explicitly withholds the completion claim. Then run a fresh Success Auditor against that complete record. Only after `SUCCESS CONFIRMED` may the primary make the final completion decision.

The E2E track should cover every requirement, important boundaries and failures, cross-feature interactions, and realistic user scenarios. Calibrate counts to the project; do not copy a fixed test quota when fewer high-signal cases prove the behavior.

## Other paths

### Iterative

Use a single contained loop: explorer → worker → critic/challenger/auditor → primary acceptance. Keep the user's existing working directory and targeted verification. Do not create artificial project management layers.

### Document review

Assign two to four read-only reviewers distinct lenses such as correctness, feasibility, evidence quality, security, user impact, or clarity. Add a challenger to test central assumptions. The primary cites the source locations, distinguishes consensus from dissent, and does not edit the document unless approved.

### Math/proof

Run at least two independent solution approaches plus a counterexample search. A verifier checks every promoted proof step or computational result without seeing the authors' confidence claims. In large-team mode, use rounds: generate candidates in parallel, independently check them, discard failures, and deepen only surviving approaches.

## Agent task contract

Every dispatch states:

- role and concrete objective;
- approved requirement or milestone being served;
- files and evidence to read;
- exclusive write scope, or explicit read-only status;
- prohibited actions and authorization boundaries;
- expected artifact or return format;
- exact completion and verification conditions.

Dispatch directly from the orchestrator through the current thread's collaboration-agent mechanism. After each spawn returns, the orchestrator includes the canonical identifier and actual status in its next handoff so the primary can record it in the roster. If spawning fails, record the failure; never represent a merely planned lane as running.

Writable agents place scratch material under their assigned coordination directory, never in the source tree. Read-only agents return their structured handoff in their final collaboration response. Production code and tests go only to explicitly owned paths.

Prompt-level ownership is not a filesystem boundary. Before every write wave, record the current status/diff and each worker's allowed paths. After each worker returns, the primary compares the new status/diff with that record and rejects or reverts through a user-approved recovery path any out-of-scope edit. Never claim hard isolation unless the runtime actually provides it. Do not create a worktree or project copy unless the approved brief authorizes it.

## Progress, liveness, and recovery

Use Codex agent status and bounded waits rather than shell sleeps or cron emulation. Give the user concise updates at meaningful transitions and at least once per minute during long work. After dispatch, repeat this primary-side loop:

1. Wait for the next agent event for at most 60 seconds using the available agent-wait mechanism.
2. On timeout, inspect the live collaboration-agent roster and any durable `progress.md` or command session output; the primary updates the run's `PROGRESS.md` with the observed state.
3. If a running agent has no observable progress across two checks and is not inside a healthy long-running command, send a focused status request naming the expected next evidence.
4. If a third check is unchanged or the agent has failed, interrupt it and launch a fresh collaboration-tree replacement from the last inspected handoff or captured collaboration response. The primary records the replacement and reason.
5. Stop the loop only when the agent returns, is replaced, or new user input changes the run.

- Never treat an ordinary long-running command as failure without inspecting its output or session.
- At a milestone boundary, replace an orchestrator whose context is visibly degraded. Require a structured final response containing completed work, active agents, decisions, evidence, and next steps. If the orchestrator has an explicitly writable coordination directory it may also persist a handoff there. The primary verifies and records the handoff before launching the successor.

Do not mark the whole run blocked merely because one agent fails. Retry, replace, repartition, or continue with unaffected work. Ask the user only when progress needs new authority or a material product decision.
