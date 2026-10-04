# Tooling, CI, Fast-Path Testing, and Linting

Read this for fast-path `go test` targeting and caching, the race detector, `golangci-lint` v2 configuration, module hygiene, tool dependencies, vulnerability scanning, and build tags for integration tests.

---

## 1. Fast-Path Test Targeting

Avoid running whole-repository test suites during localized edits. Target the affected package and tests. Quote `-run` patterns so the shell doesn't expand them.

### Targeting Matrix

| Goal | Command |
|---|---|
| **Single test** | `go test -run '^TestLoginSuccess$' ./internal/auth` |
| **Single subtest** | `go test -run '^TestLogin$/^InvalidPassword$' ./internal/auth` (`-run` splits on `/` and matches each level separately) |
| **Package with race detector** | `go test -race ./internal/auth` |
| **Skip slow tests** | `go test -short ./internal/auth` |
| **Force a re-run instead of a cached pass** | `go test -count=1 ./internal/storage` |
| **Stop at the first failure** | `go test -failfast ./internal/storage` |
| **Expose order dependence** | `go test -shuffle=on ./internal/storage` (prints the seed; re-run with `-shuffle=<seed>`) |
| **Integration build tag** | `go test -tags=integration -run '^TestPostgresConnection$' ./internal/database` |
| **Machine-readable results** | `go test -json ./...` |

### Test Caching

`go test` in package-list mode caches successful results and replays them when the test binary, the files and environment variables it read, and the flags are unchanged, and only if every flag is cacheable (`-run`, `-short`, `-v`, `-timeout`, `-failfast`, `-cpu`, `-parallel`, `-skip`, `-list`, `-benchtime`, `-coverprofile`, `-outputdir`, `-fullpath`); the output shows `(cached)`. Other flags, such as `-count` or `-shuffle`, disable caching. Tests depending on other external state (a database, the network) can therefore report a stale pass. Use `-count=1` when re-running against changed external state. `go test` also runs a subset of `go vet` checks before testing; failures there fail the test run.

---

## 2. Test Structure & Short Mode

Separate fast unit tests from slow integration tests with `testing.Short()` or build tags.

### `testing.Short()`

```go
func TestDatabaseMigration(t *testing.T) {
    if testing.Short() {
        t.Skip("skipping database migration test in short mode")
    }
    // ...
}
```

### Build Tags for Integration Suites

Put the constraint on the first line of the file, followed by a blank line:

```go
//go:build integration

package api_test

import "testing"

func TestEndToEndPaymentFlow(t *testing.T) {
    // Runs only with: go test -tags=integration ./...
}
```

### Useful `testing` APIs

- `t.Context()` (Go 1.24+): a context canceled just before the test's cleanup functions run.
- `t.Cleanup(f)`: teardown that runs even when the test fails; prefer it over `defer` in helpers.
- `t.TempDir()`, `t.Setenv(k, v)`, `t.Chdir(dir)` (Go 1.24+): scoped filesystem and environment changes, undone automatically.
- `t.Helper()`: report failures at the caller's line.
- `testing/synctest` (Go 1.25+): deterministic tests of time-dependent concurrent code (see the concurrency reference).
- Fuzzing: `func FuzzX(f *testing.F)` with `go test -run '^$' -fuzz '^FuzzX$' -fuzztime 30s ./pkg` for parsers and decoders of untrusted input.

---

## 3. `golangci-lint` v2 Configuration

`golangci-lint` aggregates many linters. v2 (March 2025) changed the configuration format; a v1 file fails with `unsupported version of the configuration`. Convert one with `golangci-lint migrate`, and validate any config with `golangci-lint config verify`.

### Example `.golangci.yml`

```yaml
version: "2"

linters:
  # "standard" (the default) enables errcheck, govet, ineffassign, staticcheck and unused.
  default: standard
  enable:
    - bodyclose
    - gocritic
    - revive
  exclusions:
    presets:
      - std-error-handling
      - common-false-positives

formatters:
  enable:
    - gofmt
    - goimports

issues:
  max-issues-per-linter: 0
  max-same-issues: 0
```

In v2, formatters live under `formatters:` and run with `golangci-lint fmt`; `run.timeout` is disabled by default; no exclusions apply unless configured under `linters.exclusions`. Extend the linter list for the project's needs rather than enabling everything; `revive`'s defaults, for example, require doc comments on every exported identifier.

### Running

```bash
# Affected packages only (fast path)
golangci-lint run ./internal/auth/...

# Whole module (full verification)
golangci-lint run ./...

# Only issues introduced since a base revision, leaving the existing baseline aside
golangci-lint run --new-from-rev=origin/main ./...
```

### Installation

golangci-lint's docs recommend the release binaries and say that `go install`, the tools pattern and the `go.mod` `tool` directive "aren't guaranteed to work". Pin the version in CI (for example via the official GitHub Action or install script with an explicit version) so local and CI results match.

---

## 4. Module Hygiene & Dependency Verification

Preserve existing changes in `go.mod` and `go.sum`. Run `go mod tidy` only for an authorized dependency change or a required repository check, and inspect its diff.

```bash
# Report what tidy would change, without modifying files; non-zero exit if anything (Go 1.23+)
go mod tidy -diff

# Add missing and remove unused requirements
go mod tidy

# Check that downloaded module sources in the cache haven't been modified
go mod verify

# Explain why a module is required
go mod why -m golang.org/x/sync

# Known vulnerabilities reachable from the code (golang.org/x/vuln/cmd/govulncheck)
govulncheck ./...
```

### Tool Dependencies (Go 1.24+)

Go-based tools a module runs (code generators, `benchstat`, `stringer`) can be recorded in `go.mod`:

```bash
go get -tool golang.org/x/tools/cmd/stringer   # adds a tool directive
go tool stringer -type=State                    # runs the pinned version
```

This replaces the older `tools.go` file of blank imports. Tool dependencies share the module's dependency graph, which is why golangci-lint advises against installing itself this way.

---

## 5. Anti-Patterns vs Pragmatic Tooling

| Anti-Pattern | Failure Mode | Pragmatic Solution |
|---|---|---|
| **Whole-repo test runs for a one-line fix** | Slow feedback on every iteration. | `go test -run '^TestName$' ./pkg` first; widen when the change warrants it. |
| **Skipping `-race` on concurrency changes** | Data races pass ordinary tests and corrupt state in production. | Run `go test -race` on packages whose concurrent code changed. Expect it to be slower (the race detector docs cite 2-20x execution time and 5-10x memory). |
| **Trusting a cached pass** | `(cached)` results hide changes in external state. | `-count=1` when external state changed. |
| **Unclosed HTTP response bodies** | The connection can't be reused; sockets and goroutines pile up. | `defer resp.Body.Close()` right after checking the request error. |
| **Slow integration tests in the default suite** | Developers stop running tests locally. | Gate them behind `testing.Short()` or `//go:build integration`. |
| **Stale `go.mod` requirements** | Unused requirements don't enter the binary, but they enlarge the module graph and `go.sum` and show up in dependency and vulnerability scans. | `go mod tidy` when a dependency change calls for it; `go mod tidy -diff` in CI. |
| **v1 `.golangci.yml` with golangci-lint v2** | The linter refuses to start. | `golangci-lint migrate`, then `golangci-lint config verify`. |

---

## 6. Concrete Code Comparisons

### HTTP Request Lifetime and Body Closure

#### ❌ ANTI-PATTERN: No Timeout, No Context, Leaked Body
```go
// BAD: http.Get uses DefaultClient, which has no timeout, and the body is never closed
resp, err := http.Get("https://api.example.com/data")
if err != nil {
    return err
}
data, err := io.ReadAll(resp.Body)
```

#### ✅ PRAGMATIC: Context, Status Check, Deferred Close
```go
// GOOD: cancellable request, bounded read, connection returned to the pool
req, err := http.NewRequestWithContext(ctx, http.MethodGet, "https://api.example.com/data", nil)
if err != nil {
    return fmt.Errorf("building request: %w", err)
}
resp, err := client.Do(req) // a shared *http.Client with a Timeout configured
if err != nil {
    return fmt.Errorf("fetching data: %w", err)
}
defer resp.Body.Close()

if resp.StatusCode != http.StatusOK {
    return fmt.Errorf("fetching data: unexpected status %s", resp.Status)
}
data, err := io.ReadAll(io.LimitReader(resp.Body, 10<<20))
if err != nil {
    return fmt.Errorf("reading response body: %w", err)
}
```

---

## 7. Fast-Path Checklist

```bash
# 1. Targeted test
go test -run '^TestTarget$' ./internal/domain

# 2. Package race check, if concurrent code changed
go test -race ./internal/domain

# 3. Targeted vet and lint
go vet ./internal/domain
golangci-lint run ./internal/domain/...

# 4. Module hygiene, if dependencies changed
go mod tidy -diff
```
