# Data Serialization, SQL Transactions, and Memory Pooling

Read this for JSON encoding and decoding, trust-boundary validation, JSON library choice (including JSON v2), SQL transaction safety, and buffer reuse with `sync.Pool`.

---

## 1. JSON Serialization & Trust Boundary Parsing

`encoding/json` is the default. Distinguish trusted internal data from untrusted external payloads.

### Struct Tag Idioms

- `json:"field_name"`: explicit wire name.
- `json:"field_name,omitempty"`: omits `false`, `0`, a nil pointer, a nil interface value, and any array, slice, map or string of length zero. It does **not** omit zero-valued structs such as `time.Time{}`.
- `json:"field_name,omitzero"` (Go 1.24+): omits the field when it is the zero value of its type, or when its `IsZero() bool` method returns true. Use it for structs and `time.Time`.
- `json:"-"`: never encoded or decoded.
- `json:",string"`: encodes a string, float, integer or boolean field as a JSON string (useful for 64-bit IDs read by JavaScript clients).

### Decoding Behavior to Know

- `Unmarshal` and `Decoder` match object keys to fields **case-insensitively** in the v1 API, and ignore unknown keys unless `DisallowUnknownFields` is set.
- On Go 1.27, `encoding/json` runs on the v2 implementation with v1 behavior preserved, but error message text may differ: branch on error types, never on messages. `GOEXPERIMENT=nojsonv2` restores the old implementation if a compatibility problem appears.
- `encoding/json/v2` (Go 1.27; `GOEXPERIMENT=jsonv2` on 1.25-1.26) has stricter defaults, such as case-sensitive matching and rejecting duplicate names and invalid UTF-8. Adopt it deliberately, not as a drop-in rename. Its API changed during the experiment (for example the `inline` tag option became `embed`), so code written against the 1.25-1.26 experiment may need updating.

### Trust Boundary Decoding

When decoding untrusted HTTP request bodies:
1. Limit the body size with `http.MaxBytesReader` and map the resulting `*http.MaxBytesError` to 413.
2. Decide whether the API rejects unknown fields. `DisallowUnknownFields` catches typos, but it also rejects clients that send fields from a newer API version.
3. Require exactly one JSON value.

```go
package httpio

import (
    "encoding/json"
    "errors"
    "fmt"
    "io"
    "net/http"
)

// DecodeJSONBody decodes a single JSON value from r into dst. The returned
// status is the HTTP status to send when err is non-nil.
func DecodeJSONBody(w http.ResponseWriter, r *http.Request, dst any, maxBytes int64) (status int, err error) {
    r.Body = http.MaxBytesReader(w, r.Body, maxBytes)

    dec := json.NewDecoder(r.Body)
    dec.DisallowUnknownFields() // only if the API contract rejects unknown fields

    if err := dec.Decode(dst); err != nil {
        var syntaxErr *json.SyntaxError
        var typeErr *json.UnmarshalTypeError
        var tooLarge *http.MaxBytesError
        switch {
        case errors.As(err, &tooLarge):
            return http.StatusRequestEntityTooLarge, fmt.Errorf("body exceeds %d bytes", tooLarge.Limit)
        case errors.As(err, &syntaxErr):
            return http.StatusBadRequest, fmt.Errorf("malformed JSON at offset %d", syntaxErr.Offset)
        case errors.Is(err, io.ErrUnexpectedEOF):
            return http.StatusBadRequest, errors.New("malformed JSON: unexpected end of body")
        case errors.As(err, &typeErr):
            return http.StatusBadRequest, fmt.Errorf("wrong type for field %q", typeErr.Field)
        case errors.Is(err, io.EOF):
            return http.StatusBadRequest, errors.New("body must not be empty")
        default:
            return http.StatusBadRequest, fmt.Errorf("decoding body: %w", err)
        }
    }

    if err := dec.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
        return http.StatusBadRequest, errors.New("body must contain a single JSON value")
    }
    return http.StatusOK, nil
}
```

The messages are built from the error's fields so they stay stable when the JSON implementation's own wording changes.

---

## 2. Serialization Library Selection

| Engine | When to Choose | Trade-offs |
|---|---|---|
| **`encoding/json`** | Default for APIs, config and almost all services. | Reflection-based. On Go 1.27 it uses the v2 implementation, which the release notes describe as unmarshaling significantly faster. |
| **`encoding/json/v2` + `jsontext`** | New code wanting stricter semantics, options, or streaming token-level access. | Go 1.27 (experiment on 1.25-1.26); different defaults from v1. |
| **Third-party JSON (`segmentio/encoding`, `bytedance/sonic`)** | Only after a profile shows JSON dominates CPU, and a benchmark on your own payloads shows a worthwhile gain over the current stdlib. | Extra dependency; differences in error messages and edge-case behavior; `sonic` relies on JIT/assembly with platform and Go-version support limits and falls back to `encoding/json` elsewhere. Published speedups were measured against older stdlib versions. |
| **Protocol Buffers / gRPC** | Service-to-service RPC and compact binary events with a schema. | Requires `.proto` definitions and code generation. |

---

## 3. SQL Database & Transaction Safety

Use parameterized queries, pass a context, and guarantee rollback on every failure path.

### The Canonical Transaction Pattern

Call `defer tx.Rollback()` right after `BeginTx`. After a successful `Commit`, `Rollback` returns `sql.ErrTxDone` and does nothing. `errcheck` reports the unchecked deferred call; write `defer func() { _ = tx.Rollback() }()` or keep the bare form if the repository's lint config excludes it. If the context passed to `BeginTx` is canceled, `database/sql` rolls the transaction back and `Commit` returns an error.

```go
package store

import (
    "context"
    "database/sql"
    "errors"
    "fmt"
)

var (
    ErrInsufficientFunds = errors.New("insufficient funds")
    ErrAccountNotFound   = errors.New("account not found")
)

type Store struct {
    db *sql.DB
}

// TransferFunds moves amount (> 0) between two accounts atomically.
func (s *Store) TransferFunds(ctx context.Context, fromID, toID string, amount int64) error {
    tx, err := s.db.BeginTx(ctx, nil)
    if err != nil {
        return fmt.Errorf("starting transfer: %w", err)
    }
    defer tx.Rollback() // no-op after a successful Commit

    // The balance guard makes the debit fail instead of overdrawing.
    res, err := tx.ExecContext(ctx,
        "UPDATE accounts SET balance = balance - $1 WHERE id = $2 AND balance >= $1", amount, fromID)
    if err != nil {
        return fmt.Errorf("debiting %s: %w", fromID, err)
    }
    if err := expectOneRow(res, ErrInsufficientFunds); err != nil {
        return fmt.Errorf("debiting %s: %w", fromID, err)
    }

    res, err = tx.ExecContext(ctx,
        "UPDATE accounts SET balance = balance + $1 WHERE id = $2", amount, toID)
    if err != nil {
        return fmt.Errorf("crediting %s: %w", toID, err)
    }
    if err := expectOneRow(res, ErrAccountNotFound); err != nil {
        return fmt.Errorf("crediting %s: %w", toID, err)
    }

    if err := tx.Commit(); err != nil {
        return fmt.Errorf("committing transfer: %w", err)
    }
    return nil
}

// expectOneRow returns errNoMatch unless the statement affected exactly one row.
func expectOneRow(res sql.Result, errNoMatch error) error {
    n, err := res.RowsAffected()
    if err != nil {
        return err
    }
    if n != 1 {
        return errNoMatch
    }
    return nil
}
```

Two transfers in opposite directions lock the same rows in opposite orders and can deadlock. Either update rows in a consistent order (for example by account ID) or treat the database's deadlock and serialization-failure errors as retryable. Isolation levels in `sql.TxOptions` are driver-specific; pass `nil` unless the code needs a particular level and the driver supports it.

### Query Parameters and Identifiers

Placeholders (`$1` for PostgreSQL, `?` for MySQL and SQLite) bind values only. Table names, column names and `ORDER BY` directions cannot be parameterized; select them from a fixed allowlist rather than formatting user input into the query.

---

## 4. Buffer Reuse with `sync.Pool`

In hot paths that allocate and discard many short-lived buffers, `sync.Pool` can reduce garbage collector pressure. Use it only after a profile shows the allocations matter. The pool may drop its contents at any garbage collection, so it is a cache, not a free list.

```go
package bufferpool

import (
    "bytes"
    "sync"
)

const maxBufferCap = 64 << 10 // don't keep buffers that grew past 64 KiB

var pool = sync.Pool{
    New: func() any { return new(bytes.Buffer) },
}

// Get returns an empty buffer.
func Get() *bytes.Buffer {
    buf := pool.Get().(*bytes.Buffer)
    buf.Reset()
    return buf
}

// Put returns buf to the pool. The caller must not use buf, or any slice
// obtained from buf.Bytes(), after calling Put.
func Put(buf *bytes.Buffer) {
    if buf.Cap() > maxBufferCap {
        return // let the GC reclaim oversized buffers
    }
    pool.Put(buf)
}
```

Store pointers (`*bytes.Buffer`, `*[]byte`), not slices or structs by value, so `Put` doesn't allocate (staticcheck SA6002).

---

## 5. Anti-Patterns vs Pragmatic Data Handling

| Anti-Pattern | Failure Mode | Pragmatic Solution |
|---|---|---|
| **Formatting values into SQL** | `fmt.Sprintf("... WHERE id = '%s'", id)` allows SQL injection. | Placeholders for values; allowlists for identifiers. |
| **Manual rollback per error branch** | One forgotten branch leaves the transaction and its locks open until the context ends. | `defer tx.Rollback()` immediately after `BeginTx`. |
| **Ignoring `RowsAffected`** | An update that matched nothing (missing row, failed guard) looks like success. | Check the count when the statement must change a specific row. |
| **Pooling unbounded buffers** | One huge request leaves a huge buffer in the pool. | Drop buffers above a capacity limit before `Put`. |
| **Reading unbounded bodies** | `io.ReadAll(r.Body)` lets a client exhaust memory. | `http.MaxBytesReader` with a limit. |
| **`omitempty` on struct or `time.Time` fields** | The zero value is still encoded. | `omitzero` (Go 1.24+) or a pointer field. |
| **Branching on JSON error text** | Messages differ between implementations (and changed in Go 1.27). | Branch on `*json.SyntaxError`, `*json.UnmarshalTypeError` and friends. |
| **Zombie decoders & dual schemas** | Fallback fields (`if d.LegacyID != ""`) complicate domain types forever. | Change structs in place; keep explicit migrations at the boundary. |

---

## 6. Data Verification Recipes

```bash
# Run the transaction tests against the test database
go test -run '^TestTransferFunds$' ./internal/store

# Benchmark serialization throughput and allocations (skip unit tests with -run '^$')
go test -run '^$' -bench '^BenchmarkJSON' -benchmem ./internal/httpio

# Fuzz a decoder that parses untrusted input
go test -run '^$' -fuzz '^FuzzDecode$' -fuzztime 30s ./internal/httpio
```
