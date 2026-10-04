# Error Handling, Inspection, and Resilience

Read this for error wrapping (`%w`), inspection via `errors.Is`, `errors.As` and `errors.AsType`, joining errors (`errors.Join`), sentinel vs typed errors, panic policy, and retry with backoff.

---

## 1. Error Wrapping & Semantic Propagation

Go treats errors as values. When propagating an error, add the context the caller lacks while preserving the cause the caller may need to inspect.

### Wrapping Rules: `%w` vs `%v`

- **Use `%w`** when callers may need to inspect the cause with `errors.Is` or `errors.As`. Wrapping makes the cause part of your API, so wrap deliberately:
  ```go
  if _, err := db.ExecContext(ctx, query, accountID); err != nil {
      return fmt.Errorf("updating balance for account %s: %w", accountID, err)
  }
  ```
- **Use `%v`** to deliberately break the chain at an architectural or trust boundary, for example so callers can't depend on an internal parser's error types:
  ```go
  if err := validateInternalToken(rawToken); err != nil {
      return fmt.Errorf("invalid authentication token: %v", err)
  }
  ```
- One `fmt.Errorf` may contain several `%w` verbs (Go 1.20+); the result matches each wrapped error.

### Message Style

- Error strings are lowercase and have no trailing punctuation, because they are usually embedded in other messages: `"reading config: open app.toml: no such file or directory"`.
- Describe what was being done (`"reading config"`), not that it failed (`"failed to read config"`); the error itself says it failed.
- Don't repeat what the wrapped error already says (the file name in an `*fs.PathError`, for instance).

---

## 2. Sentinel Errors vs Typed Error Structs

### Error Representation Decision Matrix

| Error Type | When to Use | Declaration Idiom | Inspection Idiom |
|---|---|---|---|
| **Sentinel error** | Fixed conditions without extra data. | `var ErrNotFound = errors.New("not found")` | `errors.Is(err, ErrNotFound)` |
| **Typed error** | Errors carrying data the caller acts on (field name, status code). | `type ValidationError struct { Field, Msg string }` | `errors.As(err, &target)` or, on Go 1.26+, `errors.AsType[*ValidationError](err)` |
| **Formatted error** | Context for humans, no programmatic branching expected. | `fmt.Errorf("reading %s: %w", path, err)` | Logged or returned at the top level. |
| **Joined errors** | Several independent failures (cleanup steps, validation, parallel work). Go 1.20+. | `errors.Join(err1, err2)` | `errors.Is` and `errors.As` search every joined error. |

Exported sentinels and error types are part of a package's API. Add them when callers need to branch, not for every failure.

---

## 3. Error Inspection (`errors.Is`, `errors.As`, `errors.AsType`)

Never inspect errors by matching text (`strings.Contains(err.Error(), "...")`). Messages change, wrapping changes them further, and the check silently stops matching.

```go
package storage

import (
    "errors"
    "fmt"
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

const codeDuplicateEntry = 1062

// Status maps a storage error to an HTTP status code.
func Status(err error) int {
    if errors.Is(err, ErrRecordNotFound) {
        return 404
    }
    var dbErr *DatabaseError // on Go 1.26+: if dbErr, ok := errors.AsType[*DatabaseError](err); ok
    if errors.As(err, &dbErr) && dbErr.Code == codeDuplicateEntry {
        return 409
    }
    return 500
}
```

Return typed errors as pointers (`*DatabaseError`) consistently, and wrap the pointer, not a pointer to it: on Go 1.27 `go vet` flags `fmt.Errorf("%w", p)` where `p` is `*E` and `E` already implements `error`.

---

## 4. Guard Clauses

Handle errors immediately and keep the happy path unindented. Don't nest it inside `else` blocks.

```go
user, err := findUser(ctx, id)
if err != nil {
    return fmt.Errorf("finding user %s: %w", id, err)
}

profile, err := loadProfile(ctx, user.ID)
if err != nil {
    return fmt.Errorf("loading profile for %s: %w", user.ID, err)
}

return render(profile)
```

---

## 5. Panic Policy

Don't use `panic` for normal error handling.

- **Return errors for operational failures**: timeouts, missing records, invalid input, malformed JSON and permission errors are expected states.
- **Acceptable panics**:
  1. `Must`-style helpers used during initialization with constant inputs (`regexp.MustCompile`, `template.Must`).
  2. Programmer bugs and impossible states, such as an unreachable case in an internal state machine.
  3. Package-internal panic/recover as control flow (as `encoding/json` does) only if the panic never escapes the package's API.
- **HTTP servers already recover handler panics**: `net/http` recovers a panic in `ServeHTTP`, logs the stack trace and closes the connection, isolating the failure to that request. Recovery middleware is only for a custom response or structured logging. It must re-panic `http.ErrAbortHandler`, and it does not cover goroutines the handler starts.
- **Goroutines you start**: A panic in any goroutine without a `recover` in that goroutine crashes the whole process. That is usually the right outcome for a bug. Add a `recover` only where a supervisor can meaningfully restart the work.

```go
func Recover(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            rec := recover()
            if rec == nil {
                return
            }
            if rec == http.ErrAbortHandler {
                panic(rec) // deliberate abort: let net/http handle it
            }
            slog.ErrorContext(r.Context(), "handler panic", "panic", rec, "stack", string(debug.Stack()))
            http.Error(w, "internal server error", http.StatusInternalServerError)
        }()
        next.ServeHTTP(w, r)
    })
}
```

---

## 6. Retry with Backoff

Retry only operations that are safe to repeat (idempotent, or protected by an idempotency key) and only errors that are transient (timeouts, 503, connection resets). Every retry loop needs:
1. **A retryability check**: permanent errors (bad input, 4xx, not found) return immediately.
2. **Exponential backoff with full jitter and a cap**: sleep a random duration in `[0, min(maxDelay, base*2^attempt))`.
3. **Cancellation**: stop waiting as soon as the context is done.
4. **A bounded number of attempts**.

```go
package retry

import (
    "context"
    "fmt"
    "math/rand/v2"
    "time"
)

// Do calls op until it succeeds, returns a non-retryable error, the context is done,
// or maxAttempts calls have been made. base and maxDelay must be positive.
func Do(ctx context.Context, maxAttempts int, base, maxDelay time.Duration,
    retryable func(error) bool, op func(context.Context) error) error {
    delay := base
    for attempt := 1; ; attempt++ {
        err := op(ctx)
        if err == nil || !retryable(err) {
            return err
        }
        if attempt >= maxAttempts {
            return fmt.Errorf("giving up after %d attempts: %w", attempt, err)
        }

        timer := time.NewTimer(rand.N(delay)) // full jitter
        select {
        case <-ctx.Done():
            timer.Stop()
            return fmt.Errorf("retry stopped: %w (last error: %w)", context.Cause(ctx), err)
        case <-timer.C:
        }
        delay = min(2*delay, maxDelay)
    }
}
```

Before writing one, check whether the client library already retries (many cloud SDKs and database drivers do); stacked retry layers multiply attempts.

---

## 7. Anti-Patterns vs Pragmatic Error Handling

| Anti-Pattern | Failure Mode | Pragmatic Solution |
|---|---|---|
| **Substring error checks** | `strings.Contains(err.Error(), "not found")` breaks when wording or wrapping changes. | Sentinel or typed errors checked with `errors.Is`/`errors.As`. |
| **Discarded errors** | `_ = enc.Encode(v)` or an unchecked call hides failures. | Handle or return every error. Ignoring an error needs a stated reason. |
| **Unchecked `Close` on written files** | `Close` can report the final write failure, so data loss goes unnoticed. | Check `Close` (or `Sync` then `Close`) for files you wrote. Ignoring `Close` on read-only files is common. |
| **Log and return** | The same error is logged at every layer. | Add context with `%w` and return; log once where it is handled. |
| **`%v` where callers branch on the cause** | `fmt.Errorf("query: %v", err)` breaks `errors.Is` for callers that need it. | Use `%w` unless hiding the cause is intended. |
| **Panic on bad input** | `panic("invalid email")` turns a client mistake into a crash or a 500. | Return a validation error. |
| **Retrying everything** | Retrying permanent errors or non-idempotent writes wastes time or duplicates effects. | Classify errors; retry only safe, transient failures. |

---

## 8. Concrete Code Comparisons

### Error Inspection: Fragile String Matching vs `errors.Is`

#### ❌ ANTI-PATTERN: String Inspection
```go
// BAD: breaks on any wording change and discards the underlying context
func ProcessUser(ctx context.Context, id string) error {
    _, err := repo.FindUser(ctx, id)
    if err != nil {
        if strings.Contains(err.Error(), "not found") {
            return ErrUserNotFound
        }
        return err
    }
    return nil
}
```

#### ✅ PRAGMATIC: Sentinel + `%w` + `errors.Is`
```go
var ErrNotFound = errors.New("user not found")

func (r *Repository) FindUser(ctx context.Context, id string) (*User, error) {
    var u User
    err := r.db.QueryRowContext(ctx, "SELECT id FROM users WHERE id = $1", id).Scan(&u.ID)
    if errors.Is(err, sql.ErrNoRows) {
        return nil, fmt.Errorf("querying user %s: %w", id, ErrNotFound)
    }
    if err != nil {
        return nil, fmt.Errorf("querying user %s: %w", id, err)
    }
    return &u, nil
}

// Caller: matches through any number of wrapping layers.
if errors.Is(err, ErrNotFound) {
    // ...
}
```

---

## 9. Error Verification Recipes

```bash
# Run the error-path tests of one package
go test -run '^TestAuthErrors' ./internal/auth

# Vet checks printf-style verbs, including misuse of %w
go vet ./internal/storage
```
