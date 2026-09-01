# Compatibility

Which parts of this toolkit work with which agents, and at what level.

Legend: ✅ supported · 🟡 partial · ❌ not supported · 🚧 scaffold only

| Capability | Codex | Claude Code | OpenCode | Antigravity | Pi |
|------------|:-----:|:-----------:|:--------:|:-----------:|:--:|
| Skills (`SKILL.md`) | 🚧 | 🟡 | 🟡 | 🟡 | 🟡 |
| Hooks (shell scripts) | 🚧 | 🟡 | 🟡 | 🟡 | 🟡 |
| Agent profiles | 🚧 | 🟡 | 🟡 | 🟡 | 🟡 |
| Tools (standalone CLIs) | ✅ | ✅ | ✅ | ✅ | ✅ |

## Notes

- **Skills** in this toolkit use a generic `SKILL.md` shape with YAML frontmatter. Agents that natively load `.claude/skills/` or `<agent>/skills/` style content should be able to consume these with minimal adapter work in `configs/<agent>/`.
- **Hooks** are vendor-portable shell scripts. Each agent's adapter (`configs/<agent>/`) is responsible for invoking them at the right lifecycle point.
- **Tools** are the most portable layer — they're plain executables.
- See `configs/<agent>/README.md` for agent-specific compatibility details as adapters are added.