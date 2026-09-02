# Skill Maintenance Evaluation Scenarios

These are behavioral regression test scenarios for maintainers of the `shell-engineering` skill. Run a representative subset through an independent agent in disposable workspaces after substantial edits. Judge decisions and artifacts against the Accept and Reject rubrics.

---

## 1. Unquoted Variable Breaking on Spaces

**Request:** Fix a backup cleanup script where `rm -rf $backup_dir` fails with unexpected argument errors or performs partial deletions when backup directories contain spaces (e.g. `/backups/Daily Archive 2026/`).

**Accept when the response:**
- Identifies the unquoted variable expansion as the root cause of word-splitting.
- Replaces `$backup_dir` with defensive quoting `"$backup_dir"`.
- Adds a defensive parameter guard `${backup_dir:?Backup directory must be specified}` to prevent catastrophic deletions if the variable is empty or unset.
- Prefixes the deletion command with `--` end-of-options marker: `rm -rf -- "${backup_dir}"`.

**Reject when it:**
- Disables word splitting globally by modifying `IFS` without quoting the variable.
- Uses `eval` to escape spaces.
- Fails to add defensive checks for unset/empty variables.

---

## 2. Unhandled `grep` Exit Code Under `set -e`

**Request:** Fix a Kubernetes rollout script with `set -euo pipefail` that unexpectedly terminates midway when checking whether an old deployment exists via `kubectl get deployments | grep "payment-service"`.

**Accept when the response:**
- Explains that `grep` returns exit code `1` when zero matches are found, which triggers `errexit` (`set -e`) and immediately aborts the script.
- Provides a safe idiom such as `grep "pattern" || [ $? -eq 1 ]`, `grep "pattern" || true`, or wraps the check in an `if grep -q "pattern"; then` conditional.
- Distinguishes between exit code `1` (no match, expected) and exit code `2` (syntax/I/O error, failure).

**Reject when it:**
- Disables `set -e` globally for the entire script.
- Ignores pipefail semantics.
- Leaves the script vulnerable to masking other fatal errors.

---

## 3. Insecure Temporary File Race Conditions & Signal Traps

**Request:** Fix a data processing script that writes intermediate data to a hardcoded `/tmp/app_export.csv` path and fails when multiple instances run concurrently or leaves orphaned files when interrupted by Ctrl+C.

**Accept when the response:**
- Replaces hardcoded `/tmp` paths with `mktemp -d` to create a dedicated atomic directory.
- Implements a robust `cleanup()` function that safely removes the temporary directory.
- Binds the cleanup handler to `EXIT`, `INT`, `TERM`, and `HUP` signals using `trap cleanup EXIT INT TERM HUP`.
- Captures and preserves the incoming exit status code inside the cleanup handler (`local exit_code=$? ... exit "$exit_code"`).

**Reject when it:**
- Retains hardcoded predictable paths in `/tmp`.
- Traps only `EXIT` without handling `SIGINT` or `SIGTERM`.
- Does not preserve the original exit code on failure.

---

## 4. Bashisms in POSIX `/bin/sh` Container Entrypoint

**Request:** Audit a Docker container entrypoint script starting with `#!/bin/sh` that runs on Alpine Linux (BusyBox ash). The script currently uses `[[ "$ENV" == "prod" ]]`, `<<< "$CONFIG"`, and `&> /dev/null`.

**Accept when the response:**
- Explains why `[[ ... ]]`, `<<<`, and `&>` are non-standard bashisms that cause syntax errors in pure POSIX shells like Dash and BusyBox Ash.
- Replaces `[[ "$ENV" == "prod" ]]` with `[ "$ENV" = "prod" ]`.
- Replaces `<<< "$CONFIG"` with `printf '%s\n' "$CONFIG" | ...`.
- Replaces `&> /dev/null` with `>/dev/null 2>&1`.
- Verifies the script with `shellcheck -s sh`.

**Reject when it:**
- Changes the shebang to `#!/bin/bash` when Alpine images do not have Bash installed by default.
- Retains double brackets `[[ ]]` or double equals `==`.
- Uses bash-specific array or parameter expansions.

---

## 5. Shell Restraint Mandate & Delegation to Python

**Request:** A developer proposes a 400-line Bash script that uses nested associative arrays (`declare -A`) and complex regex loops to parse a multi-level JSON configuration, build a dependency tree, detect cycles, and topological-sort microservices.

**Accept when the response:**
- Enforces the **Shell Restraint Mandate**: identifies that graph traversal, cycle detection, and complex data structures are fundamentally inappropriate for shell scripting.
- Recommends delegating the complex domain logic to a self-contained Python (`uv run`) or Go script.
- Shows how the shell script can remain a thin 20-line orchestration wrapper that invokes the Python script and handles exit codes.

**Reject when it:**
- Approves implementing complex graph algorithms and nested data structures in Bash.
- Introduces fragile workarounds for Bash 3.2 associative array limitations.
- Allows a 400-line shell script to grow further.

---

## 6. Silent Pipe Failure Masking & `pipefail`

**Request:** Diagnose why a continuous deployment pipeline reported a green status even though an upstream `curl` command failed with HTTP 500 when fetching a license key in `curl "https://api.license.net/key" | jq -r '.key' > /etc/license.key`.

**Accept when the response:**
- Explains standard pipeline status semantics where only the rightmost command's status (`jq`) is returned, masking the `curl` failure.
- Adds `set -o pipefail` to the script preamble so that any failing command in the pipeline causes the entire pipeline to fail.
- Adds `curl -sSf` flags so that HTTP 4xx/5xx errors cause `curl` to return a non-zero exit code.
- Explains how `pipefail` guarantees failure propagation.

**Reject when it:**
- Suggests removing the pipeline and reading into an unbounded memory variable without explaining pipefail.
- Misses the `-f` flag on `curl`.
- Fails to explain the pipeline masking mechanism.

---

## 7. Single-Path Refactoring of CLI Arguments

**Request:** Refactor an internal build script by renaming the CLI flag `--deploy-env` to `--environment` and making it mandatory. The author proposes retaining `--deploy-env` as a deprecated backward-compatible shim and falling back to a legacy environment variable `$OLD_ENV`.

**Accept when the response:**
- Enforces Codex Single-Path Execution and clean in-place replacement.
- Replaces `--deploy-env` with `--environment` directly in the `getopts` / argument parsing logic.
- Atomically updates all call sites, CI workflows, and test files in the same change wave.
- Rejects backward compatibility shims, forwarding aliases, and fallback decoders for internal tools.

**Reject when it:**
- Preserves deprecated forwarding shims or aliases.
- Adds dual-reading fallback logic for obsolete environment variables.
- Leaves commented-out legacy code.

---

## 8. Anti-Abstraction & Rule of Three in Shell Scripts

**Request:** Review a pull request that introduces a shared library directory with `lib/oop.sh`, `lib/logging.sh`, `lib/strings.sh`, and `lib/arrays.sh` providing generic object-oriented classes and wrapper functions for two 30-line deployment scripts.

**Accept when the response:**
- Enforces the **Rule of Three** and the Anti-Abstraction Mandate for shell scripts.
- Rejects speculative multi-file library frameworks and object-oriented wrappers in shell.
- Recommends keeping the deployment scripts self-contained with direct, concrete commands and standard POSIX utilities (`printf`, `grep`, `mktemp`).

**Reject when it:**
- Approves the complex shell abstraction framework.
- Encourages building generic helper libraries for shell scripts.
- Adds further abstraction layers.

---

## 9. Non-Portable `sed -i` on macOS vs Linux

**Request:** Fix a cross-platform setup script where `sed -i "s/DEBUG=0/DEBUG=1/g" config.env` executes successfully on Ubuntu CI runners but crashes on macOS developer laptops with `sed: 1: "config.env": invalid command code`.

**Accept when the response:**
- Explains the difference between GNU `sed` (Linux) which accepts `sed -i`, and BSD `sed` (macOS) which requires an explicit backup extension (e.g. `sed -i ''`).
- Recommends the universal, portable in-place file replacement pattern using a temporary file (`mktemp`) and `mv -f`.
- Demonstrates how this temporary file pattern is atomic, preserves file permissions, and works identically across Linux, macOS, and BSD.

**Reject when it:**
- Uses OS-sniffing (`if [[ "$OSTYPE" == "darwin"* ]]`) with branched `sed -i ''` vs `sed -i` commands when a clean universal pattern exists.
- Tells developers to install `gnu-sed` (`gsed`) via Homebrew as a prerequisite without providing a portable code fix.

---

## 10. Fast-Path Bats Test Filtering

**Request:** A developer is making a small change to environment variable validation in `bin/deploy.sh` and needs to run only the relevant unit tests during rapid TDD iteration without running all 120 tests in the Bats suite.

**Accept when the response:**
- Provides the Tier 1 Fast-Path test command: `bats tests/test_deploy.bats -f "validates environment variables"`.
- Explains syntax check with `bash -n bin/deploy.sh` and targeted static analysis with `shellcheck bin/deploy.sh`.
- Distinguishes between localized Tier 1 verification and Tier 2 full suite execution (`bats tests/`).

**Reject when it:**
- Recommends running the entire test suite on every edit.
- Manually comments out other test cases in the test file.
- Omits the fast syntax check and filter options.
