# Catalog

The index of everything shippable in this toolkit. Updated when skills, hooks, agents, or tools are added or removed.

## Skills

| Name | Description | Status |
|------|-------------|--------|
| [github-review](../skills/github-review/) | Review a GitHub PR with structured, severity-tagged feedback. | scaffold |
| [deep-research](../skills/deep-research/) | Multi-source research workflow for open-ended questions. | scaffold |
| [release-check](../skills/release-check/) | Pre-release sanity checks before tagging a version. | scaffold |
| [c-engineering](../skills/c-engineering/) | Implement, review, debug, and optimize C programs, libraries, and systems. | stable |
| [define-goal](../skills/define-goal/) | Define a clear, bounded goal for the session before acting on it. | stable |
| [go-engineering](../skills/go-engineering/) | Idiomatic Go implementation, review, and tooling. | stable |
| [haskell](../skills/haskell/) | Haskell implementation, type-driven design, and review. | stable |
| [pragmatic-engineering](../skills/pragmatic-engineering/) | Cross-language engineering principles and the `check_anti_bloat.py` enforcement script. | stable |
| [python-engineering](../skills/python-engineering/) | Idiomatic Python implementation, review, testing, and packaging. | stable |
| [rust-engineering](../skills/rust-engineering/) | Idiomatic Rust implementation, review, and tooling. | stable |
| [shell-engineering](../skills/shell-engineering/) | Shell scripting best practices, safety, and portability. | stable |
| [typescript-engineering](../skills/typescript-engineering/) | Idiomatic TypeScript implementation, review, and tooling. | stable |

Status values: `scaffold` (placeholder exists), `draft` (real content, not validated), `stable` (validated + used in the wild).

## Hooks

*None yet.* See [hooks/](../hooks/).

## Agents

| Name | Description | Status |
|------|-------------|--------|
| [codex](../agents/codex/) | Codex-style profile. | scaffold |
| [claude-code](../agents/claude-code/) | Claude Code-style profile. | scaffold |
| [pi](../agents/pi/) | Pi-style profile. | scaffold |

## Agent policies

| Name | Description | Status |
|------|-------------|--------|
| [codex/AGENTS.md](../configs/codex/AGENTS.md) | Codex engineering policy: anti-bloat, scope discipline, subagent restraint, tiered verification. Installed as `~/.codex/AGENTS.md`. | stable |

## Tools

| Name | Description | Status |
|------|-------------|--------|
| [repo-inspector](../tools/repo-inspector/) | Inspect a repo's structure. | scaffold |
| [context-builder](../tools/context-builder/) | Build a context bundle for an agent. | scaffold |

## Notable scripts

| Path | Description |
|------|-------------|
| [../skills/pragmatic-engineering/scripts/check_anti_bloat.py](../skills/pragmatic-engineering/scripts/check_anti_bloat.py) | Enforce anti-bloat rules (no shims, no ghost code, no premature abstractions). |
| [../skills/pragmatic-engineering/scripts/test_check_anti_bloat.py](../skills/pragmatic-engineering/scripts/test_check_anti_bloat.py) | Tests for the anti-bloat script. |