---
name: go-engineering
description: Implement, review, debug, and optimize Go modules and packages. Use for Go architecture, internal packages, interface design (accept interfaces, return structs), goroutine lifecycles and errgroup, context propagation, error handling (errors.Is/As/%w), JSON/wire serialization, sync.Pool, pprof profiling, and fast-path go test filtering. Do not use for non-Go work.
---

# Go Engineering

Produce the smallest correct Go change or the focused review the user requested. Preserve project policy, write concrete idiomatic Go, make concurrency lifecycles deterministic, and support completion claims with proportionate evidence.

## Start with the repository

1. Cap pre-flight discovery to 3-5 directly relevant files: inspect `go.mod`, `go.sum`, toolchain version (Go 1.20+), existing linter config (`.golangci.yml` or `.golangci.yaml`), CI workflows, and nearby code/tests.
2. Identify whether the request is implementation, diagnosis, review, API design, concurrency refactoring, performance optimization, or tooling. A review or diagnosis does not authorize edits.
3. Existing repository choices win. Do not upgrade Go version, rewrite module paths, replace dependency management, change lint policies, or reformat unrelated files unless explicitly requested.
4. Read only the reference documents routed below that match the current task.

## Cross-cutting rules

- **Flat Package Layout & `internal/` Encapsulation**: Organize packages by domain or feature, not by architectural tier (e.g. `auth`, `payment`, `sqlite`, `httpclient`). Place private application code under `internal/` to prevent external leakage. Ban garbage-can packages (`util`, `common`, `helpers`, `base`, `models`, `types`).
- **Interface Discipline ("Accept Interfaces, Return Structs")**: Define interfaces on the consumer/client side where consumed, never on the producer/service side alongside concrete types. Return concrete structs (`*Service`, `*Store`) from constructors. Keep interfaces tiny (1-2 methods like `io.Reader`, `io.Closer`).
- **Rule of Three for Interfaces**: Write concrete structs and methods first. Do not extract an interface or generic type parameter unless at least 3 distinct concrete implementations exist in the repository or an established standard library contract requires it. Never extract single-implementation interfaces solely to generate mock objects with `mockery` or `gomock`.
- **Ban on Small Builders (< 5 fields)**: For structs with fewer than 5 fields, instantiate directly with struct literals (`Config{Host: "localhost", Port: 8080}`) or standard `New(...)` constructors. Reserve the functional options pattern strictly for complex configuration structs with 5 or more optional fields.
- **Single-Path Execution & In-Place Refactoring**: Refactor types, functions, and interfaces in place and atomically update all call sites, internal usages, and tests in the same change wave. Ban legacy forwarding shims (`// Deprecated: use NewBar`), zombie JSON decoders, dual-writing, and commented-out dead code.
- **Goroutine Lifecycles & Leak Prevention**: Every goroutine must have a deterministic lifecycle and guaranteed termination. Always select on `ctx.Done()` when performing blocking channel or I/O operations. Use `errgroup.Group` for structured concurrent subtasks.
- **Context Propagation**: Pass `ctx context.Context` explicitly as the first parameter of I/O and blocking functions. Never store `context.Context` inside a struct field. Always invoke `defer cancel()` immediately after creating derived contexts (`context.WithTimeout`, `context.WithCancel`).
- **Explicit Error Handling & Wrapping**: Wrap contextual errors with `fmt.Errorf("context: %w", err)` to preserve causal chains. Inspect errors using `errors.Is` and `errors.As`. Combine concurrent errors with `errors.Join`. Ban `panic()` for ordinary operational failures (I/O, database, network, user input); reserve `panic()` strictly for unrecoverable startup invariants or programmer bugs.
- **Receiver Discipline**: Use value receivers (`func (c Config) Method()`) for small immutable structs (< 64 bytes). Use pointer receivers (`func (s *Service) Method()`) for structs containing state, mutators, mutexes (`sync.Mutex`), or large data payloads. Never mix value and pointer receivers on the same type for method sets.

## Verification

Discover and follow the repository's own commands first. Match validation scope to the change and widen it when risk warrants:

1. **Tier 1 (Fast-Path)**: For bug fixes, localized refactors, minor features, internal helpers, documentation, or config edits, run targeted commands on the affected package:
   - Target single test: `go test -v -run ^TestTargetName$ ./internal/auth`
   - Target package with race detector: `go test -race ./internal/auth`
   - Short test execution: `go test -short ./...`
   - Target vet: `go vet ./internal/auth`
2. **Tier 2 (Full Verification)**: For core architectural modifications, concurrency invariants, durable storage schemas, public package APIs, or release gates:
   - Full workspace test suite with race detector: `go test -race ./...`
   - Full coverage profile: `go test -coverprofile=coverage.out ./... && go tool cover -func=coverage.out`
   - Full workspace linter: `golangci-lint run ./...`
   - Module hygiene check: `go mod tidy && git diff --exit-code go.mod go.sum`
3. Check formatting without creating churn: `gofmt -l .` or `goimports -l .`. Inspect the diff before formatting a dirty tree.

Do not hide pre-existing failures by changing unrelated code. Report the exact command, whether it passed, and any baseline issues.

## References

- Package layout, `internal/` boundaries, consumer interface design, Rule of Three, constructor idioms: read [references/architecture-packages.md](references/architecture-packages.md).
- Goroutines, channels vs mutexes, context propagation, worker pools, bounded concurrency, `errgroup`: read [references/concurrency-context.md](references/concurrency-context.md).
- Error wrapping (`%w`), `errors.Is`/`errors.As`/`errors.Join`, sentinels, custom error types, retry backoff, panic policy: read [references/error-handling-resilience.md](references/error-handling-resilience.md).
- JSON parsing (`encoding/json`, `segmentio`), SQL transactions, buffer reuse with `sync.Pool`, wire protocols: read [references/data-serialization.md](references/data-serialization.md).
- Escape analysis (`-gcflags="-m"`), CPU/memory profiling (`pprof`), benchmarks (`benchstat`), `GOMEMLIMIT`, GC tuning: read [references/performance-profiling.md](references/performance-profiling.md).
- Fast-Path `go test` filtering, race detector (`-race`), `golangci-lint` configuration, `go.mod` hygiene, build tags: read [references/tooling-ci.md](references/tooling-ci.md).
