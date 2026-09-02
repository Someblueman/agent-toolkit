# Performance, Escape Analysis, and Profiling Playbook

Read this for memory allocation reduction, compiler escape analysis, CPU and heap profiling with `pprof`, benchmark analysis with `benchstat`, compiler inlining, and `GOMEMLIMIT` garbage collector tuning.

---

## 1. Memory Layout, Escape Analysis & Allocation Elimination

Go's compiler automatically allocates variables on the goroutine stack (very fast, zero GC cost) or escapes them to the heap (requires dynamic allocation and Garbage Collector sweeping).

### Escape Analysis Inspection

Run the compiler with escape analysis diagnostics:
```bash
# Level 1 diagnostics
go build -gcflags="-m" ./internal/auth

# Detailed escape analysis reasons
go build -gcflags="-m -m" ./internal/auth
```

### Common Heap Escape Causes & Remedies

1. **Returning Pointer to Local Variable When Stored Externally**: If the compiler cannot prove the object's lifetime is bounded by the stack frame, it escapes to heap.
2. **Interface Boxing (`any` / `interface{}`)**: Passing concrete values to functions accepting `any` or formatted print functions (`fmt.Println(val)`) causes boxing allocations.
3. **Unbounded Slice Appending**: Calling `append()` without pre-allocation triggers geometric array reallocation and copying on the heap.
4. **Sending Pointers Over Channels**: Data sent as pointers over channels frequently escapes because lifetimes become non-deterministic to compiler analysis.

### Pre-Allocation Rules

```go
// BAD: Triggers multiple re-allocations and heap churn
var results []string
for _, item := range items {
    results = append(results, transform(item))
}

// GOOD: Pre-allocated slice capacity; single allocation
results := make([]string, 0, len(items))
for _, item := range items {
    results = append(results, transform(item))
}

// GOOD: Pre-allocated map capacity hint
userIndex := make(map[string]*User, len(users))
```

---

## 2. Receiver Discipline: Value vs Pointer

| Receiver Type | Memory Footprint | Mutability | Escape Behavior | Recommendation |
|---|---|---|---|---|
| **Value Receiver** (`func (v Point) X()`) | Structs < 64 bytes (1-4 machine words) | Immutable copy | Stays on stack; no heap escape | Use for small data types, coordinates, UUIDs, time wrappers. |
| **Pointer Receiver** (`func (s *Service) Exec()`) | Structs >= 64 bytes or containing mutexes/state | Mutates receiver state | May escape if pointer outlives stack frame | Use for services, state machines, structs with `sync.Mutex`. |

*Rule*: **Never mix value and pointer receivers** on the same struct type for interface satisfaction.

---

## 3. Profiling Playbook with `pprof`

### Live Production Profiling via HTTP

Add `net/http/pprof` to an administrative HTTP port (never expose unprotected to the public internet):

```go
import _ "net/http/pprof"

// In main.go:
go func() {
    log.Println(http.ListenAndServe("127.0.0.1:6060", nil))
}()
```

### Profile Collection Commands

```bash
# 1. Collect 30-second CPU profile
curl -o cpu.pprof http://127.0.0.1:6060/debug/pprof/profile?seconds=30

# 2. Collect current Heap memory profile
curl -o mem.pprof http://127.0.0.1:6060/debug/pprof/heap

# 3. Collect Goroutine dump (useful for detecting goroutine leaks)
curl -o goroutine.pprof http://127.0.0.1:6060/debug/pprof/goroutine

# 4. Collect Mutex contention profile
curl -o mutex.pprof http://127.0.0.1:6060/debug/pprof/mutex
```

### Profile Inspection via Web UI

```bash
# Launch interactive browser UI with flame graphs and source annotation
go tool pprof -http=:8080 cpu.pprof
```

---

## 4. Rigorous Benchmarking & `benchstat`

Never make performance claims based on single runs. Use `benchstat` for statistical rigor.

### Writing High-Signal Benchmarks

```go
package parser

import (
    "strings"
    "testing"
)

func BenchmarkParseToken(b *testing.B) {
    input := "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    b.ReportAllocs() // Tracks allocations per operation
    b.ResetTimer()   // Resets timer after expensive setup

    for i := 0; i < b.N; i++ {
        _, err := ParseToken(input)
        if err != nil {
            b.Fatalf("unexpected error: %v", err)
        }
    }
}
```

### Running Statistical Benchmark Comparison

```bash
# 1. Run 10 iterations of baseline code
git checkout main
go test -bench=BenchmarkParseToken -count=10 -benchmem ./... > baseline.txt

# 2. Run 10 iterations of optimized branch
git checkout feature/fast-parse
go test -bench=BenchmarkParseToken -count=10 -benchmem ./... > optimized.txt

# 3. Compute statistical significance (p-value < 0.05 indicates valid gain)
benchstat baseline.txt optimized.txt
```

---

## 5. Garbage Collector Tuning & `GOMEMLIMIT`

In containerized environments (Docker, Kubernetes), applications can be OOM-killed if the Go heap expands beyond the container memory limit.

### Key Environment Variables

1. **`GOMEMLIMIT` (Go 1.19+)**: Soft memory limit that makes the Garbage Collector trigger more aggressively as memory approaches the ceiling, preventing container OOM kills.
   - *Best Practice*: Set `GOMEMLIMIT` to **85-90%** of the container's hard memory limit (e.g. `GOMEMLIMIT=450MiB` for a 512MiB container limit).
2. **`GOGC`** (Default `100`): Controls the target heap growth percentage relative to reachable data.
   - Setting `GOGC=off` with a defined `GOMEMLIMIT` maximizes throughput in memory-constrained environments by running GC only when approaching the memory cap.

---

## 6. Anti-Patterns vs Pragmatic Optimizations

| Anti-Pattern | Performance Cost | Pragmatic Solution |
|---|---|---|
| **String Concatenation in Loops** | `str += item` creates $O(N^2)$ byte allocations on the heap. | Use `strings.Builder` with `b.Grow(totalLen)`. |
| **Slice Resizing Without Pre-alloc** | Repeated reallocation causes continuous GC overhead and memory copying. | Pre-allocate slice with `make([]T, 0, count)`. |
| **Passing Large Structs by Value** | Copies 500+ bytes onto the stack on every function call. | Pass pointer `*LargeStruct` for large structures. |
| **Premature Concurrency / Micro-Goroutines** | Spawning goroutines for trivial 10-nanosecond operations adds runtime scheduling overhead. | Run small tasks sequentially; parallelize only compute-heavy or I/O workloads. |
| **Uncalibrated Benchmark Claims** | Comparing single noisy benchmark runs without statistical verification. | Use `benchstat` with `-count=10`. |

---

## 7. Concrete Code Comparisons

### String Aggregation: `+` vs `strings.Builder`

#### ❌ ANTI-PATTERN: Loop Concatenation
```go
// BAD: Allocates a new string and copies data on every iteration
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

#### ✅ PRAGMATIC: `strings.Builder` with Capacity Preallocation
```go
// GOOD: Zero heap re-allocations during build
func BuildQuery(columns []string) string {
    var sb strings.Builder
    sb.Grow(len(columns)*16 + 20) // Estimate capacity
    sb.WriteString("SELECT ")
    for i, col := range columns {
        if i > 0 {
            sb.WriteString(", ")
        }
        sb.WriteString(col)
    }
    sb.WriteString(" FROM users")
    return sb.String()
}
```

---

## 8. Fast-Path Performance Recipes

```bash
# Run benchmark on specific function with allocation tracking
go test -bench=^BenchmarkBuildQuery$ -benchmem ./internal/query

# Generate CPU profile and open browser visualization immediately
go test -bench=^BenchmarkBuildQuery$ -cpuprofile=cpu.pprof ./internal/query && go tool pprof -http=:8080 cpu.pprof
```
