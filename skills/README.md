# skills/

Agent-agnostic skill definitions. Each subdirectory is one skill.

## Convention

Every skill is a directory of the form `skills/<skill-name>/` containing:

- `SKILL.md` — the primary instruction file. YAML frontmatter (name, description, when-to-use) followed by markdown instructions the agent will read.
- Optional `scripts/`, `references/`, `assets/` subdirectories.

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

- [fanout/](fanout/) — fan out a prompt to one-shot local workers (Agy / OpenCode).
- [code-simplification/](code-simplification/) — diagnose and remove accidental complexity with behavioral-invariance verification.
- [hardware-aware-optimization/](hardware-aware-optimization/) — hardware-aware optimization playbooks (SIMD, branchless, arenas, lock-free, PGO/LTO).
- [profiling-software-performance/](profiling-software-performance/) — noise-controlled benchmarking and profiling across systems, managed, and lazy runtimes.

## Adding a new skill

1. `mkdir skills/<name>`
2. Add a `SKILL.md` with frontmatter.
3. Update [docs/catalog.md](../docs/catalog.md).
4. If any agent needs agent-specific wiring, add it under `configs/<agent>/`.