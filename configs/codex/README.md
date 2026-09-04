# Codex adapter

Wires the shared toolkit into OpenAI Codex.

## What this adapter does

1. Installs [AGENTS.md](AGENTS.md) as `~/.codex/AGENTS.md`.
2. Installs skills selected in `skills.txt` under `~/.codex/skills/<name>/` (real directories copied from the repo). A name resolves to `skills/<name>/` at the repo root or `native-skills/<name>/` here, never both.
3. Installs per-skill Codex metadata (`openai.yaml` interface manifests) at `~/.codex/skills/<name>/agents/openai.yaml` so Codex's skill picker can show a display name and short description.

## Layout

```
configs/codex/
├── AGENTS.md
├── README.md
└── skills/
    ├── c-engineering/openai.yaml
    ├── define-goal/openai.yaml
    ├── go-engineering/openai.yaml
    ├── haskell/openai.yaml
    ├── python-engineering/openai.yaml
    ├── rust-engineering/openai.yaml
    ├── shell-engineering/openai.yaml
    └── typescript-engineering/openai.yaml
```

The `openai.yaml` files live here (not inside the shared skill) because they are Codex-specific manifests. The shared `skills/<name>/` directories are agent-agnostic. `AGENTS.md` is also Codex-specific. `native-skills/` owns the complete Codex-specific `teamwork-preview` and `workflow` packages, including their interface metadata and references. They are not exposed through OMP's shared-skill symlink.

## Installing

`scripts/install.sh codex` syncs this adapter into `~/.codex/` (`CODEX_HOME` can select a different destination). It requires Python 3.10+. Run `--dry-run` to preview and `--check` to verify content without installation writes. Staging uses a temporary directory that is removed on completion.

The installer compares composed skill content, including interface metadata and executable bits. It excludes `__pycache__`, `*.pyc`, and `.DS_Store` consistently. `.agent-toolkit-install.json` records the fingerprint of each successfully installed or adopted item. Matching pre-existing content can be adopted; differing untracked content or local edits are preserved and reported with exit code 1. Changes to previously installed, unmodified content refresh automatically.

Inspect a conflict before using `--force`, which replaces conflicting selected items. `--prune` removes only retired items in the ownership record; an edited retired item requires `--force`. Items without an ownership record are never inferred to be obsolete. System skills, plugin caches, and other independent installations are outside this installer's ownership. Do not run concurrent installers for one destination.

The selected list intentionally excludes toolkit drafts and `fanout`, whose standalone tool is not installed by this adapter. Add a skill to `skills.txt` only when its runtime dependencies are ready.

The anti-bloat script lives at `skills/pragmatic-engineering/scripts/check_anti_bloat.py` and is installed at `~/.codex/scripts/check_anti_bloat.py` for convenience.
