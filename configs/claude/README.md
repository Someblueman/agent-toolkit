# claude/

Claude Code adapter. Installation is **link-based, per skill**:

- Each skill named in [skills.txt](skills.txt) is symlinked from
  `~/.claude/skills/<name>` to the canonical package at `skills/<name>/`, so edits here
  reach the next Claude Code session without reinstalling. `CLAUDE_CONFIG_DIR` selects a
  different Claude configuration directory.
- Unlike OMP, the whole `skills/` directory is not linked: Claude's user skills directory
  also holds skills the toolkit does not own (hand-written or synced skills), and
  several toolkit packages require Codex capabilities or external CLIs. See
  [skill compatibility](../../skills/README.md) before selecting more packages.

## What `install.sh claude` does

| Situation at `~/.claude/skills/<name>` | Result |
|---|---|
| Missing | Linked to `skills/<name>/`. |
| Already a link to this checkout's package | Left alone. |
| A link into this checkout's `skills/` under another name | Relinked. |
| Any other link, directory or file | Reported as a conflict (exit 1). `--force` replaces a link, or moves other content to `~/.claude/agent-toolkit-backups/<name>.<timestamp>`, outside `skills/` so Claude does not load it as a duplicate. |

- `--check` verifies the links without writing and fails on missing, conflicting or
  retired links.
- `--prune` removes links into this checkout's `skills/` whose names are no longer
  selected. Other links and directories are never touched.
- `--dry-run` prints the changes without making them.

Rerun the installer after editing `skills.txt`. After moving the checkout, existing links
point to the old path and are reported as conflicts; rerun with `--force`.

Agent-specific metadata such as `agents/openai.yaml` is part of each package and is
ignored by Claude Code. Targeted at Claude Code's user skills directory
(`~/.claude/skills/<name>/SKILL.md`).

## Backed-up personal setup (not installed)

These files are backups of the live copies under `~/.claude/`. `install.sh claude` does not
install them, and `skills.txt` does not select `sol` or `ambition-check`. Copy them by hand.

| Backup | Live location |
|---|---|
| [CLAUDE.md](CLAUDE.md) | `~/.claude/CLAUDE.md` |
| [output-styles/orchestrator.md](output-styles/orchestrator.md) | `~/.claude/output-styles/orchestrator.md` |
| [skills/sol/](../../skills/sol/) | `~/.claude/skills/sol/` |
| [skills/ambition-check/](../../skills/ambition-check/) | `~/.claude/skills/ambition-check/` |
| [hooks/session/ambition-check.sh](../../hooks/session/ambition-check.sh) | `~/.claude/hooks/ambition-check.sh` |

They also need these entries in `~/.claude/settings.json`:

```json
{
  "outputStyle": "Orchestrator",
  "env": { "CLAUDE_CODE_SUBAGENT_MODEL": "sonnet" },
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "~/.claude/hooks/ambition-check.sh", "timeout": 10 } ] }
    ]
  }
}
```

The output style applies to every Claude Code session that loads user settings, including
headless `claude -p` workers. A launcher that runs Claude as a worker should set
`CLAUDE_WORKER=1`, so that the hook tells the session to do its task without delegating.
`sol` also needs the `codex` CLI logged in with a ChatGPT account.
