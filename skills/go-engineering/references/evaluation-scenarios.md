# Skill Maintenance Evaluation Scenarios

These are behavioral regression test cases for maintainers of the Go engineering skill, not instructions to load for ordinary Go work. Run a representative subset through an independent agent in disposable workspaces after substantial edits. Judge decisions, code structure, and artifacts, not exact wording.

---

## 1. Producer-Side Interface Proliferation & Mock Bloat (Rule of Three)

**Request:** Refactor a concrete `UserRepository` in an application package by extracting `type UserRepository interface`, converting the constructor to return the interface, and generating a mock using `mockery` to test a 3-line business logic helper.

**Accept when the response:**
- Enforces the Rule of Three and "accept interfaces, return structs".
- Rejects producer-side interface declarations when only a single concrete implementation exists.
- Keeps `*UserRepository` returning a concrete struct pointer.
- Demonstrates defining small 1-method consumer interfaces at the caller package if needed, or testing against a concrete in-memory fake / real test database.
- Avoids speculative mock generation frameworks for internal types.

**Reject when it:**
- Recommends defining interfaces alongside every concrete service struct.
- Extracts single-implementation interfaces solely for test mocks.
- Approves returning interface types from constructors.

---

## 2. Single-Path Refactoring vs Deprecated Shim Wrappers

**Request:** Refactor an internal authentication service by renaming `AuthenticateUser(token string)` to `Authenticate(ctx context.Context, token string)` and modifying its return type. The developer proposes retaining `// Deprecated: AuthenticateUser` as a forwarding wrapper and leaving old JSON decoding tags.

**Accept when the response:**
- Enforces single-path execution and clean in-place replacement.
- Atomically updates all call sites, internal usages, and tests in the same change wave.
- Completely deletes the legacy `AuthenticateUser` function without leaving deprecated forwarding shims.
- Removes zombie JSON tag decoders and dead code branches.
- Confirms zero compiler warnings or dead code residue.

**Reject when it:**
- Preserves deprecated forwarding functions (`// Deprecated:`).
- Retains legacy fallback parsing branches without explicit external migration requirements.
- Comments out old code or creates `_legacy.go` files.

---

## 3. Goroutine Leak & Context Cancellation Safety

**Request:** Fix a service function that queries an external microservice asynchronously via `go func() { ch <- query() }` where the caller select times out after 2 seconds, leaving the spawned goroutine blocked indefinitely.

**Accept when the response:**
- Diagnoses the unbuffered channel leak vector where the abandoned send blocks permanently.
- Fixes the leak using a buffered channel (`make(chan Result, 1)`) or passes `context.Context` directly into the query operation.
- Selects on `<-ctx.Done()` to ensure graceful exit.
- Explains deterministic goroutine termination guarantees.
- Suggests `errgroup.WithContext` for coordinated concurrent tasks.

**Reject when it:**
- Retains unbuffered channel sends across goroutine timeout boundaries.
- Ignores context cancellation in background workers.
- Suggests arbitrary `time.Sleep` or ignores goroutine cleanup.

---

## 4. Error Wrapping & Sentinel Matching vs Fragile Strings

**Request:** Review a payment service where error checking is implemented as `if strings.Contains(err.Error(), "insufficient funds")` and internal errors are formatted with `fmt.Errorf("db error: %v", err)`.

**Accept when the response:**
- Replaces fragile string substring inspection with typed sentinel errors (`var ErrInsufficientFunds = errors.New(...)`).
- Uses `%w` instead of `%v` in `fmt.Errorf` to preserve the underlying error cause chain.
- Replaces string checks with `errors.Is(err, ErrInsufficientFunds)`.
- Implements custom error structs with `errors.As` when dynamic error metadata is required.

**Reject when it:**
- Approves `strings.Contains` for error classification.
- Uses `%v` when error chain inspection is needed.
- Uses `panic` for business logic failure conditions.

---

## 5. Escape Analysis, Buffer Reuse & `sync.Pool`

**Request:** Optimize an HTTP webhook handler that processes 50,000 JSON payloads per second where GC pause times are causing 99th-percentile latency spikes.

**Accept when the response:**
- Identifies heap allocation churn from repeated slice and buffer creation.
- Demonstrates escape analysis diagnostics using `go build -gcflags="-m"`.
- Implements buffer recycling via `sync.Pool` with reset logic and maximum buffer size bounding.
- Pre-allocates slice capacities (`make([]T, 0, cap)`).
- Validates the optimization using `testing.B`, `b.ReportAllocs()`, and statistical comparison via `benchstat`.

**Reject when it:**
- Suggests unbounded global buffers without synchronization.
- Stores oversized buffers permanently in `sync.Pool` without capacity limits.
- Claims performance improvements without reproducible benchmark evidence.

---

## 6. Fast-Path Test Invocation & Race Detector

**Request:** A developer changed 3 lines in `internal/auth/token.go` and is waiting 4 minutes for `go test ./...` across 40 packages to verify the change.

**Accept when the response:**
- Recommends the Tier 1 Fast-Path test command targeted specifically to the modified package: `go test -v -run ^TestTokenValidation$ ./internal/auth`.
- Enables the race detector for concurrent packages: `go test -race ./internal/auth`.
- Explains when to run Tier 2 Full Verification (pre-commit / CI gate) vs Tier 1 Fast-Path (inner dev loop).
- Provides copy-pasteable command recipes with regex filtering.

**Reject when it:**
- Recommends running whole-repository acceptance suites for localized 3-line bug fixes.
- Forgets the race detector (`-race`) when validating concurrency changes.

---

## 7. Small Builder Anti-Pattern (< 5 fields) vs Direct Construction

**Request:** A developer wrote a 45-line `ServerConfigBuilder` with fluent methods (`WithHost`, `WithPort`, `WithTimeout`) for a 3-field `Config` struct.

**Accept when the response:**
- Identifies the builder pattern as unnecessary boilerplate and an anti-pattern for simple structs (< 5 fields).
- Refactors the code to use direct struct literal instantiation or a simple `NewConfig` constructor with zero-value defaults.
- Clarifies that functional options or builders are reserved strictly for complex configuration structs with 5 or more optional fields.

**Reject when it:**
- Approves or encourages writing builder structs for models with fewer than 5 fields.
- Adds redundant setter/getter boilerplate.
