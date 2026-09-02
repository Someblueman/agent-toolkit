# Codex adapter

Wires the shared toolkit into OpenAI Codex.

## What this adapter does

1. Installs [../../agents/global-policy.md](../../agents/global-policy.md) as `~/.codex/AGENTS.md`.
2. Installs each shared skill under `~/.codex/skills/<name>/` (symlinked, where Codex supports it).
3. Installs per-skill Codex metadata (`openai.yaml` interface manifests) at `~/.codex/skills/<name>/agents/openai.yaml` so Codex's skill picker can show a display name and short description.

## Layout

```
configs/codex/
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

The source `openai.yaml` files live here (not inside the shared skill) because they are Codex-specific manifests. The shared `skills/<name>/` directories are agent-agnostic.

## Installing

`scripts/install.sh codex` (TBD) will sync this adapter into `~/.codex/`.

The anti-bloat script lives at `skills/pragmatic-engineering/scripts/check_anti_bloat.py` and should be runnable from any working directory. Codex currently exposes it via the legacy `~/.codex/scripts/check_anti_bloat.py` shim; the shim becomes unnecessary once the install script is in place.