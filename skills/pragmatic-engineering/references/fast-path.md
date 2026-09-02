# Fast-Path Decision Tree & Tiered Verification

Use this reference to select the appropriate verification tier and execute focused test commands.

## 1. Tier Selection Decision Matrix

| Change Scope | Risk Level | Verification Tier | Required Checks |
|---|---|---|---|
| Bug fix in single module | Low | **Tier 1 (Fast-Path)** | Targeted test file/filter + targeted linter/typecheck |
| Localized helper refactor | Low | **Tier 1 (Fast-Path)** | Targeted test suite for module |
| Minor feature in isolated file | Low | **Tier 1 (Fast-Path)** | New unit test + affected package tests |
| Documentation / comments / typo | Minimal | **Tier 1 (Fast-Path)** | Format check / spell check only |
| Core architectural overhaul | High | **Tier 2 (Full Verification)** | Full workspace acceptance command + all tests |
| Cryptographic primitive / Auth | High | **Tier 2 (Full Verification)** | Full test suite + security/fuzz/property checks |
| Concurrency / lock-free memory | High | **Tier 2 (Full Verification)** | Full test suite + ThreadSanitizer/Miri/stress tests |
| Durable schema migration | High | **Tier 2 (Full Verification)** | Migration integration tests + full suite |
| Public library published API | High | **Tier 2 (Full Verification)** | Semver checks + full workspace suite |

---

## 2. Targeted Test Command Recipes (Tier 1 Fast-Path)

### Rust (Cargo)
- Run a specific test function:
  ```bash
  cargo test test_function_name
  ```
- Run tests in a specific package and module:
  ```bash
  cargo test -p package_name --test test_file -- module::path
  ```
- Fast typecheck without full build:
  ```bash
  cargo check -p package_name
  ```

### Python (pytest)
- Run a specific test file:
  ```bash
  pytest tests/test_module.py
  ```
- Run a specific test by name expression:
  ```bash
  pytest -k "test_specific_behavior"
  ```

### TypeScript / JavaScript (Jest / Vitest)
- Run tests matching a specific pattern:
  ```bash
  npm test -- -t "specific behavior"
  ```
- Fast typecheck:
  ```bash
  npx tsc --noEmit
  ```

### Go
- Run a specific test in a package:
  ```bash
  go test -v ./pkg/submodule -run TestSpecificBehavior
  ```

---

## 3. Escalation Rules

Escalate from Tier 1 to Tier 2 if:
1. The targeted test uncovers an unexpected regression in a shared core type.
2. The change alters a type exported across 3+ crate/package boundaries.
3. The targeted check fails and the failure root cause is ambiguous.
