# Repository instructions

This repository is the source of truth for reusable agent skills and their installers.
These instructions govern work on the toolkit. `configs/codex/AGENTS.md` is a separate
policy artifact installed into the user's Codex home; do not put repository layout rules there.

## Skill ownership and layout

- Every toolkit-owned skill has exactly one complete source package at `skills/<name>/`.
  This includes skills that require a particular agent or external tool.
- Keep `SKILL.md`, scripts, references, assets, and optional agent metadata together in that
  package. Codex picker metadata belongs at `skills/<name>/agents/openai.yaml`.
- Do not create skill sources or metadata overlays under `configs/`, including
  `configs/<agent>/skills/` or `native-skills/`. Do not fork a skill for each agent.
- `configs/<agent>/` contains adapter wiring: installation selection, agent policy, and
  runtime configuration. An adapter must consume the canonical packages in `skills/`.
- Document agent capabilities and external dependencies in the skill package. Central
  storage and successful installation do not establish runtime support on every agent.
- Installed copies and links are outputs. Edit the repository source and use its installer
  to refresh them. Vendor-managed system and plugin skills remain externally owned.

## Installation and changes

- Codex selects packages through `configs/codex/skills.txt` and copies each complete package.
  OMP links the central `skills/` directory. Preserve those contracts when changing adapters.
- When adding or moving a skill, update `docs/catalog.md`, affected installer selections,
  documentation, test paths, and quality-check roots together. Remove superseded sources.
- Preserve installer ownership tracking, local-edit protection, and unrelated installed
  content. A source relocation should preserve installed content and executable bits unless
  a behavior change is explicitly intended.
- For installer changes, run `python3 -m unittest discover -s scripts -p test_install.py -v`
  and exercise affected installers in temporary destinations, including repeat installation.
  Use `bash scripts/install.sh codex --check` for read-only comparison with the live install;
  do not use `--force` to conceal drift.
- Run relevant affected tests, configured quality checks when applicable, and
  `git diff --check`. Documentation-only changes need no new test harness.

See `skills/README.md`, `configs/<agent>/README.md`, and `docs/contributing.md` for details.
