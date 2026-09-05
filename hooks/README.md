# hooks/

Executable lifecycle hooks and their supporting modules live here. Agent-specific registration examples live in `configs/<agent>/`.

## Quality hook

- `session/quality.py` is the Codex JSON entry point.
- `session/quality_hook.py` handles prompt baselines, post-tool feedback, and bounded Stop-hook repair continuation.
- `tools/quality/` supplies the shared checker and language tooling.

The entry point receives event JSON on stdin and returns Codex hook JSON on stdout. A Stop-hook block is expressed in JSON with exit code 0. Per-session fingerprints are stored outside the repository in the user cache.

See [quality setup](../tools/quality/README.md) for installation and trust instructions. Create other hook categories when an implementation needs them.
