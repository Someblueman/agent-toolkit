# hooks/

Executable lifecycle hooks and their supporting modules live here. Agent-specific registration examples live in `configs/<agent>/`.

## Quality hook

- `session/quality.py` is the Codex JSON entry point.
- `session/quality_hook.py` prompts for missing project verification setup, reports
  the repository's definition of green, checks tools, gives fast post-tool feedback,
  and verifies the full automated inventory at Stop with bounded repair continuation.
  Manual evidence remains an explicit responsibility of the agent/reviewer.
- `tools/quality/` supplies the shared checker and language tooling.

The entry point receives event JSON on stdin and returns Codex hook JSON on stdout. A Stop-hook block is expressed in JSON with exit code 0. Per-session fingerprints are stored outside the repository in the user cache.

See [quality setup](../tools/quality/README.md) for installation and trust instructions. Create other hook categories when an implementation needs them.
