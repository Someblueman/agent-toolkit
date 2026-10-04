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
