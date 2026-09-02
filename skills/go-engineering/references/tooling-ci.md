# Tooling, CI, Fast-Path Testing, and Linting

Read this for fast-path `go test` filtering, race detector configuration, `golangci-lint` setup, `go.mod` hygiene, and build tags for integration test isolation.

---

## 1. Fast-Path Test Filtering Recipes

Avoid running whole-repository test suites during localized edits. Use precise test targeting to keep feedback loops under 500ms.

### Targeting Matrix

| Goal | Command Recipe |
|---|---|
| **Single Unit Test** | `go test -v -run ^TestLoginSuccess$ ./internal/auth` |
| **Single Subtest** | `go test -v -run ^TestLogin/InvalidPassword$ ./internal/auth` |
| **Target Package with Race Detector** | `go test -race ./internal/auth` |
| **Fast Short Mode (Skip slow tests)** | `go test -short ./...` |
| **Re-run only failed package** | `go test ./internal/storage` |
| **Specific Build Tag (e.g. integration)**| `go test -tags=integration -run ^TestPostgresConnection$ ./internal/database` |

---

## 2. Test Structure & Short Mode Discipline

Separate fast unit tests from slow integration/network tests using `testing.Short()` or build tags.

### Using `testing.Short()`

```go
package database_test

import (
    "testing"
)

func TestDatabaseMigration(t *testing.T) {
    if testing.Short() {
        t.Skip("skipping slow database migration test in short mode")
    }

    // Heavy integration test spinning up real database container...
}
```

### Using Build Tags for Integration Suites

Add a build constraint at the very top of heavy integration test files:

```go
//go:build integration

package api_test

import (
    "testing"
)

func TestEndToEndPaymentFlow(t *testing.T) {
    // Runs only when `go test -tags=integration ./...` is executed
}
```

---

## 3. `golangci-lint` Configuration & Linter Rules

`golangci-lint` is the industry-standard aggregated linter for Go.

### Recommended `.golangci.yml` Configuration

```yaml
run:
  timeout: 5m
  tests: true

linters:
  enable:
    - govet          # Reports suspicious constructs (printf errors, unreachable code)
    - errcheck       # Ensures errors are checked
    - staticcheck    # Advanced Go static analysis
    - unused         # Finds unused constants, variables, functions, and types
    - ineffassign    # Detects ineffectual assignments
    - revive         # Fast, configurable drop-in replacement for golint
    - gocritic       # Deep code analysis and style checks
    - prealloc       # Finds slice declarations that could be preallocated
    - bodyclose      # Checks whether HTTP response bodies are closed

issues:
  exclude-use-default: false
  max-issues-per-linter: 0
  max-same-issues: 0
```

### Targeted Lint Execution

```bash
# Run linter only on the modified package (Fast-Path)
golangci-lint run ./internal/auth/...

# Run linter across the entire repository (Full Verification)
golangci-lint run ./...
```

---

## 4. Module Hygiene & Dependency Verification

Never leave dirty or uncommitted changes in `go.mod` and `go.sum`.

### Dependency Maintenance Commands

```bash
# Clean up unused dependencies and add missing ones
go mod tidy

# Verify hashes of downloaded dependencies against go.sum
go mod verify

# Ensure go.mod and go.sum are cleanly formatted and synchronized
git diff --exit-code go.mod go.sum
```

---

## 5. Anti-Patterns vs Pragmatic Tooling

| Anti-Pattern | Failure Mode | Pragmatic Solution |
|---|---|---|
| **Whole-Repo Test Runs on 1-Line Fix** | Wastes 2-5 minutes per edit iteration; breaks developer focus. | Use `go test -run ^TestName$ ./package` for immediate feedback. |
| **Skipping `-race` on Concurrency Code** | Latent data races pass tests silently and corrupt production memory. | Always run `go test -race` on packages with channels or mutexes. |
| **Unchecked HTTP Response Bodies** | Leaks TCP sockets and connection pool slots indefinitely. | Always `defer resp.Body.Close()` immediately after checking `err == nil`. |
| **Slow Integration Tests in Default Suite** | Developers avoid running local tests because test suite takes 10 minutes. | Gate slow tests behind `testing.Short()` or `//go:build integration`. |
| **Ignoring Unused Dependencies** | Bloats binary size and introduces supply chain vulnerability vectors. | Run `go mod tidy` before every commit. |

---

## 6. Concrete Code Comparisons

### HTTP Response Body Closure

#### ❌ ANTI-PATTERN: Leaked Response Body
```go
// BAD: If read fails or function returns early, response body leaks open connection
resp, err := http.Get("https://api.example.com/data")
if err != nil {
    return err
}
data, err := io.ReadAll(resp.Body) // Missing resp.Body.Close()!
```

#### ✅ PRAGMATIC: Immediate Deferred Closure
```go
// GOOD: Connection is guaranteed to return to pool cleanly
resp, err := http.Get("https://api.example.com/data")
if err != nil {
    return fmt.Errorf("fetching data: %w", err)
}
defer resp.Body.Close() // Guaranteed closure

data, err := io.ReadAll(resp.Body)
if err != nil {
    return fmt.Errorf("reading response body: %w", err)
}
```

---

## 7. Fast-Path CI Checklist

```bash
# 1. Fast-Path local unit test
go test -v -run ^TestTarget$ ./internal/domain

# 2. Package race check
go test -race ./internal/domain

# 3. Targeted lint
golangci-lint run ./internal/domain/...

# 4. Final module hygiene check
go mod tidy && git diff --exit-code go.mod go.sum
```
