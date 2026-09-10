---
name: teamwork-preview
description: Run an approval-gated multi-agent project team for substantial software, research, document-review, simulation, or proof work. Use when the user invokes Teamwork or asks for an interviewed, independently verified agent-team workflow; do not use for routine delegation or a small task that the user has not asked to run as Teamwork.
---

# Teamwork Preview

Reproduce the useful shape of Antigravity's `/teamwork-preview` with Codex-native subagents: interview first, execute only an approved brief, keep the primary thread focused on user intent and integration, and require independent verification before claiming completion.

## Non-negotiable lifecycle

Teamwork has two phases. Never collapse them.

1. **Prompt crafting.** Interview the user, persist the verbatim request and evolving brief in a non-project draft directory, and wait for explicit approval. Do not edit project files, launch implementation agents, or create the execution workspace during this phase.
2. **Autonomous execution.** After approval, create durable run artifacts, launch the team, work through milestones, and run the blocking verification gates. Routine execution decisions do not require further approval; permissions, destructive actions, external writes, purchases, and material scope expansion still do.

Read [interview-and-brief.md](references/interview-and-brief.md) before conducting Phase 1. Once the user approves, read [orchestration.md](references/orchestration.md), [verification.md](references/verification.md), and [artifacts.md](references/artifacts.md) before starting Phase 2.

## Select an execution path

Choose from the approved brief; tell the user which path was selected.

- **General:** Multi-file engineering, migrations, simulations, or broad research. Decompose into milestones and run independent implementation and E2E-verification tracks.
- **Iterative:** One contained change the user explicitly wants kept small. Use one explorer, one worker, then independent review and audit. Do not manufacture milestones.
- **Document review:** Give independent reviewers distinct lenses, then synthesize evidence and dissent. No implementation worker unless the approved brief asks for edits.
- **Math/proof:** Run independent solution attempts, a counterexample/challenger lane, and a verifier.
- **Math/proof large team:** Select when the user explicitly asks for a large or very large team on a hard proof, bound, or combinatorial search. Use tournament rounds that promote only independently checked candidates.

If the task is too small to benefit, say so during the interview and offer the Iterative path. If the user still wants Teamwork, honor it without inflating the scope.

## Roles

Use the matching custom agents when available: `teamwork_orchestrator`, `teamwork_explorer`, `teamwork_worker`, `teamwork_test_designer`, `teamwork_critic`, `teamwork_challenger`, `teamwork_auditor`, and `teamwork_success_auditor`. If a client cannot select custom agent types but supports model overrides, spawn the orchestrator as a Sol high-effort subagent and specialists as Luna subagents with the relevant role contract in each prompt. If neither custom roles nor coordinator model selection is available, report the capability failure before implementation.

Spawn every teammate as a descendant in the current collaboration tree. The primary spawns one `teamwork_orchestrator` with `fork_turns="none"`; that orchestrator directly spawns and manages its specialist descendants. Do not create or message a separate Codex task, projectless thread, app thread, or CLI process as a dispatch substitute unless the user explicitly asks for separate tasks. Record a teammate as active only after the collaboration spawn operation returns its real identifier.

Use `gpt-5.6-sol` at high effort for the Project Orchestrator. Use `gpt-5.6-luna` at medium effort for fast specialist execution by default and Luna high for adversarial or integrative judgment. Keep the primary agent's current model for final synthesis and acceptance. Do not replace an explicitly requested model.

## Primary-agent ownership

The primary thread acts as user liaison, sentinel, and final integration owner. It must:

- preserve the approved request and authorization boundaries;
- be the sole writer and authority for the top-level plan, agent roster, progress, verification record, and recovery decisions;
- personally inspect relevant diffs, surrounding code, and command evidence;
- reconcile conflicting reports by evidence, not vote count;
- run or directly witness the final acceptance command;
- refuse to claim completion until the Success Auditor confirms the approved criteria and the primary independently agrees.

Subagent reports are evidence, never authority. The Project Orchestrator directly coordinates its descendants and returns structured milestone handoffs to the primary. The primary may inspect or message any descendant by its canonical task path, but it does not duplicate routine scheduling. The orchestrator proposes top-level coordination updates to the primary and cannot approve its own work or make external/destructive decisions for the user.

## Completion

Finish with a concise handoff separating:

- what was delivered;
- what was independently verified, including exact commands or evaluation methods;
- remaining uncertainty or rejected criteria;
- repository and publication state.

If a gate fails, return its actionable findings for repair within the approved attempt/time budget. Auditor replacement, crashed lanes and fresh gates consume that same budget; do not reset it by spawning a replacement. If bounds were not agreed, propose them before starting the team. If the team cannot satisfy a criterion within the agreed bounds, report partial completion honestly rather than weakening the criterion or fabricating success.
