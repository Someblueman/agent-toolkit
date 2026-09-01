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

- [github-review/](github-review/) — review a GitHub PR with structured feedback.
- [deep-research/](deep-research/) — multi-source research workflow.
- [release-check/](release-check/) — pre-release sanity checks.

## Adding a new skill

1. `mkdir skills/<name>`
2. Add a `SKILL.md` with frontmatter.
3. Update [docs/catalog.md](../docs/catalog.md).
4. If any agent needs agent-specific wiring, add it under `configs/<agent>/`.