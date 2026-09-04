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
├── tools/         # Standalone tools scripts can invoke (fanout, ...)
├── scripts/       # installer and its focused acceptance tests
├── configs/       # Per-agent adapters that wire the above into Codex / Claude / ...
├── templates/     # Reusable prompt + project scaffolds
└── docs/          # catalog.md, compatibility.md, contributing.md
```

## Quick start

1. Clone this repo somewhere stable (e.g. `~/.agent-toolkit`).
2. Review `configs/codex/skills.txt` for the selected Codex skills, described in [docs/catalog.md](docs/catalog.md).
3. Run `./scripts/install.sh codex --dry-run`, then `./scripts/install.sh codex`. Python 3.10+ is required. Use `omp` to install OMP's links and configuration.
4. Re-run the same installer after repository updates. For Codex, `./scripts/install.sh codex --check` verifies the installed content without changing it.

Codex refreshes unmodified managed content and reports local conflicts with exit code 1. Review differences before using `--force`. `--prune` removes only retired items recorded by this installer; independently installed skills and vendor-managed packages are left alone. See [Codex installation](configs/codex/README.md).

## Principles

- **Portable content lives in the top-level dirs.** Agent-specific policy, metadata, selection, and native skills live in `configs/<agent>/`.
- **Skills are agent-agnostic.** Use `SKILL.md` with YAML frontmatter so any agent can render them.
- **Hooks are shell scripts.** Anything executable counts; agents can wrap them however they need.
- **No agent-specific files in shared dirs.** If a skill needs agent-specific behavior, put it in `configs/<agent>/`.

See [docs/contributing.md](docs/contributing.md) for the full rules.
