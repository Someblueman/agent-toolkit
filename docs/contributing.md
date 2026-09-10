# Contributing

Thanks for helping grow the toolkit. This document covers the rules that keep the repo agent-agnostic and easy to fork.

## Core rules

1. **The top-level dirs hold the source of truth.** `configs/` only contains glue.
2. **Keep complete skills together.** Agent-specific skill metadata belongs inside `skills/<name>/` (for example `agents/openai.yaml`). Keep installation selection and runtime wiring in `configs/<agent>/`.
3. **Skills are `SKILL.md` files with YAML frontmatter.** Keep them short and focused.
4. **Hooks are executable shell scripts.** Python with a shebang is acceptable when shell isn't enough.
5. **Tools are standalone CLIs.** Anything stateful belongs in `tools/`, not in hooks.

## Adding a new skill

```
skills/<name>/SKILL.md
```

Frontmatter keys:

- `name` — kebab-case, matches the directory.
- `description` — one line. State **what** the skill does and **when** to load it.

Keep helpers and references in the same package. Document agent/tool requirements in its
instructions. Add optional Codex picker metadata at `agents/openai.yaml`, and select the
package in `configs/codex/skills.txt` when appropriate. Then update [catalog.md](catalog.md).

## Adding a new hook

Drop an executable in `hooks/<category>/` with a top-of-file comment explaining the event payload it expects. Add the per-agent wiring under `configs/<agent>/`.

## Adding a new agent profile

`agents/<name>/AGENT.md` with the system prompt + behavioral spec, plus `tools.txt` for the allowlist. Vendor config goes in `configs/<vendor>/`.

## Adding a new tool

`tools/<name>/bin/<name>` executable + `README.md` documenting input/output/exit codes.

## Pull request checklist

- [ ] New skill/hook/agent/tool appears in `docs/catalog.md`.
- [ ] If a new agent is targeted, an entry exists in `docs/compatibility.md` and an adapter stub in `configs/<agent>/`.
- [ ] No executable bits in `configs/` that should be in `tools/`.
- [ ] Scripts honor `--help`.

## Style

- Markdown: 100-char soft wrap, sentence case headings, fenced code blocks.
- Shell: `set -euo pipefail`, `#!/usr/bin/env bash`.
- YAML: 2-space indent, no tabs.