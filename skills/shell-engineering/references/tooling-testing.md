# Tooling, Testing, & CI Verification

Read this guide when setting up static analysis with `shellcheck`, authoring automated unit and integration tests with `bats-core`, mocking external binaries, or configuring CI verification pipelines.

---

## 1. Static Analysis with ShellCheck

[ShellCheck](https://www.shellcheck.net/) is the mandatory static analysis tool for all Bash and POSIX shell scripts. It catches syntax errors, subtle quoting vulnerabilities, portability bugs, and edge cases.

### Canonical ShellCheck Commands

```bash
# Analyze a single Bash script following source includes (-x)
shellcheck -x -s bash bin/deploy.sh

# Analyze a POSIX script with strict POSIX compliance checks
shellcheck -x -s sh bin/entrypoint.sh

# Workspace-wide analysis across all shell files
shellcheck -x $(find . -type f -name "*.sh" -not -path "./.git/*")
```

### High-Priority ShellCheck Diagnostics

| Code | Violation Description | Remediation Pattern |
|---|---|---|
| **SC2086** | Double quote to prevent globbing and word splitting. | Replace `$var` with `"$var"`. |
| **SC2155** | Declare and assign separately to avoid masking return value. | Replace `local res=$(cmd)` with `local res; res=$(cmd)`. |
| **SC2046** | Quote this to prevent word splitting. | Replace `cmd $(subcmd)` with `cmd "$(subcmd)"` or an array. |
| **SC2181** | Check exit code directly with `if mycmd;` rather than `if [ $? -eq 0 ]`. | Use direct command in condition: `if git status; then ...`. |
| **SC2002** | Useless use of `cat`. | Replace `cat file \| grep pat` with `grep pat file`. |
| **SC2034** | Variable appears unused. | Verify if exported or intended for trap; prefix with `_` or export. |

### Documenting Intentional Exceptions
When an unquoted variable is genuinely required (e.g. intentional word splitting of trusted flags), disable the check locally and document the rationale:

```bash
# Intentional word splitting of trusted internal flags variable
# shellcheck disable=SC2086
docker run --rm $DOCKER_FLAGS "$IMAGE_NAME"
```

---

## 2. Automated Testing with Bats-Core

[Bats-core](https://github.com/bats-core/bats-core) (Bash Automated Testing System) is the standard automated testing framework for Bash scripts.

### Canonical Bats Test File (`tests/test_deploy.bats`)

```bats
#!/usr/bin/env bats

setup() {
  # Create isolated scratch workspace for each test
  export TEST_TMP_DIR
  TEST_TMP_DIR="$(mktemp -d "/tmp/bats_test.XXXXXX")"
  export MOCK_BIN_DIR="${TEST_TMP_DIR}/bin"
  mkdir -p "$MOCK_BIN_DIR"
  
  # Shadow PATH so test mocks are invoked before system binaries
  export PATH="${MOCK_BIN_DIR}:${PATH}"
  
  # Path to script under test
  export SCRIPT="${BATS_TEST_DIRNAME}/../bin/deploy.sh"
}

teardown() {
  if [[ -d "$TEST_TMP_DIR" ]]; then
    rm -rf "$TEST_TMP_DIR"
  fi
}

@test "deploy.sh: rejects missing required arguments with exit code 2" {
  run "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" =~ "Missing required arguments" ]]
}

@test "deploy.sh: displays help message on --help" {
  run "$SCRIPT" --help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage:" ]]
}

@test "deploy.sh: successfully executes dry-run mode" {
  run "$SCRIPT" --dry-run my-service v1.0.0
  [ "$status" -eq 0 ]
  [[ "$output" =~ "[DRY-RUN] Would build and push:" ]]
}

@test "deploy.sh: invokes docker build and push with correct image tag" {
  # Mock the docker binary
  cat << 'EOF' > "${MOCK_BIN_DIR}/docker"
#!/bin/sh
echo "MOCK_DOCKER: $*"
exit 0
EOF
  chmod +x "${MOCK_BIN_DIR}/docker"

  run "$SCRIPT" auth-service v2.1.0
  [ "$status" -eq 0 ]
  [[ "$output" =~ "MOCK_DOCKER: build -t registry.internal.net/auth-service:v2.1.0" ]]
  [[ "$output" =~ "MOCK_DOCKER: push registry.internal.net/auth-service:v2.1.0" ]]
}
```

---

## 3. Pure-Shell Test Harness Fallback

If Bats is not available in the environment, use this zero-dependency pure-shell test harness:

```bash
#!/usr/bin/env bash
set -euo pipefail

PASS_COUNT=0
FAIL_COUNT=0

assert_equals() {
  local expected="$1"
  local actual="$2"
  local test_name="$3"
  
  if [[ "$expected" == "$actual" ]]; then
    printf '  ✅ PASS: %s\n' "$test_name"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    printf '  ❌ FAIL: %s (Expected: "%s", Got: "%s")\n' "$test_name" "$expected" "$actual" >&2
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

test_help_flag() {
  local out
  out="$(./bin/deploy.sh --help 2>&1)" || true
  [[ "$out" == *"Usage:"* ]]
  assert_equals "0" "$?" "Displays usage on --help"
}

test_missing_args() {
  local status=0
  ./bin/deploy.sh >/dev/null 2>&1 || status=$?
  assert_equals "2" "$status" "Exits with code 2 on missing args"
}

main() {
  printf 'Running Shell Test Suite...\n'
  test_help_flag
  test_missing_args
  
  printf '\nResults: %d Passed, %d Failed\n' "$PASS_COUNT" "$FAIL_COUNT"
  if [[ "$FAIL_COUNT" -gt 0 ]]; then
    exit 1
  fi
}

main "$@"
```

---

## 4. Tiered Verification Fast-Path Recipes

### Tier 1 (Fast-Path - Rapid TDD Iteration)
```bash
# 1. Quick syntax verification
bash -n bin/deploy.sh

# 2. Fast targeted ShellCheck
shellcheck bin/deploy.sh

# 3. Fast targeted Bats test filter
bats tests/test_deploy.bats -f "dry-run"
```

### Tier 2 (Full Verification - Pre-Commit & CI)
```bash
# 1. Full workspace ShellCheck
shellcheck -x $(find . -type f -name "*.sh")

# 2. Full Bats suite execution
bats tests/

# 3. Cross-shell execution check
/bin/sh -n bin/*.sh
/bin/bash -n bin/*.sh
```
