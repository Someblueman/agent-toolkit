# omp/

Oh My Pi adapter. Unlike the codex adapter (copy-based), OMP installation is
**symlink-based**: `~/.omp/agent` points back into this repo so the toolkit is
the single source of truth. Edit files here; changes are live on the next OMP
session (and `omp config get <key>` picks them up immediately).

## What `install.sh omp` creates

| Link at `~/.omp/agent/` | Target in this repo | Purpose |
|---|---|---|
| `config.yml` | `configs/omp/config.yml` | Settings: model roles, fallback chains, compaction, memory |
| `skills/` | `skills/` | Shared SKILL.md instructions (OMP-native format already) |
| `agents/` | `agents/` | Task-agent definitions (`explorer.md` etc.) |

## Notes

- `AGENTS.md` is **not** installed: OMP discovers `~/.codex/AGENTS.md` through
  its Codex discovery source, so installing a copy would double-load the policy.
- Codex MCP servers (`node_repl`, `openaiDeveloperDocs`) are likewise discovered
  from `~/.codex/config.toml` automatically.
- `omp config set <key> <value>` may replace the `config.yml` symlink with a
  real file. If that happens, re-run `scripts/install.sh omp --force` to restore
  the link, or just edit `configs/omp/config.yml` directly.
- Targeted at OMP with the `openai-codex`, `opencode-go`, `opencode-zen`, and
  `openrouter` providers authenticated.
