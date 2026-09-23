# skills/

The canonical home for every toolkit skill. Each subdirectory is one complete package,
including skills that require a particular agent or external tool.

## Convention

Every skill is a directory of the form `skills/<skill-name>/` containing:

- `SKILL.md` — the primary instruction file. YAML frontmatter (name, description, when-to-use) followed by markdown instructions the agent will read.
- Optional `scripts/`, `references/`, `assets/` subdirectories.
- Optional agent metadata, such as `agents/openai.yaml` for the Codex skill picker.

A minimal `SKILL.md`:

```markdown
---
name: my-skill
description: One-line summary of what this skill does and when to load it.
---

# Instructions
...
```

## Existing skills

- [fanout/](fanout/) — model-agnostic review, critique, bug-hunt, and owned implementation workflows.
- [claude-bridge/](claude-bridge/) — continuing local exchanges with an isolated Claude peer.
- [code-simplification/](code-simplification/) — diagnose and remove accidental complexity with behavioral-invariance verification.
- [hardware-aware-optimization/](hardware-aware-optimization/) — hardware-aware optimization playbooks (SIMD, branchless, arenas, lock-free, PGO/LTO).
- [profiling-software-performance/](profiling-software-performance/) — noise-controlled benchmarking and profiling across systems, managed, and lazy runtimes.

## Adding a new skill

1. `mkdir skills/<name>`
2. Add a `SKILL.md` with frontmatter.
3. Update [docs/catalog.md](../docs/catalog.md).
4. Keep skill metadata inside the package; put installer selection and runtime wiring under `configs/<agent>/`.

## Installation and compatibility

Codex copies packages selected by `configs/codex/skills.txt`. OMP links this entire directory,
so all packages are visible there. Other adapters should consume these same packages.

Visibility does not establish runtime support: `team-leader` uses native collaboration
for specialist subagents, Codex app tools for larger tasks, and heartbeat recovery.
`teamwork-preview` requires the Codex collaboration capabilities described
in its instructions, and `workflow` requires the external `afk` CLI. Their instructions and
requirements remain part of the central package; relocation does not port those workflows.
