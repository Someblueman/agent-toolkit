---
name: plan
description: Collaboratively develop and revise one agent-readable plan file. Use when asked to iterate on a plan or use plan; agreeing on the document does not launch implementation.
---

# Plan

Develop the design with the user and keep one coherent brief that another agent can act on
without reading the conversation. This works in ordinary conversation; no special planning
mode or execution runner is required.

## Develop the proposal

- Start with the existing conversation and relevant project instructions, code, and checks.
  Reuse an existing plan when it covers this work. Follow the user's chosen location or the
  repository's planning convention; otherwise choose a descriptive Markdown file under
  `docs/plans/` and tell the user its path. Respect any restriction on project writes and use
  an allowed draft location instead. Do not overwrite an unrelated file.
- Write a concrete initial proposal from what is known. Ask only questions whose answers
  materially change scope, design, acceptance, or authorization. Recommend a choice with its
  tradeoff instead of turning the conversation into a questionnaire.
- Distinguish user-agreed decisions, agent proposals, and unresolved assumptions. Do not convert
  a suggestion or silence into agreement. Record enough rationale to prevent a later agent from
  reopening a settled choice without new evidence.
- Ground consequential choices in the actual system. Investigate uncertainties with read-only
  evidence; propose a small prototype when running code would decide the issue. Execute that
  prototype only within authorization already given. Neither delegation nor implementation is
  implied by a planning request.

## Keep one current file

Update the same file after substantive decisions or corrections. Rewrite superseded sections
and their dependent acceptance criteria so contradictory instructions do not survive. Keep
only rejected alternatives whose rationale will help future decisions; do not append the chat
transcript or create a new plan for every revision.

Use as much of this structure as the work needs:

- Outcome, intended user, scope, and explicit exclusions.
- Relevant current behavior and source locations; identify facts still needing verification.
- Constraints and decisions, with brief rationale and agreement status.
- Chosen or proposed approach, including a realistic usage example when an interface matters.
- Cohesive work stages and real dependencies, each with observable completion evidence.
- Acceptance checks with expected outcomes; label proposed or unavailable checks honestly.
- Open questions and the next decision or investigation needed.
- Handoff context: working location, authorization boundaries, and whether execution is authorized.

Keep implementation details only where they express a real contract or settled decision. Do
not invent task counts, architecture layers, or elaborate schedules to fill a template.

## Review and hand off

For each iteration, explain what changed and surface the most consequential unresolved choice.
Link the file so the user can inspect it. Before handoff, read it as a fresh agent: ensure each
requirement has meaningful acceptance evidence, paths resolve or are clearly proposed, and no
open question is disguised as an instruction. A valid format does not validate the design.

Agreeing with or saving the plan does not authorize execution. Continue implementation when
the user has actually authorized it, using the existing execution workflow if requested; do
not launch a runner merely because the plan is ready. Follow repository policy for committing
the requested document, without treating that commit as approval of its proposed design.
