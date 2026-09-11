# Codex adapter

Wires the shared toolkit into OpenAI Codex.

## What this adapter does

1. Installs [AGENTS.md](AGENTS.md) as `~/.codex/AGENTS.md`.
2. Installs skills selected in `skills.txt` under `~/.codex/skills/<name>/` (real directories copied from the repo). Every name resolves to one complete package at `skills/<name>/` in the repo root.
3. Installs per-skill Codex metadata (`openai.yaml` interface manifests) at `~/.codex/skills/<name>/agents/openai.yaml` so Codex's skill picker can show a display name and short description.

## Layout

```
configs/codex/
├── AGENTS.md
├── README.md
└── skills.txt
```

Each canonical `skills/<name>/` package contains its instructions, helpers, references,
and optional `agents/openai.yaml` picker metadata. The installer copies the package as-is;
there is no second source or metadata overlay in this adapter. `skills.txt` selects packages
for Codex and `AGENTS.md` supplies its installed policy.

The central `team-leader` and `teamwork-preview` packages require Codex capabilities;
`workflow` requires the external `afk` CLI. Central storage does not remove those runtime
requirements. See [skill compatibility](../../skills/README.md).

## Installing

`scripts/install.sh codex` syncs this adapter into `~/.codex/` (`CODEX_HOME` can select a different destination). It requires Python 3.10+. Run `--dry-run` to preview and `--check` to verify content without installation writes. Staging uses a temporary directory that is removed on completion.

The installer compares complete skill content, including interface metadata and executable bits. It excludes `__pycache__`, `*.pyc`, and `.DS_Store` consistently. `.agent-toolkit-install.json` records the fingerprint of each successfully installed or adopted item. Matching pre-existing content can be adopted; differing untracked content or local edits are preserved and reported with exit code 1. Changes to previously installed, unmodified content refresh automatically.

Inspect a conflict before using `--force`, which replaces conflicting selected items. `--prune` removes only retired items in the ownership record; an edited retired item requires `--force`. Items without an ownership record are never inferred to be obsolete. System skills, plugin caches, and other independent installations are outside this installer's ownership. Do not run concurrent installers for one destination.

The selected list includes the user-requested `code-simplification`, `hardware-aware-optimization`, and `profiling-software-performance` drafts. Installation does not establish their behavioral correctness or install optional profiling/compiler dependencies. `fanout` remains excluded because its standalone tool is not installed by this adapter.

The anti-bloat script lives at `skills/pragmatic-engineering/scripts/check_anti_bloat.py` and is installed at `~/.codex/scripts/check_anti_bloat.py` for convenience.

## Repository quality hooks

Quality hooks use the shared [quality installer](../../tools/quality/README.md), separately
from skill materialization. Run `tools/quality/bin/quality --root /path/to/repo setup --codex`
for a repository with its own `quality.json`. This provisions its selected tools and
registers hooks, reusing matching user-level JSON handlers. For first-time setup, select
the repository's language profiles and source roots as described in the quality guide.

`tools/quality/bin/quality install-codex --global` registers project setup and verification
hooks once in `CODEX_HOME`. Review/trust the definitions in Codex `/hooks`; installation
preserves trust and enablement settings. In a Git repository without a complete
`quality.json`, the prompt hook directs the agent to define that project's verification
criteria first. It does not install tools or modify projects during hook execution.
