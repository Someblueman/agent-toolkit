# Performance, Escape Analysis, and Profiling Playbook

Read this for allocation reduction, compiler escape analysis, CPU, heap, mutex, block and goroutine profiling with `pprof`, execution traces, benchmarks with `b.Loop` and `benchstat`, profile-guided optimization, and `GOMEMLIMIT`/`GOGC` tuning.

Measure before optimizing: reproduce the slow path, profile it, change one thing, and compare benchmarks statistically. Make no performance claim without a before/after measurement.

---

## 1. Escape Analysis & Allocation Reduction

The compiler places values on the goroutine stack when it can prove they don't outlive the function, and on the heap (which costs allocation and GC work) otherwise. Escape decisions change between releases, so inspect them on the toolchain you ship rather than relying on rules of thumb.

### Escape Analysis Inspection

```bash
# Escape and inlining decisions
go build -gcflags='-m' ./internal/auth

# With the reasons
go build -gcflags='-m -m' ./internal/auth
```

### Common Heap Escape Causes

1. **Pointers that outlive the call**: returning or storing a pointer to a local value (in a global, a long-lived struct, or a channel) moves it to the heap.
2. **Conversion to an interface**: passing a value as `any` (including to `fmt.Println` or `slog` attributes) can allocate when the value escapes. Small values and conversions the compiler can prove don't escape may not allocate; check with `-gcflags=-m`.
3. **Growing slices and maps without a size hint**: repeated growth reallocates and copies.
4. **Closures capturing variables** that outlive the call, such as goroutine bodies.

### Pre-Allocation

```go
// Grows the backing array several times.
var results []string
for _, item := range items {
    results = append(results, transform(item))
}

// One allocation when the final length is known.
results := make([]string, 0, len(items))
for _, item := range items {
    results = append(results, transform(item))
}

// Map capacity hint.
userIndex := make(map[string]*User, len(users))
```

Pre-size when the length is known or cheaply estimated. Don't guess wildly; an oversized hint wastes memory.

---

## 2. Receiver Choice

Go's code review guidance gives no byte threshold. It says not to mix receiver kinds on one type and, when in doubt, to use a pointer.

| Use a Pointer Receiver When | Use a Value Receiver When |
|---|---|
| A method mutates the receiver. | The type is a small immutable struct or a basic type (`time.Time`-like values, IDs, coordinates). |
| The struct contains a `sync.Mutex` or other value that must not be copied. | The type is a map, func or chan (already reference-like). |
| The struct is large enough that copying it on each call is a cost. | Methods must be callable on non-addressable values (map elements, return values). |

A value receiver does not guarantee stack allocation: storing the value in an interface can still move it to the heap.

---

## 3. Profiling Playbook with `pprof`

### Serving Profiles from a Running Program

Importing `net/http/pprof` registers its handlers on `http.DefaultServeMux`. Never serve `DefaultServeMux` on a public listener. Serve profiles from a dedicated mux bound to localhost or an admin network:

```go
import (
    "log"
    "net/http"
    "net/http/pprof"
)

func startDebugServer() {
    mux := http.NewServeMux()
    mux.HandleFunc("/debug/pprof/", pprof.Index) // also serves heap, goroutine, mutex, block, allocs
    mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
    mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
    mux.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
    mux.HandleFunc("/debug/pprof/trace", pprof.Trace)
    go func() {
        log.Println(http.ListenAndServe("127.0.0.1:6060", mux))
    }()
}
```

Mutex and block profiles are empty until enabled, because sampling them has a cost:

```go
runtime.SetMutexProfileFraction(100) // sample ~1 in 100 contention events
runtime.SetBlockProfileRate(10_000)  // sample ~1 event per 10µs spent blocked
```

### Collection Commands

Quote the URLs: `?` is a glob character in zsh.

```bash
# 30-second CPU profile
curl -o cpu.pprof 'http://127.0.0.1:6060/debug/pprof/profile?seconds=30'

# Heap profile (in-use and cumulative allocation samples)
curl -o heap.pprof 'http://127.0.0.1:6060/debug/pprof/heap'

# Full goroutine stacks as text, with how long each has been blocked
curl -o goroutines.txt 'http://127.0.0.1:6060/debug/pprof/goroutine?debug=2'

# Goroutines leaked on unreachable channels or locks (Go 1.27; 1.26 with GOEXPERIMENT=goroutineleakprofile)
curl -o leaks.pprof 'http://127.0.0.1:6060/debug/pprof/goroutineleak'

# Mutex contention (requires SetMutexProfileFraction)
curl -o mutex.pprof 'http://127.0.0.1:6060/debug/pprof/mutex'

# 5-second execution trace (scheduler latency, GC pauses, blocking)
curl -o trace.out 'http://127.0.0.1:6060/debug/pprof/trace?seconds=5'
```

Adding `?seconds=N` to `heap`, `allocs`, `mutex` or `block` returns a delta profile covering only that window.

### Inspecting Profiles

```bash
# Interactive web UI: flame graph, top, source and disassembly views
go tool pprof -http=:8080 cpu.pprof

# Heap: inuse_space (default) shows what is retained; alloc_space shows allocation volume (GC pressure)
go tool pprof -sample_index=alloc_space -http=:8080 heap.pprof

# Execution trace viewer
go tool trace trace.out
```

For incidents that are hard to reproduce, `runtime/trace.FlightRecorder` (Go 1.25+) keeps the last few seconds of trace in memory so the program can write a snapshot when it detects a problem.

---

## 4. Benchmarking & `benchstat`

Never make performance claims from single runs.

### Writing Benchmarks with `b.Loop` (Go 1.24+)

```go
package token

import "testing"

func BenchmarkParseToken(b *testing.B) {
    input := "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." // setup runs once
    b.ReportAllocs()

    for b.Loop() {
        if _, err := ParseToken(input); err != nil {
            b.Fatalf("ParseToken: %v", err)
        }
    }
}
```

`b.Loop` times only the loop, so setup before it needs no `b.ResetTimer()`, and it keeps the loop body's results alive so the compiler can't optimize the work away. Before Go 1.26 it also prevented inlining inside the loop, which could make a benchmark allocate where real callers don't. For modules below `go 1.24`, use `for i := 0; i < b.N; i++` with `b.ResetTimer()` after setup, and assign results to a package-level sink.

To guard an allocation budget in a regular test, use `testing.AllocsPerRun`:

```go
if n := testing.AllocsPerRun(100, func() { _, _ = ParseToken(input) }); n > 1 {
    t.Errorf("ParseToken allocates %v times per call, want <= 1", n)
}
```

### Statistical Comparison

```bash
# -run '^$' skips unit tests; -count=10 gives benchstat enough samples
git stash   # or check out the baseline commit
go test -run '^$' -bench '^BenchmarkParseToken$' -count=10 -benchmem ./internal/token > old.txt
git stash pop
go test -run '^$' -bench '^BenchmarkParseToken$' -count=10 -benchmem ./internal/token > new.txt

benchstat old.txt new.txt
```

`benchstat` reports a delta only when the difference is statistically significant (Mann-Whitney U test, α = 0.05) and prints `~` otherwise. At that threshold about 1 in 20 comparisons of identical code still looks significant, so don't re-run until a result appears. Use an otherwise idle machine, at least 10 runs per side, and interleave old and new runs when noise is high. Install with `go install golang.org/x/perf/cmd/benchstat@latest`, or record it as a module tool with `go get -tool golang.org/x/perf/cmd/benchstat` (Go 1.24+) and run `go tool benchstat`.

---

## 5. Profile-Guided Optimization (PGO)

Since Go 1.21, `go build` uses a CPU profile named `default.pgo` in the main package's directory automatically (`-pgo=auto`). Collect a representative production CPU profile, commit it as `cmd/<name>/default.pgo`, and refresh it periodically. PGO mainly improves inlining and devirtualization of hot calls; measure the gain with benchmarks or production metrics.

---

## 6. Garbage Collector & Runtime Tuning

Read <https://go.dev/doc/gc-guide> before changing these settings.

- **`GOGC`** (default `100`): heap growth target relative to live heap after a collection. Higher values trade memory for less GC CPU.
- **`GOMEMLIMIT`** (Go 1.19+): a soft limit on memory the Go runtime manages; as it nears the limit the GC runs more often. It does not count memory the runtime doesn't manage (C allocations through cgo, memory-mapped files). Leave headroom below a container's hard limit for that: the GC guide suggests an extra 5-10%. Near the limit the program can slow down severely instead of being OOM-killed, so alert on GC CPU as well.
- **`GOGC=off` with `GOMEMLIMIT`**: GC runs only near the limit, maximizing throughput for a program that owns its memory budget. Don't use it when the program shares limited memory with other processes, and only when the live heap stays well below the limit; a transient heap spike near the limit makes the GC run almost continuously.
- **`GOMAXPROCS`**: since Go 1.25 the runtime respects Linux cgroup CPU limits and updates `GOMAXPROCS` when they change. Remove `automaxprocs`-style libraries in modules at `go 1.25`+.
- **Green Tea GC** (default since Go 1.26): the release notes expect a 10-40% reduction in GC overhead. Re-measure GC-related tuning after upgrading.

---

## 7. Anti-Patterns vs Pragmatic Optimizations

| Anti-Pattern | Performance Cost | Pragmatic Solution |
|---|---|---|
| **String concatenation in loops** | `s += x` copies the whole string each time: quadratic work. | `strings.Join` for simple joins; `strings.Builder` (with `Grow` when the size is known) for incremental building. |
| **Appending without a size hint** | Repeated reallocation and copying. | `make([]T, 0, n)` when `n` is known. |
| **Copying large structs by value** | Every call copies the whole struct. | Pass `*LargeStruct`, after confirming in a profile that the copies matter. |
| **Goroutines for trivial work** | Scheduling overhead exceeds the work. | Run small tasks sequentially; parallelize CPU-heavy or blocking work. |
| **Uncalibrated benchmark claims** | Noise mistaken for improvement. | `benchstat` with `-count=10` or more. |
| **Optimizing without a profile** | Effort spent where time isn't. | Profile first; optimize the top entries. |

---

## 8. Concrete Code Comparisons

### String Building

#### ❌ ANTI-PATTERN: Loop Concatenation
```go
// BAD: allocates and copies a new string every iteration
func BuildQuery(columns []string) string {
    q := "SELECT "
    for i, col := range columns {
        if i > 0 {
            q += ", "
        }
        q += col
    }
    q += " FROM users"
    return q
}
```

#### ✅ PRAGMATIC: `strings.Join`, or `strings.Builder` for Incremental Output
```go
// GOOD: Join sizes the result once
func BuildQuery(columns []string) string {
    return "SELECT " + strings.Join(columns, ", ") + " FROM users"
}

// GOOD: Builder when output is produced piece by piece
func WriteRows(rows [][]string) string {
    var sb strings.Builder
    for _, row := range rows {
        sb.WriteString(strings.Join(row, "\t"))
        sb.WriteByte('\n')
    }
    return sb.String()
}
```

---

## 9. Performance Recipes

```bash
# One benchmark with allocation counts, skipping unit tests
go test -run '^$' -bench '^BenchmarkBuildQuery$' -benchmem ./internal/query

# CPU profile of a benchmark. Profiling flags keep the compiled query.test binary in the current directory.
go test -run '^$' -bench '^BenchmarkBuildQuery$' -cpuprofile cpu.pprof ./internal/query
go tool pprof -http=:8080 cpu.pprof

# Memory and mutex profiles from tests (go test enables the mutex sampling itself)
go test -run '^$' -bench . -memprofile mem.pprof -mutexprofile mutex.pprof ./internal/query

# Execution trace from a test
go test -run '^TestPipeline$' -trace trace.out ./internal/pipeline && go tool trace trace.out
```
