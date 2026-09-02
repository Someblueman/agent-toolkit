# Bash Strict Modes & Execution Invariants

Read this guide when setting up shell execution flags, handling errors deterministically under `set -e`, managing temporary files, catching process signals, or writing exit traps.

---

## 1. The Canonical Strict Mode Header

Every production Bash script must start with the canonical strict mode preamble:

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
```

For POSIX-compliant `/bin/sh` scripts (where `pipefail` and `IFS=$'\n\t'` syntax are not standardized), use:

```bash
#!/bin/sh
set -eu
```

### Breakdown of Strict Mode Flags

| Flag | Name | Operational Invariant | Why It Is Mandatory |
|---|---|---|---|
| `-e` | `errexit` | Aborts execution immediately if any command returns a non-zero exit status (with specific context exceptions). | Prevents cascading corruption where subsequent commands execute on top of failed preceding steps. |
| `-u` | `nounset` | Treats unset or uninitialized variables and parameters as fatal errors during expansion. | Catches typos (e.g. `rm -rf "$TARGET_DR/data"` when variable is named `TARGET_DIR`), preventing catastrophic unintended deletions. |
| `-o pipefail` | `pipefail` | Sets pipeline exit status to the rightmost command with a non-zero status, or zero if all succeeded. | Prevents silent error masking where a failing producer is masked by a succeeding consumer (`failing_cmd \| cat` exits 0 without `pipefail`). |
| `IFS=$'\n\t'` | Field Separator | Changes Internal Field Separator from standard space/tab/newline to only newline and tab. | Prevents loop iteration over file paths or command outputs from splitting words on embedded spaces. |

---

## 2. Common `errexit` Pitfalls & Safe Workarounds

While `set -e` is essential, standard shell behavior contains subtle edge cases where `-e` can either silently deactivate or unexpectedly abort execution.

### Pitfall 1: Arithmetic Evaluation Returning Zero
In Bash, `(( expr ))` returns exit status `1` (failure) if the arithmetic expression evaluates to `0`. Under `set -e`, this immediately crashes the script.

❌ **ANTI-PATTERN: Crashing on initial count increment**
```bash
set -e
count=0
(( count++ )) # Post-increment evaluates to 0 (old value) -> exit status 1 -> SCRIPT CRASHES!
echo "Count is $count"
```

✅ **PRAGMATIC: Safe arithmetic assignments**
```bash
set -euo pipefail
count=0
count=$(( count + 1 )) # Safe variable assignment never returns non-zero exit status
# Or explicitly:
(( count += 1 )) || true
```

---

### Pitfall 2: `grep` Returning Exit Code 1 on Zero Matches
When `grep` finds no matches, it exits with status `1`. Under `set -e`, this is treated as a fatal failure rather than an empty result set.

❌ **ANTI-PATTERN: Unhandled `grep` under `set -e`**
```bash
set -e
# Crashes the script immediately if no active pods exist
active_pods=$(kubectl get pods | grep "Running")
echo "Active: $active_pods"
```

✅ **PRAGMATIC: Explicit fallback with exit code inspection**
```bash
set -euo pipefail
# Allow exit code 1 (no match), but still fail on exit code 2 (syntax/file error)
active_pods=$(kubectl get pods | grep "Running" || [ $? -eq 1 ])

# Alternatively, for boolean checks, use if condition:
if grep -q "Running" <<< "$pod_list"; then
  echo "Found running pods"
else
  echo "No running pods found"
fi
```

---

### Pitfall 3: Subshells Inside Conditional Statements
Under POSIX and Bash standards, if a command or subshell is part of the test condition in an `if`, `elif`, `while`, or `until` statement, or on the left side of `&&` or `||`, `errexit` is **disabled inside that entire command and its child subshells**.

❌ **ANTI-PATTERN: Expecting `-e` to catch errors inside checked helper functions**
```bash
set -e

perform_setup() {
  mkdir /protected/directory # Fails with permission denied
  touch /protected/directory/file.txt # Silently continues because errexit is disabled!
  return 0
}

# The if statement disables errexit inside perform_setup!
if perform_setup; then
  echo "Setup completed"
fi
```

✅ **PRAGMATIC: Explicit error checking inside functions**
```bash
set -euo pipefail

perform_setup() {
  if ! mkdir -p "/tmp/app_setup"; then
    printf 'error: failed to create setup directory\n' >&2
    return 1
  fi
  touch "/tmp/app_setup/file.txt"
}

perform_setup
```

---

## 3. Signal Handling & Atomic Cleanup Traps

Scripts often create temporary directories, lockfiles, or spawn background child processes. If a script exits unexpectedly or is interrupted by `SIGINT` (Ctrl+C) or `SIGTERM` (CI cancellation), orphaned resources must be cleaned up deterministically.

### Robust Multi-Signal Trap Pattern

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Scratch workspace variable
SCRATCH_DIR=""

cleanup() {
  # Capture the incoming exit code before executing cleanup commands
  local exit_code=$?
  
  # Remove temporary directory if created
  if [[ -n "${SCRATCH_DIR:-}" && -d "$SCRATCH_DIR" ]]; then
    rm -rf "$SCRATCH_DIR"
  fi

  # Kill background child jobs if any remain
  local pids
  pids=$(jobs -p)
  if [[ -n "$pids" ]]; then
    # shellcheck disable=SC2086
    kill -TERM $pids 2>/dev/null || true
  fi

  exit "$exit_code"
}

# Trap EXIT (normal termination) and common termination signals
trap cleanup EXIT INT TERM HUP

main() {
  # Allocate atomic scratch directory
  SCRATCH_DIR="$(mktemp -d "/tmp/myapp.XXXXXX")"
  
  # Do work...
  echo "Running work inside ${SCRATCH_DIR}"
}

main "$@"
```

### Signal Traps Summary Table

| Signal | Name | Trigger Scenario | Expected Handling |
|---|---|---|---|
| `EXIT` (0) | Shell Exit | Script terminates normally or via `exit` | Always execute cleanup (delete temp files, release locks) |
| `INT` (2) | `SIGINT` | User presses Ctrl+C in terminal | Terminate immediately, execute cleanup, propagate exit code 130 |
| `TERM` (15) | `SIGTERM` | CI system, Docker, or `kill` requests shutdown | Graceful stop, terminate child processes, execute cleanup, exit 143 |
| `HUP` (1) | `SIGHUP` | Controlling terminal or SSH session disconnects | Clean up and exit |

---

## 4. Atomic File Operations

To prevent corrupting target files during crashes, power failures, or concurrent reads, never write output directly to the destination path. Use the **atomic temporary file swap pattern**.

```bash
write_config() {
  local target_file="$1"
  local content="$2"
  local target_dir
  target_dir="$(dirname "$target_file")"

  # Create temp file in the SAME filesystem to ensure atomic mv rename
  local tmp_file
  tmp_file="$(mktemp "${target_dir}/tmp.config.XXXXXX")"

  # Write content to temporary file
  printf '%s\n' "$content" > "$tmp_file"
  chmod 0644 "$tmp_file"

  # Atomic rename (POSIX rename syscall replaces target_file atomically)
  mv -f "$tmp_file" "$target_file"
}
```

---

## 5. Exit Code Conventions

Always return meaningful exit codes conforming to standard POSIX and Linux conventions:

| Exit Code | Meaning | Example Scenario |
|---|---|---|
| `0` | Success | Normal successful completion |
| `1` | General runtime error | Network timeout, missing prerequisite, operation failure |
| `2` | Misuse of shell built-in or invalid CLI syntax | Missing required argument, unrecognized command-line flag |
| `126` | Command invoked cannot execute | Permission problem or command is not an executable |
| `127` | Command not found | Binary missing from `$PATH` |
| `128+N` | Fatal signal `N` | `130` for `SIGINT` (128+2), `143` for `SIGTERM` (128+15) |
