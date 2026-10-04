# Modern Go: Features by Release

Read this before using a language feature or standard-library API that may be newer than the module allows, and when reviewing code for idioms that newer releases made obsolete.

---

## 1. What the `go` Directive Controls

- Since Go 1.21 the `go` line in `go.mod` is a **minimum requirement**: older toolchains refuse to build the module, and with the default `GOTOOLCHAIN=auto` a newer toolchain is downloaded when needed. The optional `toolchain` line names a preferred toolchain.
- The `go` line also selects **language semantics** per module (for example, per-iteration loop variables apply only to modules declaring `go 1.22` or later). A `//go:build go1.N` constraint can raise the version for a single file.
- `go vet`'s `stdversion` check reports uses of standard-library symbols newer than the file's effective Go version. Since Go 1.27, `go test` runs it by default.
- Use features only up to the module's `go` version. Do not raise the `go` line to reach a feature unless the user asks; it raises the minimum for every consumer of the module.
- Since Go 1.26, `go mod init` with toolchain 1.N writes `go 1.(N-1).0`, so new modules stay buildable by both supported releases.

Each Go release is supported until two newer major releases exist. Check the current release at <https://go.dev/doc/devel/release> rather than assuming.

---

## 2. Features by Release

Prefer these over older idioms when the module's `go` version allows them.

### Go 1.21

- Built-ins `min`, `max`, `clear`. Packages `slices`, `maps`, `cmp`, `log/slog`.
- `context.AfterFunc`, `context.WithoutCancel`, `context.WithDeadlineCause`, `context.WithTimeoutCause`.
- `sync.OnceFunc`, `sync.OnceValue`, `sync.OnceValues`.
- Profile-guided optimization (PGO) generally available: a `default.pgo` in the main package directory is used automatically.

### Go 1.22

- **Per-iteration loop variables.** `for i, v := range xs` creates new `i`, `v` each iteration, so `v := v` copies before capturing in a closure or goroutine are unnecessary. Remove them in modules at `go 1.22`+.
- Range over integers: `for i := range n`.
- `math/rand/v2` (use instead of `math/rand` in new code).
- `net/http.ServeMux` patterns with methods and wildcards: `mux.HandleFunc("GET /items/{id}", h)` with `r.PathValue("id")`.

### Go 1.23

- Range-over-func iterators and the `iter` package; `slices.All`, `slices.Collect`, `maps.Keys`, `maps.Values` and friends return or consume iterators.
- Timers: unreferenced `time.Timer`/`time.Ticker` values are collected even if not stopped, and timer channels are unbuffered so `Reset`/`Stop` never leave a stale value. On toolchains 1.23-1.26 this applies to modules at `go 1.23`+; since Go 1.27 timer channels are always unbuffered. `time.After` in a loop no longer leaks until it fires.
- `unique` package for value interning.
- `go mod tidy -diff` reports needed changes without modifying files and exits non-zero if any are needed.

### Go 1.24

- Generic type aliases.
- `testing.B.Loop` for benchmarks (see the performance reference); `T.Context`, `T.Chdir`.
- `encoding/json` `omitzero` tag option (uses `IsZero()` when defined).
- `os.Root` for filesystem access confined to a directory.
- `go.mod` `tool` directive: `go get -tool <pkg>` records a tool dependency and `go tool <name>` runs it.
- `runtime.AddCleanup` (prefer over `runtime.SetFinalizer`), `weak` package.
- `strings.Lines`, `strings.SplitSeq`, `bytes` equivalents returning iterators.

### Go 1.25

- `sync.WaitGroup.Go(func())` adds, runs and marks done in one call. The vet `waitgroup` analyzer flags a misplaced `wg.Add` inside the goroutine (renamed `waitgroupgo` in 1.27).
- `testing/synctest` generally available: `synctest.Test` runs code in a bubble with a fake clock; `synctest.Wait` waits for the bubble's goroutines to block.
- Container-aware `GOMAXPROCS`: on Linux the runtime respects cgroup CPU limits and updates `GOMAXPROCS` if limits change. Libraries such as `automaxprocs` are no longer needed.
- `runtime/trace.FlightRecorder` keeps a rolling in-memory execution trace to snapshot after an incident.
- `encoding/json/v2` and `encoding/json/jsontext` available behind `GOEXPERIMENT=jsonv2`.
- `T.Attr`, `T.Output`; `go.mod` `ignore` directive.

### Go 1.26

- `new(expr)`: `new` accepts an expression, e.g. `Age: new(yearsSince(born))` for optional pointer fields.
- `errors.AsType[E error](err error) (E, bool)`: a type-safe, faster generic `errors.As`.
- `go fix` revamped as the home of modernizers: run it to update code to current idioms and APIs. `//go:fix inline` on a function lets `go fix` inline calls to it, which automates migrations off deprecated wrappers.
- Green Tea garbage collector enabled by default (the release notes expect a 10-40% reduction in GC overhead; opt out with `GOEXPERIMENT=nogreenteagc`, which 1.27 still accepts but which the 1.26 notes said would be removed).
- `goroutineleak` profile available as an experiment (`GOEXPERIMENT=goroutineleakprofile`).
- `T.ArtifactDir`, `B.ArtifactDir`, `F.ArtifactDir` for test output files. `B.Loop` no longer prevents inlining in the loop body.
- `signal.NotifyContext` cancels its context with a cause naming the signal received.

### Go 1.27

- Generic methods: a method declaration may declare its own type parameters.
- Struct literal keys may be any valid field selector for the struct type, not only top-level field names.
- `encoding/json` is backed by the v2 implementation: behavior is preserved but error message text may differ (opt out with `GOEXPERIMENT=nojsonv2`). `encoding/json/v2` is available as a package.
- `goroutineleak` profile generally available, including the `net/http/pprof` endpoint `/debug/pprof/goroutineleak`.
- `testing/synctest.Sleep` (sleep then `Wait`); `httptest.NewTestServer` serves over an in-memory fake network usable inside a `synctest` bubble.
- `go test` runs the `stdversion` vet check by default. The vet `printf` check flags `fmt.Errorf("...: %w", p)` where `p` has type `*E` and `E` itself implements `error`, a latent bug that breaks type checks such as `errors.Is`.
- `go mod tidy` merges duplicate `require` blocks for modules at `go 1.27`+.

---

## 3. Outdated Idioms to Recognize in Review

| Older idiom | Replacement | Requires |
|---|---|---|
| `v := v` before a closure or goroutine in a loop | Nothing; loop variables are per-iteration | `go 1.22` |
| `math/rand` with manual seeding | `math/rand/v2` | 1.22 |
| `for i := 0; i < b.N; i++` plus `b.ResetTimer()` | `for b.Loop()` | 1.24 |
| `ctx, cancel := context.WithCancel(context.Background())` in tests | `t.Context()` | 1.24 |
| `wg.Add(1); go func() { defer wg.Done(); ... }()` | `wg.Go(func() { ... })` | 1.25 |
| `var target *T; if errors.As(err, &target)` | `if target, ok := errors.AsType[*T](err); ok` | 1.26 |
| `go.uber.org/automaxprocs` | Built-in container-aware `GOMAXPROCS` | 1.25 |
| `tools.go` with blank imports to pin tools | `tool` directive in `go.mod` | 1.24 |
| Manual `sort.Slice` with a less func | `slices.Sort`, `slices.SortFunc(xs, cmp)` | 1.21 |

Running `go fix ./...` (Go 1.26+) applies many such modernizations mechanically; review its diff like any other change.
