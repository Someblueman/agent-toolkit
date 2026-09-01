# agent-toolkit

A vendor-neutral home for skills, hooks, agents, and tools that improve AI coding assistants (Codex, Claude Code, OpenCode, Antigravity, Pi, and friends).

The toolkit is organized around **agent-agnostic primitives** in the top-level directories and **per-agent adapter layers** in `configs/`. This lets one well-written `SKILL.md` be reused across multiple agents without forking the content.

## Layout

```
agent-toolkit/
├── README.md
├── skills/        # SKILL.md-style instructions agents can load
├── hooks/         # Pre-tool, post-tool, and session lifecycle hooks
├── agents/        # Reusable agent profiles (system prompts + tool allowlists)
├── tools/         # Standalone tools scripts can invoke (repo-inspector, context-builder, ...)
├── scripts/       # install.sh, sync.sh, validate.sh — repo-level utilities
├── configs/       # Per-agent adapters that wire the above into Codex / Claude / ...
├── templates/     # Reusable prompt + project scaffolds
└── docs/          # catalog.md, compatibility.md, contributing.md
```

## Quick start

1. Clone this repo somewhere stable (e.g. `~/.agent-toolkit`).
2. Run `./scripts/install.sh <agent>` to copy the relevant `configs/<agent>` pieces into the agent's home directory.
3. Pick the skills you want from `skills/` — they are described in [docs/catalog.md](docs/catalog.md).
4. Re-run `./scripts/sync.sh` whenever this repo updates to refresh your local copies.

## Principles

- **Source of truth lives in the top-level dirs.** `configs/` only contains glue.
- **Skills are agent-agnostic.** Use `SKILL.md` with YAML frontmatter so any agent can render them.
- **Hooks are shell scripts.** Anything executable counts; agents can wrap them however they need.
- **No agent-specific files in shared dirs.** If a skill needs agent-specific behavior, put it in `configs/<agent>/`.

See [docs/contributing.md](docs/contributing.md) for the full rules.