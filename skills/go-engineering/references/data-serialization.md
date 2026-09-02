# Data Serialization, SQL Transactions, and Memory Pooling

Read this for JSON encoding/decoding, wire protocol handling, SQL transaction safety, trust boundary validation, and zero-allocation buffer reuse with `sync.Pool`.

---

## 1. JSON Serialization & Trust Boundary Parsing

Go provides powerful reflective JSON serialization via `encoding/json`. In production services, distinguish between internal data transfers and untrusted external payloads.

### JSON Tag Idioms

- `json:"field_name"`: Explicit snake_case or camelCase wire name.
- `json:"field_name,omitempty"`: Omits zero-values (`0`, `""`, `nil`, `false`) from output JSON.
- `json:"-"`: Completely ignores field in serialization.
- `json:",string"`: Encodes numbers as strings (useful for 64-bit integers in JavaScript clients).

### Trust Boundary Decoding

When decoding untrusted HTTP request bodies:
1. Limit payload size with `http.MaxBytesReader(w, r.Body, maxBytes)` to prevent memory exhaustion DoS attacks.
2. Use `json.NewDecoder(r.Body)` with `dec.DisallowUnknownFields()` to catch unknown or mistyped fields.
3. Handle single-object streams strictly.

```go
package httpio

import (
    "encoding/json"
    "errors"
    "fmt"
    "io"
    "net/http"
)

func DecodeJSONBody(w http.ResponseWriter, r *http.Request, dst any, maxBytes int64) error {
    r.Body = http.MaxBytesReader(w, r.Body, maxBytes)

    dec := json.NewDecoder(r.Body)
    dec.DisallowUnknownFields() // Reject unexpected fields at trust boundary

    if err := dec.Decode(dst); err != nil {
        var syntaxErr *json.SyntaxError
        var unmarshalTypeErr *json.UnmarshalTypeError
        switch {
        case errors.As(err, &syntaxErr):
            return fmt.Errorf("body contains malformed JSON at position %d: %w", syntaxErr.Offset, err)
        case errors.As(err, &unmarshalTypeErr):
            return fmt.Errorf("body contains incorrect type for field %q: %w", unmarshalTypeErr.Field, err)
        case errors.Is(err, io.EOF):
            return errors.New("body must not be empty")
        default:
            return err
        }
    }

    // Ensure there is only a single JSON object in the stream
    if err := dec.Decode(&struct{}{}); err != io.EOF {
        return errors.New("body must only contain a single JSON value")
    }

    return nil
}
```

---

## 2. Serialization Library Selection Matrix

| Engine | Throughput / Allocations | When to Choose | Trade-offs |
|---|---|---|---|
| **`encoding/json` (Stdlib)** | Moderate speed; reflection allocations | Default choice for all standard APIs, config files, and low-to-medium traffic. | Slower on large JSON payloads (> 100 KB). |
| **`segmentio/encoding/json`** | 2-4x faster than stdlib | Drop-in standard replacement for high-throughput REST APIs. | Additional dependency. |
| **`bytedance/sonic`** | 5-10x faster (JIT/AVX) | Extreme throughput microservices on x86-64 / ARM64 Linux/macOS. | Unsafe memory manipulation; arch-specific JIT. |
| **Protobuf / gRPC** | Ultra-high throughput; binary compact | Internal service-to-service RPCs, real-time event streams. | Requires `.proto` schema definitions and code generation. |

---

## 3. SQL Database & Transaction Safety

Database interactions must maintain strict safety invariants: parameterized queries, explicit context timeouts, and guaranteed transaction rollback on failure.

### The Canonical SQL Transaction Pattern

The idiomatic Go transaction pattern uses `defer tx.Rollback()`. If `tx.Commit()` succeeds, `tx.Rollback()` returns `sql.ErrTxDone` and performs a safe no-op.

```go
package store

import (
    "context"
    "database/sql"
    "fmt"
)

type Store struct {
    db *sql.DB
}

func (s *Store) TransferFunds(ctx context.Context, fromID, toID string, amount int64) error {
    tx, err := s.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
    if err != nil {
        return fmt.Errorf("starting tx: %w", err)
    }
    // Safe deferred rollback: harmless if tx.Commit() is executed below
    defer tx.Rollback()

    // Step 1: Debit sender
    _, err = tx.ExecContext(ctx, "UPDATE accounts SET balance = balance - $1 WHERE id = $2", amount, fromID)
    if err != nil {
        return fmt.Errorf("debiting %s: %w", fromID, err)
    }

    // Step 2: Credit receiver
    _, err = tx.ExecContext(ctx, "UPDATE accounts SET balance = balance + $1 WHERE id = $2", amount, toID)
    if err != nil {
        return fmt.Errorf("crediting %s: %w", toID, err)
    }

    // Step 3: Commit transaction
    if err := tx.Commit(); err != nil {
        return fmt.Errorf("committing tx: %w", err)
    }

    return nil
}
```

---

## 4. Zero-Allocation Buffer Pooling with `sync.Pool`

In high-throughput systems, constantly allocating and discarding byte slices or `bytes.Buffer` instances causes severe Garbage Collector pressure. Use `sync.Pool` to recycle memory buffers safely.

### Safe Buffer Pool Implementation

```go
package bufferpool

import (
    "bytes"
    "sync"
)

const maxBufferSize = 64 * 1024 // 64 KB cap to prevent permanent memory retention

var pool = sync.Pool{
    New: func() any {
        // Pre-allocate initial buffer capacity
        return bytes.NewBuffer(make([]byte, 0, 4096))
    },
}

// Get retrieves a clean, reset buffer from the pool.
func Get() *bytes.Buffer {
    buf := pool.Get().(*bytes.Buffer)
    buf.Reset()
    return buf
}

// Put returns the buffer to the pool unless it has grown excessively large.
func Put(buf *bytes.Buffer) {
    if buf.Cap() > maxBufferSize {
        // Drop oversized buffer to let GC reclaim memory
        return
    }
    pool.Put(buf)
}
```

---

## 5. Anti-Patterns vs Pragmatic Data Serialization

| Anti-Pattern | Failure Mode | Pragmatic Solution |
|---|---|---|
| **SQL String Concatenation** | `fmt.Sprintf("SELECT * FROM u WHERE id = '%s'", id)` allows SQL injection. | Always use parameterized queries: `$1` (Postgres) or `?` (MySQL/SQLite). |
| **Missing `defer tx.Rollback()`** | Early return on error leaves database locks open and connection leaks. | Always invoke `defer tx.Rollback()` immediately after `db.BeginTx`. |
| **Storing Large Buffers in `sync.Pool`** | An anomalous 100 MB buffer stays in pool indefinitely, causing out-of-memory. | Cap maximum buffer capacity before returning to pool (`buf.Cap() > limit`). |
| **Unbounded JSON Body Reading** | `io.ReadAll(r.Body)` allows attackers to send 10 GB stream, exhausting RAM. | Wrap with `http.MaxBytesReader(w, r.Body, maxLimit)`. |
| **Zombie Decoders & Dual Schemas** | Keeping fallback fields (`if d.LegacyID != ""`) complicates domain structs. | Refactor domain structs in-place; keep migrations explicit at boundary. |

---

## 6. Concrete Code Comparisons

### Database Transaction Management

#### ❌ ANTI-PATTERN: Manual Rollback in Every Error Branch
```go
// BAD: Prone to missed rollbacks on panics or unexpected returns
tx, err := db.Begin()
if err != nil { return err }

if err := step1(tx); err != nil {
    tx.Rollback()
    return err
}

if err := step2(tx); err != nil {
    // BUG: Developer forgot to call tx.Rollback() here!
    return err
}

return tx.Commit()
```

#### ✅ PRAGMATIC: Guaranteed Deferred Rollback
```go
// GOOD: Safe, clean, and panic-resilient
tx, err := db.BeginTx(ctx, nil)
if err != nil {
    return fmt.Errorf("begin tx: %w", err)
}
defer tx.Rollback() // Safe no-op once Commit() succeeds

if err := step1(ctx, tx); err != nil {
    return fmt.Errorf("step 1: %w", err)
}
if err := step2(ctx, tx); err != nil {
    return fmt.Errorf("step 2: %w", err)
}

return tx.Commit()
```

---

## 7. Fast-Path Data Verification Recipes

```bash
# Run database transaction unit tests against test DB
go test -v -run ^TestTransferFunds$ ./internal/store

# Benchmark JSON serialization throughput and allocations
go test -bench=BenchmarkJSON -benchmem ./internal/httpio
```
