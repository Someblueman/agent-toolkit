---
name: workflow
description: Create a repository-aware, AFK-compatible implementation plan and submit it to the deterministic runner. Use when the user invokes $workflow or asks Codex to plan and launch an unattended software change; do not use for an ordinary plan that the user wants only as prose.
---

# Workflow

Turn the user's software request into a validated task DAG and submit it without
requiring the user to hand-author YAML or start a separate Codex session.

## Workflow

1. Resolve the target Git repository from an explicit path or the current
   workspace. Read its active instructions, inspect Git status, and inspect only
   the files needed to understand architecture and repository-native checks.
   Preserve dirty work. AFK runs from committed Git state, so stop and explain
   the boundary only if the requested work depends on uncommitted content.
2. Convert the request into the smallest useful DAG. Keep a localized change as
   one task. Split only where work has a real dependency or independently useful
   acceptance boundary. Each task must have concrete instructions and focused,
   executable checks; final checks validate the integrated result.
3. Read [references/afk-plan-format.md](references/afk-plan-format.md), then write
   the complete bundle beneath `${AFK_HOME:-~/.afk}/plans/`. Never add planning
   or runner files to the target repository. Use a descriptive, collision-free
   plan name and a `tasks/` instruction file for every node.
4. Run `afk plan lint <plan.yaml>`. If it fails, correct the bundle and rerun
   until the CLI accepts it. Do not submit an unvalidated plan.
5. Run `afk plan graph <plan.yaml>` and inspect the rendered dependencies for
   missing, reversed, or ceremonial edges. Briefly tell the user what will run,
   but do not wait for another approval unless the user asked for plan-only
   output or a genuinely unresolved choice would materially change the work.
6. Submit with `afk run <plan.yaml> --repo <repository>`. Stay with the command
   until it returns a terminal status. Report the run ID, branch, result commit,
   evidence directory, validation/review status, and any blocker.

If `afk` is unavailable, report that installation problem; do not replace CLI
validation with visual inspection or invent another plan format.

## Boundaries

- A direct `$workflow` request authorizes creating the external plan bundle and
  starting its local AFK run. It does not authorize pushing, merging, publishing,
  deleting branches, or changing the user's original checkout.
- Ask a concise question only when the answer cannot be inferred from the repo
  and would substantially alter scope or acceptance. Otherwise make reasonable
  repository-grounded assumptions and proceed.
- The plan-authoring agent chooses tasks and writes instructions. The AFK CLI is
  the authority for schema validity, dependency traversal, checks, retries,
  review, and terminal status.
- Never claim success from the plan text or worker report. Use the runner's Git,
  command, and independent-review evidence.
