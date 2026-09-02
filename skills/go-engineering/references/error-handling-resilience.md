# Error Handling, Inspection, and Resilience

Read this for explicit error wrapping (`%w`), inspection via `errors.Is` and `errors.As`, multiple error joining (`errors.Join`), sentinel vs typed errors, retry backoff loops, and panic avoidance policies.

---

## 1. Error Wrapping & Semantic Propagation

Go treats errors as explicit values. When propagating errors up the call stack, add operational context while preserving the underlying causal error chain.

### Wrapping Rules: `%w` vs `%v`

- **Use `%w`** when callers need to programmatically inspect the root cause (using `errors.Is` or `errors.As`):
  ```go
  if err := db.ExecContext(ctx, query); err != nil {
      return fmt.Errorf("updating account balance %s: %w", accountID, err)
  }
  ```
- **Use `%v`** when you deliberately want to redact or break the error chain at an architectural or trust boundary (e.g. hiding internal database errors from public API clients):
  ```go
  if err := validateInternalToken(rawToken); err != nil {
      // Intentionally do not wrap internal token parser error
      return fmt.Errorf("invalid authentication token: %v", err)
  }
  ```

---

## 2. Sentinel Errors vs Typed Error Structs

### Error Representation Decision Matrix

| Error Type | When to Use | Declaration Idiom | Inspection Idiom |
|---|---|---|---|
| **Sentinel Error** | Fixed, static error conditions without dynamic metadata. | `var ErrNotFound = errors.New("resource not found")` | `errors.Is(err, ErrNotFound)` |
| **Typed Error Struct** | Errors carrying dynamic parameters (e.g. HTTP status, field validation errors). | `type ValidationError struct { Field string; Msg string }` | `var valErr *ValidationError`<br>`if errors.As(err, &valErr) { ... }` |
| **Formatted Error** | Contextual errors without specific program branching needs. | `fmt.Errorf("reading file %s: %w", path, err)` | Top-level logging or default handler. |
| **Joined Errors** | Collecting errors across multiple parallel or sequential steps (Go 1.20+). | `errors.Join(err1, err2, err3)` | `errors.Is` and `errors.As` traverse all joined errors. |

---

## 3. Idiomatic Error Inspection (`errors.Is` & `errors.As`)

Never inspect errors using string matching (`strings.Contains(err.Error(), "...")`). String inspection is brittle, breaks on refactorings, and violates encapsulation.

```go
package storage

import (
    "errors"
    "fmt"
    "io/fs"
)

var ErrRecordNotFound = errors.New("record not found")

type DatabaseError struct {
    Query string
    Code  int
    Err   error
}

func (e *DatabaseError) Error() string {
    return fmt.Sprintf("db error (code %d) on %q: %v", e.Code, e.Query, e.Err)
}

func (e *DatabaseError) Unwrap() error {
    return e.Err
}

// Caller Inspection Example:
func HandleError(err error) {
    // 1. Check for sentinel error
    if errors.Is(err, ErrRecordNotFound) {
        // Return 404
        return
    }

    // 2. Check for typed error struct
    var dbErr *DatabaseError
    if errors.As(err, &dbErr) {
        if dbErr.Code == 1062 { // Duplicate entry
            // Return 409 Conflict
            return
        }
    }
}
```

---

## 4. Single-Path Error Handling & Guard Clauses

Always handle errors immediately using guard clauses. Do not nest the happy path inside `else` blocks.

```go
// GOOD: Linear, clean guard clauses
user, err := findUser(id)
if err != nil {
    return fmt.Errorf("finding user %s: %w", id, err)
}

profile, err := loadProfile(user.ID)
if err != nil {
    return fmt.Errorf("loading profile for %s: %w", user.ID, err)
}

return render(profile)
```

---

## 5. Panic Avoidance Policy

Go provides `panic` and `recover`, but `panic` is **strictly reserved for unrecoverable programmer errors or package initialization failures**.

### Panic Decision Rubric

- **NEVER Panic for Operational Failures**: Network timeouts, missing database records, invalid user inputs, malformed JSON, and filesystem permission errors are normal operational states; return `error`.
- **Permissible Panics**:
  1. Package initialization wrappers (e.g. `template.Must`, `regexp.MustCompile`) during process boot.
  2. Invariant violations that indicate a fatal internal bug (e.g. unreachable state in internal state machine).
- **Top-Level Panic Recovery**: Protect HTTP servers and background workers from unexpected process crashes using recovery middleware:
  ```go
  func RecoveryMiddleware(next http.Handler) http.Handler {
      return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
          defer func() {
              if rec := recover(); rec != nil {
                  log.Printf("PANIC recovered: %v\n%s", rec, debug.Stack())
                  http.Error(w, "internal server error", http.StatusInternalServerError)
              }
          }()
          next.ServeHTTP(w, r)
      })
  }
  ```

---

## 6. Resilience & Context-Aware Retry Loops

When implementing retries for transient failures (e.g. HTTP 503, database connection drops), always enforce:
1. **Exponential Backoff with Full Jitter** (prevents thundering herd problems).
2. **Strict Context Cancellation Compliance** (`ctx.Done()`).
3. **Maximum Retry Bounds**.

```go
package retry

import (
    "context"
    "fmt"
    "math/rand"
    "time"
)

func DoWithRetry(ctx context.Context, maxAttempts int, initialDelay time.Duration, op func(ctx context.Context) error) error {
    var lastErr error
    delay := initialDelay

    for attempt := 1; attempt <= maxAttempts; attempt++ {
        err := op(ctx)
        if err == nil {
            return nil
        }
        lastErr = err

        if attempt == maxAttempts {
            break
        }

        // Add full jitter: random between 0 and delay
        jittered := time.Duration(rand.Float64() * float64(delay))
        delay = delay * 2 // Exponential backoff

        select {
        case <-ctx.Done():
            return fmt.Errorf("retry aborted by context (%w): last error: %w", ctx.Err(), lastErr)
        case <-time.After(jittered):
        }
    }

    return fmt.Errorf("operation failed after %d attempts: %w", maxAttempts, lastErr)
}
```

---

## 7. Anti-Patterns vs Pragmatic Error Handling

| Anti-Pattern | Failure Mode | Pragmatic Solution |
|---|---|---|
| **String Substring Error Check** | `strings.Contains(err.Error(), "not found")` breaks when error text changes. | Define sentinel `var ErrNotFound = errors.New(...)` and check with `errors.Is`. |
| **Ignored Error Returns** | `_ = f.Close()` or ignoring returned errors causes silent data loss. | Handle or explicitly log errors: `if err := f.Close(); err != nil { ... }`. |
| **Double Error Logging & Return** | Logging `log.Println(err)` and returning `return err` creates log flood and duplicate entries. | Add context with `%w` and return; log only once at top-level boundary. |
| **Unwrapped Error Formatting** | Using `fmt.Errorf("query error: %v", err)` strips causal chain, preventing `errors.Is`. | Use `%w` for error wrapping. |
| **Panic on Bad Input** | Calling `panic("invalid email")` crashes the entire web server process. | Return `ValidationError` or typed domain error. |

---

## 8. Concrete Code Comparisons

### Error Inspection: Fragile String Matching vs `errors.Is`

#### ❌ ANTI-PATTERN: String Inspection
```go
// BAD: Fragile string inspection that fails on any wording change
func ProcessUser(id string) error {
    err := repo.FindUser(id)
    if err != nil {
        if strings.Contains(err.Error(), "not found") {
            return ErrUserNotFound // Loss of underlying context
        }
        return err
    }
    return nil
}
```

#### ✅ PRAGMATIC: Standard `errors.Is` Inspection with `%w`
```go
// GOOD: Robust causal chain checking with wrapped context
var ErrNotFound = errors.New("user not found")

func (r *Repository) FindUser(ctx context.Context, id string) (*User, error) {
    var u User
    if err := r.db.QueryRowContext(ctx, "SELECT ...", id).Scan(&u.ID); err != nil {
        if errors.Is(err, sql.ErrNoRows) {
            return nil, fmt.Errorf("querying user %s: %w", id, ErrNotFound)
        }
        return nil, fmt.Errorf("db failure: %w", err)
    }
    return &u, nil
}

// Caller:
if errors.Is(err, ErrNotFound) {
    // Correctly handled across any number of wrapping layers
}
```

---

## 9. Fast-Path Error Verification Recipes

```bash
# Run tests for specific error paths in auth module
go test -v -run ^TestAuthErrors ./internal/auth

# Verify error wrapping behavior and failure boundaries
go test -v -run ^TestErrorChainMatching$ ./internal/storage
```
