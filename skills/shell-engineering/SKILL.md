---
name: shell-engineering
description: Implement, review, debug, and optimize Bash and POSIX shell scripts, CLI pipelines, and automation. Use for shell scripts, orchestration glue, strict error handling, defensive quoting, portable parameter expansion, shellcheck, and bats tests.
---

# Shell Engineering

Produce the smallest correct Bash or POSIX shell change or focused review requested. Enforce the Shell Restraint Mandate, strict error handling, defensive quoting, and automated verification with ShellCheck and Bats.

## 1. Start with the repository

Before modifying or creating shell scripts, inspect the repository instructions and the smallest set of files (target 3-5 files) that establish the operational environment:

1. **Interpreter & Target Dialect**: Check the shebang (`#!/bin/sh` for POSIX vs `#!/usr/bin/env bash` for Bash) and deployment environment (Linux distro, macOS with default Bash 3.2, FreeBSD, Alpine/Busybox).
2. **Configuration & Linting**: Inspect `.shellcheckrc`, `.editorconfig`, CI workflow definitions, and existing test harnesses.
3. **Test Infrastructure**: Check for `bats-core`, custom subshell test runners, or `make test` targets.
4. **Identify Scope**: Distinguish between orchestration glue, build scripts, deploy automation, and standalone CLI tools. Do not alter unrelated scripts or refactor established project idioms without instruction.

## 2. Non-negotiable defaults

- **The Shell Restraint Mandate**: Restrict shell strictly to orchestration, process execution, environment manipulation, and file-system plumbing. Strictly FORBID complex domain logic, in-memory data structures (trees, graphs, nested maps), floating-point arithmetic engines, or distributed state machines in shell. When complex state or structured data makes shell difficult to maintain, consider Python (`uv run`), Go (`go run`), `jq`, or `awk`.
- **Strict Execution Modes**:
  - Choose Bash error handling deliberately: `set -euo pipefail` can help, but handle expected failures explicitly. Change IFS only when the parsing contract requires it.
  - For POSIX shell, choose `set -eu` only with its context-dependent error behavior understood.
- **Defensive Quoting**: Double-quote EVERY parameter expansion, command substitution, and variable reference (`"$var"`, `"$@"`). Never use unquoted `$var` or `$*` unless word-splitting or glob expansion is explicitly and provably required.
- **Deterministic Signal & Exit Cleanup**: Always allocate temporary resources via `mktemp -d` and bind deterministic cleanup functions to `EXIT`, `INT`, `TERM`, and `HUP` signals using an EXIT cleanup trap and separate signal handlers that exit 130, 143 and 129 respectively.
- **Dialect Discipline (POSIX vs Bash)**:
  - If shebang is `#!/bin/sh`, enforce strict POSIX compliance. Ban all bashisms: `[[ ... ]]`, `<<<`, `&>`, `${arr[@]}`, `declare`, `local` extensions, and Bash regex `=~`.
  - If shebang is `#!/usr/bin/env bash`, preserve compatibility with Bash 3.2 (macOS default) unless the repository explicitly targets Bash 4+ or Bash 5+. Avoid `declare -A` (associative arrays), `readarray`/`mapfile`, and `${var,,}` parameter transformations in portable scripts.
- **Single-Path Execution & In-Place Refactoring**: Refactor shell functions, CLI options, and script arguments in place. Atomically update all callers, flags, and test cases in the same change wave. Forbid deprecated option shims, fallback flags, forwarding wrapper scripts, and ghost/commented-out code.
- **Anti-Abstraction & Rule of Three**: Forbid multi-layer shell library abstractions (e.g. `lib_logging.sh`, `lib_arrays.sh`, `oop_shell.sh`). Write direct, concrete commands. Keep scripts self-contained and transparent.
- **Safe Pipeline Design**: Always design pipelines to survive `pipefail`. Handle expected non-zero exits (such as `grep` finding zero matches) explicitly without triggering unintended script abortion. Use `find -print0 | xargs -0` or `while IFS= read -r -d ''` for robust NUL-delimited stream processing.
- **Actionable Error Reporting**: Print diagnostic and error messages to standard error (`printf '%s\n' "error: ..." >&2`) and exit with meaningful status codes: `0` for success, `1` for runtime failure, `2` for invalid CLI arguments/syntax.

## 3. Tiered Verification

Discover and follow the repository's test infrastructure. Match verification scope to the risk of the change:

### Tier 1 (Fast-Path - TDD & Localized Edits)
Run targeted, fast verification during rapid iteration:
- **Syntax Check**: `bash -n script.sh` or `sh -n script.sh`
- **Targeted ShellCheck**: `shellcheck -x -s bash script.sh` or `shellcheck -x -s sh script.sh`
- **Targeted Bats Test Filter**: `bats tests/test_deploy.bats -f "validates environment variables"`
- **Subshell Dry-Run / Help Check**: `./script.sh --help` or `./script.sh --dry-run`

### Tier 2 (Full Verification - Architecture & CI Gates)
Run full verification for critical pipelines, deployment hooks, and multi-script releases:
- **Full Bats Test Suite**: `bats tests/`
- **Repository-Wide ShellCheck**: `shellcheck -x **/*.sh`
- **Cross-Shell Compatibility Matrix**: Verify execution across `/bin/sh` (dash, ash, busybox) and `/bin/bash` (macOS 3.2, Linux 5.x).
- **Signal Handling & Trap Verification**: Test interrupt resilience with `SIGINT` (`kill -2`) and abnormal termination.

## 4. References Routing Table

| Topic / Task | Reference Document |
|---|---|
| Shell boundary rules, delegation criteria to Python/Go/jq/awk, glue architecture | [references/shell-restraint-architecture.md](references/shell-restraint-architecture.md) |
| `set -euo pipefail`, subshell traps, signal handling (`EXIT`/`TERM`), exit codes | [references/bash-strict-modes.md](references/bash-strict-modes.md) |
| POSIX `/bin/sh` vs Bash 3.2 vs Bash 5.x, bashisms catalog, portable parameter expansions | [references/portability-posix.md](references/portability-posix.md) |
| Defensive quoting, word splitting, globbing, path resolution, `getopts` argument parsing | [references/defensive-quoting-paths.md](references/defensive-quoting-paths.md) |
| Pipelines, stream processing, safe `jq`, `awk`, `sed`, `grep`, and `xargs -0` integration | [references/external-tools-pipelines.md](references/external-tools-pipelines.md) |
| `shellcheck` directives, `bats-core` test harness, mocking, CI pipeline verification | [references/tooling-testing.md](references/tooling-testing.md) |

## 5. Maintain this skill
