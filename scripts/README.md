# scripts/

Repo-level utility scripts. These operate on the toolkit itself (install, sync, validate) rather than on user projects.

## Scripts

- `install.sh` — copy a `configs/<agent>/` payload into an agent's home directory.
- `sync.sh` — refresh local agent configs from this repo.
- `validate.sh` — check that `skills/`, `hooks/`, `agents/`, `tools/` follow conventions.

All scripts should:

- Be executable (`chmod +x`).
- Use `set -euo pipefail`.
- Accept `--help` and print usage.

## Convention

Implementations land here as the toolkit matures. For now this directory contains the names and the rules.