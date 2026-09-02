# Codex adapter

Wires the shared toolkit into OpenAI Codex.

## What this adapter does

1. Installs [AGENTS.md](AGENTS.md) as `~/.codex/AGENTS.md`.
2. Installs each shared skill under `~/.codex/skills/<name>/` (real dir, files copied from the repo).
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

The `openai.yaml` files live here (not inside the shared skill) because they are Codex-specific manifests. The shared `skills/<name>/` directories are agent-agnostic. `AGENTS.md` is also Codex-specific — each agent ships its own policy under its own `configs/<agent>/` directory.

## Installing

`scripts/install.sh codex` syncs this adapter into `~/.codex/`.

The anti-bloat script lives at `skills/pragmatic-engineering/scripts/check_anti_bloat.py` and is installed at `~/.codex/scripts/check_anti_bloat.py` for convenience. The legacy shim at the same path (a 35-line wrapper) becomes unnecessary once the install script is wired up.