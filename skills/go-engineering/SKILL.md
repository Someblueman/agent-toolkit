---
name: go-engineering
description: Implement, review, debug, and optimize Go code. Use when working with .go files, go.mod or go.work, Go package and API design, goroutines, channels and context, error handling, JSON or SQL code, Go tests and benchmarks, pprof profiling, or golangci-lint and Go CI. Do not use for non-Go work.
---

# Go Engineering

Produce the smallest correct Go change or the focused review the user requested. Preserve project policy, write concrete idiomatic Go, make concurrency lifecycles deterministic, and support completion claims with proportionate evidence.

## Start with the repository

1. Read applicable repository instructions, then start discovery with 3-5 directly relevant files and expand when needed to understand contracts, callers, or risks. Relevant starting points: `go.mod` (and `go.work` if present), the linter config (`.golangci.yml`, `.golangci.yaml`, `.golangci.toml` or `.golangci.json`), CI workflows, and nearby code and tests.
2. Read the `go` directive in `go.mod`. It is the minimum toolchain (enforced since Go 1.21) and it selects language semantics such as per-iteration loop variables (1.22). Use language features and standard-library APIs only up to that version; [references/modern-go.md](references/modern-go.md) lists what each release added. Do not raise the `go` line just to use a newer feature unless asked.
3. Identify whether the request is implementation, diagnosis, review, API design, concurrency refactoring, performance optimization, or tooling. A review or diagnosis does not authorize edits.
4. Existing repository choices win. Do not upgrade the Go version, rewrite module paths, replace dependency management, change lint policy, or reformat unrelated files unless explicitly requested.
5. Read only the reference documents routed below that match the current task.

## Cross-cutting rules

- **Packages**: Name packages for what they provide (`auth`, `sqlite`, `httpclient`), short and lowercase, and avoid stutter (`auth.Service`, not `auth.AuthService`). Avoid uninformative names such as `util`, `common`, `helpers`, `misc`, `types` or `models`. Put code that other modules must not import under `internal/`; the `go` command enforces that boundary.
- **Interfaces**: Accept interfaces, return concrete types. Define an interface in the package that consumes it, not next to its implementation, and not before a consumer actually needs it. Small interfaces (one or two methods, like `io.Reader`) are the common case, not a hard cap.
- Prefer concrete code; introduce an abstraction when it simplifies a current requirement or expresses a necessary boundary or invariant.
- Choose direct construction, constructors or functional options according to validation needs and call-site clarity, not field count.
- Replace internal APIs in place and update callers and tests together. Preserve or migrate published APIs, durable data, and cross-process contracts as required. Add compatibility shims, version decoders, or transitional dual writes only when those contracts require them; remove superseded internal implementations and commented-out legacy code.
- **Goroutine lifetimes**: Make it clear when, or whether, every goroutine exits. Give each one an owner that waits for it (`errgroup.Group`, or `sync.WaitGroup`, whose `Go` method needs Go 1.25+). Select on `ctx.Done()` around blocking channel operations, and use context-aware APIs or deadlines for network and file I/O.
- **Context**: Pass `ctx context.Context` as the first parameter of functions that block or do I/O. Do not store a context in a struct field; pass it to each call. Call `defer cancel()` immediately after `context.WithCancel`, `WithTimeout` or `WithDeadline`. Never pass a `nil` context; use `context.TODO()` while plumbing is incomplete.
- **Errors**: Return errors, don't panic, for ordinary failures (I/O, network, database, user input). Wrap with `fmt.Errorf("doing x: %w", err)` when callers may inspect the cause; use `%v` to deliberately hide it at a boundary. Inspect with `errors.Is` and `errors.As` (or `errors.AsType`, Go 1.26+), never by matching `err.Error()` text. Combine independent failures with `errors.Join`. Error strings are lowercase with no trailing punctuation. Handle each error once: either log it or return it. Reserve `panic` for programmer bugs, impossible states, and `Must`-style initialization.
- **Receivers**: Don't mix value and pointer receivers on one type. Use pointer receivers when methods mutate the receiver, when the struct contains a `sync.Mutex` or other value that must not be copied, or when the struct is large. Value receivers suit small immutable structs and basic types. When in doubt, use a pointer receiver.

## Verification

Follow repository-required checks. The commands below are examples to select from, not a checklist to run in full. Choose checks for the changed behavior and risk; documentation-only changes do not automatically require code tests. Broaden or repeat checks only for new changes, failures, unresolved risks, or required acceptance criteria. Quote `-run` and `-bench` patterns so the shell does not expand them.

1. **Tier 1 (fast path)**: For bug fixes, localized refactors, minor features, internal helpers, documentation, or config edits, target the affected package:
   - Single test: `go test -run '^TestTargetName$' ./internal/auth`
   - Package with race detector, for changed concurrent code: `go test -race ./internal/auth`
   - Bypass the test cache when re-running against changed external state: add `-count=1`
   - Vet: `go vet ./internal/auth`
2. **Tier 2 (full verification)**: For core architectural modifications, concurrency invariants, durable storage schemas, public package APIs, or release gates:
   - Module test suite with race detector: `go test -race ./...` (`./...` covers the current module only; in a `go.work` workspace, run each module)
   - Linter: `golangci-lint run ./...`; add `--new-from-rev=<base>` to separate new findings from a pre-existing baseline
   - Module tidiness without modifying files: `go mod tidy -diff` (Go 1.23+)
   - Known vulnerabilities, when dependencies changed or for releases: `govulncheck ./...`
3. Check formatting without creating churn: `gofmt -l .` or `goimports -l .`. Inspect the diff before formatting a dirty tree.

Do not hide pre-existing failures by changing unrelated code. Report the exact command, whether it passed, and any baseline issues.

## References

- Features by Go release (1.21-1.27) and how the `go` directive gates them: read [references/modern-go.md](references/modern-go.md).
- Package layout, `internal/` boundaries, consumer interface design, concrete-first design, constructor idioms, in-place refactoring: read [references/architecture-packages.md](references/architecture-packages.md).
- Goroutine lifetimes and leak detection, channels vs mutexes vs atomics, context propagation, `errgroup`, `testing/synctest`: read [references/concurrency-context.md](references/concurrency-context.md).
- Error wrapping (`%w`), `errors.Is`/`As`/`AsType`/`Join`, sentinels vs typed errors, panic policy, retry with backoff: read [references/error-handling-resilience.md](references/error-handling-resilience.md).
- JSON (`omitempty`/`omitzero`, trust-boundary decoding, JSON v2), SQL transactions, `sync.Pool` buffer reuse: read [references/data-serialization.md](references/data-serialization.md).
- Escape analysis, `pprof` (CPU, heap, mutex, block, goroutine leaks), benchmarks with `b.Loop` and `benchstat`, PGO, `GOMEMLIMIT` and GC tuning: read [references/performance-profiling.md](references/performance-profiling.md).
- `go test` targeting and caching, race detector, `golangci-lint` v2 configuration, module hygiene, build tags, tool dependencies: read [references/tooling-ci.md](references/tooling-ci.md).
