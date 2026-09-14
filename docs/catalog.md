# Catalog

The index of everything shippable in this toolkit. Updated when skills, hooks, agents, or tools are added or removed.

## Skills

| Name | Description | Status |
|------|-------------|--------|
| [c-engineering](../skills/c-engineering/) | Implement, review, debug, and optimize C programs, libraries, and systems. | stable |
| [code-simplification](../skills/code-simplification/) | Diagnose and remove accidental complexity; enforce complexity budgets with differential parity testing. | draft |
| [define-goal](../skills/define-goal/) | Define a clear, bounded goal for the session before acting on it. | stable |
| [hardware-aware-optimization](../skills/hardware-aware-optimization/) | Hardware-aware optimization playbooks: SIMD, branchless, custom allocators, lock-free, PGO/LTO. | draft |
| [fanout](../skills/fanout/) | Fan out a prompt to one-shot local workers (Agy / OpenCode / Muse). | stable |
| [go-engineering](../skills/go-engineering/) | Idiomatic Go implementation, review, and tooling. | stable |
| [profiling-software-performance](../skills/profiling-software-performance/) | Noise-controlled benchmarking and profiling for systems, managed, and lazy runtimes. | draft |
| [haskell](../skills/haskell/) | Haskell implementation, type-driven design, and review. | stable |
| [pragmatic-engineering](../skills/pragmatic-engineering/) | Cross-language engineering principles and the `check_anti_bloat.py` enforcement script. | stable |
| [python-engineering](../skills/python-engineering/) | Idiomatic Python implementation, review, testing, and packaging. | stable |
| [rust-engineering](../skills/rust-engineering/) | Idiomatic Rust implementation, review, and tooling. | stable |
| [shell-engineering](../skills/shell-engineering/) | Shell scripting best practices, safety, and portability. | stable |
| [typescript-engineering](../skills/typescript-engineering/) | Idiomatic TypeScript implementation, review, and tooling. | stable |
| [investigate](../skills/investigate/) | Investigate questions using code, runtime evidence, and history; read-only by default. | draft |
| [prototype](../skills/prototype/) | Resolve design uncertainty with a small runnable experiment. | draft |
| [plan](../skills/plan/) | Collaboratively maintain one agent-readable plan without automatically launching execution. | draft |
| [reflect](../skills/reflect/) | Extract supported lessons and update the appropriate guidance within authorized scope. | draft |

Status values: `scaffold` (placeholder exists), `draft` (real content, not validated), `stable` (validated + used in the wild).

## Skills with runtime requirements

The shared `investigate`, `prototype`, `plan`, and `reflect` skills are selected for Codex with
explicit-only invocation (`$investigate`, `$prototype`, `$plan`, and `$reflect`). They are drafts
pending real-work pilots.

| Name | Source | Installation |
|---|---|---|
| team-leader | `skills/team-leader/` | Selected for Codex; uses independent workstream owners in authorized worktrees, focused specialists, leader-owned integration, and one recovery heartbeat. |
| teamwork-preview | `skills/teamwork-preview/` | Selected for Codex; imported from the existing personal installation on 2026-09-04 without changing behavior. |
| workflow | `skills/workflow/` | Selected for Codex; imported from the existing personal installation on 2026-09-04 without changing behavior. Requires the external `afk` CLI. |

All packages, including their optional agent metadata, live under `skills/`.
`configs/codex/skills.txt` is the explicit Codex selection. The user requested installation of the three draft skills (`code-simplification`, `hardware-aware-optimization`, and `profiling-software-performance`); their draft status remains unchanged. `fanout` is selected for Codex and uses the installer-managed `agent-toolkit-root.txt` to locate its standalone tool in this checkout.

## External skill ownership

Codex's `.system` skills and plugin-cache skills remain vendor-managed; their source is not copied here. The personal installations of `frontend-design`, `develop-web-game`, `playwright`, and `playwright-interactive` were selected for removal on 2026-09-04 because they are seldom used. The user identifies these as official external skills; their exact upstream versions were not independently established. Do not reintroduce local forks during toolkit refresh. If needed later, install from a verified upstream source through the normal skill installer.

## Hooks

| Name | Description | Status |
|---|---|---|
| [quality](../hooks/session/quality.py) | Codex lifecycle entrypoint for the local quality checker; preserves scope and bounds repair continuation. | draft |

## Agents

*None yet.* See [agents/](../agents/).

## Agent policies

| Name | Description | Status |
|------|-------------|--------|
| [codex/AGENTS.md](../configs/codex/AGENTS.md) | Codex engineering policy: anti-bloat, scope discipline, subagent restraint, tiered verification. Installed as `~/.codex/AGENTS.md`. | stable |

## Tools

| Name | Description | Status |
|------|-------------|--------|
| [fanout](../tools/fanout/) | Run bounded one-shot local workers (Agy / OpenCode / Muse) and collect structured results. | stable |
| [quality](../tools/quality/) | Provision pinned linters and run repository-defined behavioral checks through automatic preflight, edit feedback and completion hooks. | draft |

## Notable scripts

| Path | Description |
|------|-------------|
| [../skills/pragmatic-engineering/scripts/check_anti_bloat.py](../skills/pragmatic-engineering/scripts/check_anti_bloat.py) | Enforce anti-bloat rules (no shims, no ghost code, no premature abstractions). |
| [../skills/pragmatic-engineering/scripts/test_check_anti_bloat.py](../skills/pragmatic-engineering/scripts/test_check_anti_bloat.py) | Tests for the anti-bloat script. |
