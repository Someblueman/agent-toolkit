# omp/

Oh My Pi adapter. Installation is **hybrid**:

- `skills/` and `agents/` are **symlinked** into `~/.omp/agent` so the toolkit
  stays the single source of truth for read-only content. Edit files here;
  changes are live on the next OMP session.
- `config.yml` is **copied** into `~/.omp/agent/config.yml`. OMP owns its config
  at runtime: it normalizes and rewrites the file whenever settings persist
  (e.g. an in-session model switch writes back `modelRoles.default`), and it
  creates a `config.yml.lock` next to the resolved config path. With a symlink
  those writes clobbered the repo copy, stripping all comments and dirtying
  the repo. Re-run `scripts/install.sh omp` to re-sync the repo copy over the
  live one (pass `--force` if OMP's rewrite drifted).

## What `install.sh omp` creates

| At `~/.omp/agent/` | Source in this repo | Install | Purpose |
|---|---|---|---|
| `config.yml` | `configs/omp/config.yml` | copy | Settings: model roles, fallback chains, compaction, memory |
| `skills/` | `skills/` | symlink | Shared SKILL.md instructions (OMP-native format already) |
| `agents/` | `agents/` | symlink | Task-agent definitions (`explorer.md` etc.) |

## Notes

- `AGENTS.md` is **not** installed: OMP discovers `~/.codex/AGENTS.md` through
  its Codex discovery source, so installing a copy would double-load the policy.
- Codex MCP servers (`node_repl`, `openaiDeveloperDocs`) are likewise discovered
  from `~/.codex/config.toml` automatically.
- Runtime setting changes (`omp config set`, in-session model switches) land in
  the live copy only. Make intended changes permanent by editing
  `configs/omp/config.yml` here and re-running `scripts/install.sh omp`.
- Targeted at OMP with the `openai-codex`, `opencode-go`, `opencode-zen`, and
  `openrouter` providers authenticated.
