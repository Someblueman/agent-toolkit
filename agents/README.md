# agents/

Reusable agent profiles. Each profile is the *behavioral definition* of an agent — system prompt, persona, tool allowlist — separate from any single vendor's config format.

## Convention

A profile lives at `agents/<name>/` and contains:

- `AGENT.md` — system prompt and behavioral spec.
- `tools.txt` (or `tools.yaml`) — the allowlist of tool names this profile may use.
- Optional `examples/` with sample invocations.

Vendors wire these profiles into their native format under `configs/<vendor>/`.

## Existing profiles

*None yet.*

Engineering policies (e.g. `AGENTS.md`) are **per-agent** and live under `configs/<agent>/`. This keeps each vendor's policy standalone and editable without touching the shared agent layer.