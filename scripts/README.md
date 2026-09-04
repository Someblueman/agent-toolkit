# scripts/

Repo-level utility scripts. These operate on the toolkit itself (install, sync, validate) rather than on user projects.

## Scripts

- `install.sh codex` — install or refresh selected Codex skills, policy, and anti-bloat script.
- `install.sh codex --check` — read-only content comparison; exit 1 for missing, different, or retired managed items.
- `install.sh codex --dry-run` — preview updates without changing the installation.
- `install.sh codex --prune` — remove retired installer-owned content, preserving local edits unless `--force` is supplied.
- `install.sh omp` — link shared skills/agents and copy OMP configuration.
- `install_codex.py` — standard-library implementation of Codex materialization and ownership tracking; invoked by `install.sh`.
- `test_install.py` — isolated acceptance tests for the real installer CLI: `python3 -m unittest discover -s scripts -p test_install.py -v`.

All scripts should:

- Be executable (`chmod +x`).
- Use `set -euo pipefail`.
- Accept `--help` and print usage.

## Convention

Use the installer itself for refreshes; there is no separate sync command. Codex supports Python 3.10+ and `CODEX_HOME` for an isolated destination. Do not run multiple installers concurrently against one destination.
