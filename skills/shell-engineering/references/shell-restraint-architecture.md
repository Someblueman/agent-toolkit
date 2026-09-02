# Shell Restraint & Architecture

Read this guide when deciding whether a task belongs in shell, designing script architecture, structuring glue code, or determining when to delegate to Python, Go, `jq`, or `awk`.

---

## 1. The Shell Restraint Mandate

Shell script is fundamentally designed for **process execution, command orchestration, pipeline composition, and lightweight filesystem operations**. It is not a general-purpose application programming language. Writing complex domain logic or data manipulation in shell leads to subtle quoting bugs, unhandled edge cases in whitespace/special characters, poor performance, and untestable code.

### The Golden Rule of Shell Restraint
> **Use shell exclusively as the thin orchestration glue between robust, purpose-built executables. The moment a script requires complex state, nested data structures, floating-point arithmetic, or exceeds ~150–200 lines of code, immediately delegate to Python, Go, `jq`, or `awk`.**

### What Belongs in Shell vs What is Forbidden

| Category | ✅ Belongs in Shell | ❌ FORBIDDEN in Shell |
|---|---|---|
| **Orchestration** | Invoking compilers, linters, test runners, Docker, Git commands | Orchestrating complex distributed multi-node state machines |
| **Data Structures** | Flat positional arguments (`"$@"`), simple indexed lists | Trees, graphs, nested dictionaries, in-memory relational tables |
| **Data Formats** | Passing files/streams directly to `jq`, `sed`, `awk`, `python` | Parsing JSON, YAML, XML, or HTML using Bash regex, `grep`, or `cut` |
| **Arithmetic** | Integer increment counters (`$((count + 1))`), exit code math | Floating-point math, financial calculations, trigonometric functions |
| **Networking** | Invoking `curl` or `rsync` with clear exit code checks | Writing custom HTTP protocol parsers, websocket clients, or OAuth token flows |
| **Concurrency** | Bounded background execution (`wait "$pid"`), single subshells | Complex worker pools, semaphore queues, lock-free synchronization |

---

## 2. Delegation Decision Matrix

When approaching a task, evaluate requirements against this matrix to select the right tool:

| Requirement / Complexity | Recommended Tool | Invocation Pattern / Rationale |
|---|---|---|
| Querying or transforming structured JSON | `jq` | `jq -r '.items[] \| select(.active) \| .id' input.json` (Avoid multi-line `sed`/`awk` hacks) |
| Delimited column extraction & text summary | `awk` | `awk -F',' '$3 > 100 { sum += $3; count++ } END { print sum/count }' data.csv` |
| Fast stream text replacement | `sed` | `sed 's|/var/log/old|/var/log/new|g' input.txt` |
| Complex JSON/YAML parsing, REST API client, data validation | Python (`uv run`) | `uv run --with requests,pydantic script.py` (Full type safety, rich error handling) |
| High-throughput file processing, concurrent worker pools, native CLI | Go (`go run`) | `go run ./cmd/processor` (Compile-time safety, high concurrency performance) |
| System service lifecycle, container entrypoint, CI pipeline step | Bash (`set -euo pipefail`) | Self-contained, zero-dependency process coordination |

---

## 3. Anti-Patterns & Pragmatic Alternatives

| Anti-Pattern | Operational Risk | Pragmatic Replacement |
|---|---|---|
| **Regex JSON Parsing** (`grep -o '"id": "[^"]*"'`) | Breaks on nested structures, unescaped characters, multi-line values, or key ordering changes. | Delegate to `jq`: `jq -r '.id'`. |
| **Associative Array Graph Walk** (`declare -A graph`) | Bash 3.2 incompatibility on macOS; high memory consumption; fragile error propagation. | Delegate to a 20-line Python script using `dataclasses` and `dict`. |
| **Floating Point via `bc` Loops** (`echo "$a * 1.5" \| bc`) | Forking subshells inside loops causes severe performance degradation; brittle error trapping. | Compute in a single `awk` or `python` pass. |
| **God-Script Sprawl** (500+ line bash script) | Untestable spaghetti code; subtle quoting bugs; unmaintainable signal handling. | Split into small, focused CLI tools written in Go or Python. |
| **Custom Shell Frameworks** (`source lib/oop.sh`) | Unnecessary abstraction layers; obscures command execution; breaks tooling like ShellCheck. | Apply the **Rule of Three**: use direct concrete commands and keep scripts self-contained. |

---

## 4. Architecture of a Robust Glue Script

Every production Bash script should follow a structured, predictable layout:

```bash
#!/usr/bin/env bash
# ==============================================================================
# Script: deploy_service.sh
# Purpose: Build, tag, and publish Docker container images to registry.
# ==============================================================================
set -euo pipefail
IFS=$'\n\t'

# ------------------------------------------------------------------------------
# 1. Global Constants & Configuration (Read-only)
# ------------------------------------------------------------------------------
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd -P)"
readonly SCRIPT_NAME="$(basename "$0")"
readonly REGISTRY="${REGISTRY:-registry.internal.net}"
readonly TIMEOUT_SECONDS=300

# ------------------------------------------------------------------------------
# 2. Cleanup & Trap Handling
# ------------------------------------------------------------------------------
TMP_DIR=""

cleanup() {
  local exit_code=$?
  if [[ -n "${TMP_DIR:-}" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
  exit "$exit_code"
}

trap cleanup EXIT INT TERM HUP

# ------------------------------------------------------------------------------
# 3. Helper Functions (Single responsibility, local variables)
# ------------------------------------------------------------------------------
log_info() {
  printf '[INFO] [%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
}

log_error() {
  printf '[ERROR] [%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
}

usage() {
  cat <<EOF
Usage: ${SCRIPT_NAME} [OPTIONS] <service_name> <version_tag>

Options:
  -h, --help        Display this help message and exit
  -d, --dry-run     Print actions without executing builds

Arguments:
  service_name      Name of the microservice directory under services/
  version_tag       Semver or Git commit SHA tag for the image
EOF
}

# ------------------------------------------------------------------------------
# 4. Entrypoint (main function called at EOF)
# ------------------------------------------------------------------------------
main() {
  local dry_run=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      -d|--dry-run)
        dry_run=1
        shift
        ;;
      -*)
        log_error "Unknown option: $1"
        usage
        exit 2
        ;;
      *)
        break
        ;;
    esac
  done

  if [[ $# -ne 2 ]]; then
    log_error "Missing required arguments."
    usage
    exit 2
  fi

  local service_name="$1"
  local version_tag="$2"
  local target_image="${REGISTRY}/${service_name}:${version_tag}"

  TMP_DIR="$(mktemp -d "/tmp/${SCRIPT_NAME}.XXXXXX")"
  log_info "Created scratch workspace at ${TMP_DIR}"

  if [[ "$dry_run" -eq 1 ]]; then
    log_info "[DRY-RUN] Would build and push: ${target_image}"
    return 0
  fi

  log_info "Building image: ${target_image}"
  docker build -t "$target_image" "services/${service_name}"
  docker push "$target_image"
  log_info "Successfully deployed ${target_image}"
}

# Execute main passing all command-line arguments
main "$@"
```

### Key Architectural Idioms:
1. **`main "$@"` at end of script**: Guarantees the script is completely parsed into memory before executing. If a script is truncated or modified mid-execution (e.g. via `git pull` or network share updates), execution will not abort midway through an incomplete function.
2. **Readonly Global Configuration**: Uppercase `readonly` variables declare configuration once at top of file.
3. **Local Variables in Functions**: Always use `local` for function-scoped variables to prevent pollution of the global namespace.
4. **Standardized Stderr Logging**: Log diagnostic messages to `>&2` so stdout remains clean for piping to downstream tools.

---

## 5. Concrete Code Comparisons

### Example 1: JSON Data Extraction

❌ **ANTI-PATTERN: Brittle regex and sed parsing in Bash**
```bash
# Brittle: Breaks on unexpected whitespace, newlines, or escaped quotes
response=$(curl -s "https://api.internal.net/users")
user_emails=$(echo "$response" | grep -o '"email": "[^"]*"' | cut -d'"' -f4)
for email in $user_emails; do
  echo "Processing $email"
done
```

✅ **PRAGMATIC: Delegating structured extraction to `jq`**
```bash
# Robust: Handles arbitrary valid JSON, null values, and special characters cleanly
response=$(curl -sSf "https://api.internal.net/users")
while IFS= read -r email; do
  [[ -n "$email" ]] || continue
  printf 'Processing %s\n' "$email"
done < <(echo "$response" | jq -r '.users[].email // empty')
```

---

### Example 2: Complex State & Data Processing

❌ **ANTI-PATTERN: 200 lines of Bash associative arrays for metric aggregation**
```bash
declare -A metric_sums
declare -A metric_counts

while IFS=, read -r timestamp host metric_name value; do
  metric_sums["$metric_name"]=$(echo "${metric_sums["$metric_name"]:-0} + $value" | bc)
  metric_counts["$metric_name"]=$(( ${metric_counts["$metric_name"]:-0} + 1 ))
done < metrics.csv
# Incompatible with macOS Bash 3.2, slow bc subshells, fragile string math
```

✅ **PRAGMATIC: Delegating data aggregation to a self-contained Python script**
```bash
# Invoked seamlessly from shell glue via uv
uv run --with polars python - << 'EOF'
import polars as pl

df = pl.read_csv("metrics.csv", has_header=False, new_columns=["ts", "host", "metric", "value"])
agg = df.group_by("metric").agg([
    pl.col("value").mean().alias("avg_value"),
    pl.col("value").count().alias("count")
])
print(agg)
EOF
```

---

## 6. Single-Path Refactoring in Shell Scripts

When updating CLI arguments, function signatures, or environment variables in shell scripts:
1. **Atomically Update Call Sites**: Change the function or option name directly in place. Update all calling scripts, CI workflows, and documentation in the same commit.
2. **Forbid Legacy Option Shims**: Never retain `--old-flag` as an undocumented pass-through alias to `--new-flag` unless required by external backwards compatibility contracts.
3. **Delete Dead Wrapper Scripts**: Avoid creating `script_v2.sh` alongside `script.sh` or leaving commented-out legacy implementations.
