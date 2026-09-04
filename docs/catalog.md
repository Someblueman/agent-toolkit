# Catalog

The index of everything shippable in this toolkit. Updated when skills, hooks, agents, or tools are added or removed.

## Skills

| Name | Description | Status |
|------|-------------|--------|
| [c-engineering](../skills/c-engineering/) | Implement, review, debug, and optimize C programs, libraries, and systems. | stable |
| [code-simplification](../skills/code-simplification/) | Diagnose and remove accidental complexity; enforce complexity budgets with differential parity testing. | draft |
| [define-goal](../skills/define-goal/) | Define a clear, bounded goal for the session before acting on it. | stable |
| [hardware-aware-optimization](../skills/hardware-aware-optimization/) | Hardware-aware optimization playbooks: SIMD, branchless, custom allocators, lock-free, PGO/LTO. | draft |
| [fanout](../skills/fanout/) | Fan out a prompt to one-shot local workers (Agy / OpenCode). | stable |
| [go-engineering](../skills/go-engineering/) | Idiomatic Go implementation, review, and tooling. | stable |
| [profiling-software-performance](../skills/profiling-software-performance/) | Noise-controlled benchmarking and profiling for systems, managed, and lazy runtimes. | draft |
| [haskell](../skills/haskell/) | Haskell implementation, type-driven design, and review. | stable |
| [pragmatic-engineering](../skills/pragmatic-engineering/) | Cross-language engineering principles and the `check_anti_bloat.py` enforcement script. | stable |
| [python-engineering](../skills/python-engineering/) | Idiomatic Python implementation, review, testing, and packaging. | stable |
| [rust-engineering](../skills/rust-engineering/) | Idiomatic Rust implementation, review, and tooling. | stable |
| [shell-engineering](../skills/shell-engineering/) | Shell scripting best practices, safety, and portability. | stable |
| [typescript-engineering](../skills/typescript-engineering/) | Idiomatic TypeScript implementation, review, and tooling. | stable |

Status values: `scaffold` (placeholder exists), `draft` (real content, not validated), `stable` (validated + used in the wild).

## Codex-specific skills

| Name | Source | Installation |
|---|---|---|
| teamwork-preview | `configs/codex/native-skills/teamwork-preview/` | Selected for Codex; imported from the existing personal installation on 2026-09-04 without changing behavior. |
| workflow | `configs/codex/native-skills/workflow/` | Selected for Codex; imported from the existing personal installation on 2026-09-04 without changing behavior. Requires the external `afk` CLI. |

`configs/codex/skills.txt` is the explicit Codex selection. Draft shared skills and `fanout` remain available in the repository but are not installed into Codex by default.

## External skill ownership

Codex's `.system` skills and plugin-cache skills remain vendor-managed; their source is not copied here. The personal installations of `frontend-design`, `develop-web-game`, `playwright`, and `playwright-interactive` were selected for removal on 2026-09-04 because they are seldom used. The user identifies these as official external skills; their exact upstream versions were not independently established. Do not reintroduce local forks during toolkit refresh. If needed later, install from a verified upstream source through the normal skill installer.

## Hooks

*None yet.* See [hooks/](../hooks/).

## Agents

*None yet.* See [agents/](../agents/).

## Agent policies

| Name | Description | Status |
|------|-------------|--------|
| [codex/AGENTS.md](../configs/codex/AGENTS.md) | Codex engineering policy: anti-bloat, scope discipline, subagent restraint, tiered verification. Installed as `~/.codex/AGENTS.md`. | stable |

## Tools

| Name | Description | Status |
|------|-------------|--------|
| [fanout](../tools/fanout/) | Run bounded one-shot local workers (Agy / OpenCode) and collect structured results. | stable |

## Notable scripts

| Path | Description |
|------|-------------|
| [../skills/pragmatic-engineering/scripts/check_anti_bloat.py](../skills/pragmatic-engineering/scripts/check_anti_bloat.py) | Enforce anti-bloat rules (no shims, no ghost code, no premature abstractions). |
| [../skills/pragmatic-engineering/scripts/test_check_anti_bloat.py](../skills/pragmatic-engineering/scripts/test_check_anti_bloat.py) | Tests for the anti-bloat script. |
