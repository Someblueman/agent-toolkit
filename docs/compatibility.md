# Compatibility

Which parts of this toolkit work with which agents, and at what level.

Legend: ✅ supported · 🟡 partial · ❌ not supported · 🚧 scaffold only

## Capability Layer Matrix

| Capability | Codex | Claude Code | OpenCode | Antigravity | Pi |
|---|:---:|:---:|:---:|:---:|:---:|
| Skills (`SKILL.md`) | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 |
| Hooks (shell scripts) | 🚧 | 🟡 | 🟡 | 🟡 | 🟡 |
| Agent profiles | 🚧 | 🟡 | 🟡 | 🟡 | 🟡 |
| Tools (standalone CLIs) | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Specific Capability: Fan-out Delegation (`fanout`)

| Role / Feature | Codex | OpenCode | Antigravity | Claude Code | Pi |
|---|:---:|:---:|:---:|:---:|:---:|
| **Orchestrator / Caller** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Worker Target (Agy / Gemini)** | N/A | N/A | ✅ | N/A | N/A |
| **Worker Target (OpenCode / Minimax)**| N/A | ✅ | N/A | N/A | N/A |
| **Adapter Configuration** | ✅ (`configs/codex/`) | ✅ (`lib/opencode_worker.mjs`) | ✅ (`schemas/`) | 🟡 | 🟡 |

### Harness & Agent Details

- **Codex**: Full support as task orchestrator. Dispatches subtasks via bash tool calls to `tools/fanout/bin/fanout`, loads instructions from `skills/fanout/SKILL.md`, and follows ingestion workflow in `configs/codex/README.md`.
- **OpenCode**: Full support both as caller orchestrator and as worker harness (`--harness opencode`). Spawns ephemeral SDK v2 instances per worker with support for arbitrary `--agent` profiles (`plan`, `build`, etc.) and arbitrary task-specific JSON payloads.
- **Antigravity (Agy)**: Full support both as caller orchestrator and as worker harness (`--harness agy`). Executes `gemini-3.7-flash-low` in plan sandbox mode with schema validation and automatic 1x transient retries.
- **Claude Code & Pi**: Full support as CLI caller orchestrators invoking `tools/fanout/bin/fanout`.

---

## General Notes

- **Skills** in this toolkit use a generic `SKILL.md` shape with YAML frontmatter. Agents that natively load `.claude/skills/` or `<agent>/skills/` style content consume these with minimal adapter glue in `configs/<agent>/`.
- **Hooks** are vendor-portable shell scripts. Each agent's adapter (`configs/<agent>/`) is responsible for invoking them at the right lifecycle point.
- **Tools** are the most portable layer — standalone executables callable from any agent possessing shell/subprocess execution capabilities.
- See `configs/<agent>/README.md` for agent-specific configuration and adapter details.
