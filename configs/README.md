# configs/

Per-agent adapter layers. Each subdirectory contains the *vendor-native* files that wire this toolkit's shared skills, hooks, agents, and tools into a specific agent.

## Principle

The source of truth lives in the top-level directories (`skills/`, `hooks/`, `agents/`, `tools/`). Configs here are glue only — they reference, copy, or symlink to the canonical content.

## Existing configs

- [codex/](codex/) — OpenAI Codex adapter (TOML/JSON files Codex expects).

## Adding a new agent adapter

1. `mkdir configs/<agent>`
2. Add only the vendor-native files needed.
3. Where possible, reference shared skills via copy or symlink rather than re-authoring.
4. Document the agent version this targets in the subdir's README.