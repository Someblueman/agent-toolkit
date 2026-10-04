# Architecture, Packages, and Interface Discipline

Read this for package layout, `internal/` boundaries, module design, interface design ("accept interfaces, return structs"), concrete-first design for interfaces, constructor idioms, and single-path refactoring.

---

## 1. Package Layout & Encapsulation

Go organizes code into packages that provide distinct namespaces and encapsulation boundaries. Package structure should reflect what each package provides rather than technical architectural layers. The Go team's guide is <https://go.dev/doc/modules/layout>; follow the repository's existing layout before either.

### Common Layout for a Module with Commands

```
repo-root/
├── cmd/
│   └── api-server/           # One directory per command: flags, config loading, dependency wiring
│       └── main.go
├── internal/                 # Packages other modules cannot import (enforced by the go command)
│   ├── auth/                 # Domain package: authentication logic, token generation
│   ├── billing/              # Domain package: billing rules, payment processing
│   ├── sqlite/               # Storage adapter: migrations, queries
│   └── httpapi/              # Transport adapter: routing, handlers, middleware
├── go.mod
└── go.sum
```

The layout guide does not use a `pkg/` directory. Exported, importable packages can live at the module root or in their own directories. Keep `pkg/` only where a repository already uses it.

### Layout Choices

| Layout | When to Use | Notes |
|---|---|---|
| **Single package** | Small libraries or a single command | All code in the module root (`package main` for a command). Split only when a package boundary clarifies the design. |
| **Commands + `internal/`** | Services and multi-command repositories | Commands under `cmd/<name>/`, supporting code in `internal/<domain>/`. Group by feature or domain, not by tier (`controllers/`, `services/`, `models/`). |
| **Importable library** | Packages meant for other modules | Exported packages at the root or in named subdirectories; keep helpers that are not part of the API in `internal/`. |

### Package Naming Rules

1. **Short, lowercase, single word**: No underscores or mixedCaps. Describe what the package provides (`auth`, `sqlite`, `httpclient`, `jsonrpc`).
2. **Avoid stutter**: Callers see the package name, so `auth.Service` rather than `auth.AuthService`, `bufio.Reader` rather than `bufio.BufReader`.
3. **Avoid uninformative names**: `util`, `common`, `helpers`, `misc`, `base`, `shared`, `models`, `types`, `interfaces`. They tell call sites nothing and accumulate unrelated code with imports from everywhere. Move each helper to the package that uses it or to a package named for what it does (`strcase`, `retry`).

---

## 2. Interface Discipline & Concrete-First Design

Go interfaces are **satisfied implicitly**, so the consumer of a dependency can declare the interface it needs without the implementation knowing about it.

### Core Principles

1. **Accept interfaces, return concrete types**:
   - Constructors and functions usually return concrete pointer or value types (`*Service`, `*Store`), so callers get the full API and new methods don't break anyone.
   - Return an interface when hiding the implementation is the point or the implementation is chosen at runtime (`errors.New` returns `error`; `cipher.NewGCM` returns `cipher.AEAD`).
   - Accept the smallest interface the function actually uses (`io.Reader`, `fmt.Stringer`).
2. **Define interfaces at the consumer**: The package that uses a dependency declares the interface it needs. The implementing package exports the concrete type.
3. **Don't define interfaces before they are used**: Without a real consumer it is hard to know which methods an interface needs.
4. **Small interfaces are the norm**: One- or two-method interfaces (`io.Reader`, `io.Closer`) are common and compose well. Larger interfaces are acceptable when a consumer genuinely needs the methods together.
5. **Concrete first**: Write concrete types first. Introduce an abstraction when it simplifies a current requirement or expresses a necessary boundary or invariant.
6. **Don't add interfaces just for mocking**: Do not define an interface on the implementor side "for mocking". Design the API so it can be tested through the real implementation, using in-memory dependencies (`net/http/httptest`, an in-memory SQLite database, `net.Pipe`), or a small hand-written fake next to the test. Avoid generated-mock sprawl (`mockery`, `gomock`) for single-implementation types.

---

## 3. Struct Construction

### Construction Decision Rubric

| Situation | Recommended Idiom | Example |
|---|---|---|
| **No invariants; zero values are useful** | Struct literal | `cfg := Config{Host: "localhost", Port: 8080}` |
| **Validation or required setup** | Constructor returning an error | `func New(host string, port int) (*Client, error)` |
| **Many optional settings with defaults** | Config struct or functional options | `func NewServer(addr string, opts ...Option) (*Server, error)` |

Prefer struct literals and simple constructors when they make requirements clear. Functional options or builders can help with genuinely optional configuration or staged validation. Avoid boilerplate that obscures required fields; field count alone is not a decision rule. Make the zero value useful where practical (`sync.Mutex`, `bytes.Buffer`).

---

## 4. Single-Path Execution & In-Place Refactoring

Before renaming methods, modifying struct fields, or altering package paths, establish published API, durable-data, and cross-process contracts. Preserve or migrate those contracts as required. For internal APIs:
- Perform a **clean in-place replacement** and update all call sites, internal usages, and tests in the same change.
- **Legacy retention anti-patterns** (when no published compatibility requirement exists):
  - *Forwarding shims*:
    ```go
    // BAD: deprecated wrapper kept although every caller is in this module
    // Deprecated: use NewClient instead.
    func New(host string) *Client { return NewClient(host) }
    ```
  - *Zombie decoders*: fallback decoding of obsolete fields without an explicit migration requirement:
    ```go
    // BAD: zombie fallback decoding
    if raw["old_token"] != nil { ... }
    ```
  - *Ghost code*: commented-out legacy code or dead files (`legacy_store.go`).
- When an exported API must keep a deprecated wrapper for external callers, mark it `// Deprecated:` and, on Go 1.26+, add a `//go:fix inline` directive so `go fix` can rewrite callers to the replacement.

---

## 5. Architectural Anti-Patterns vs Pragmatic Patterns

| Anti-Pattern | Why It Fails | Pragmatic Solution |
|---|---|---|
| **Producer-side interfaces** | Declaring `type UserService interface` next to `userService` couples callers to the producer's method set and adds boilerplate. | Return `*user.Service`. Let callers define small interfaces if they need them. |
| **Grab-bag `util` package** | Collects unrelated code, says nothing at call sites, and grows imports from everywhere. | Co-locate helpers with their users or name a package for what it does. |
| **Speculative builders** | Builder boilerplate, verbose call sites, extra allocations. | Struct literal or a simple `New(...)` constructor. |
| **Package stutter** | `auth.AuthService` repeats itself at every call site. | Name the type `auth.Service`. |
| **Tier packages (`models/`, `controllers/`)** | Spreads one feature across horizontal packages that all import each other, inviting import cycles. | Group by feature or domain: `internal/user`, `internal/order`. |

---

## 6. Concrete Code Comparisons

### Interface Placement & Concrete-First Design

#### ❌ ANTI-PATTERN: Producer-Side Interface Returned from the Constructor
```go
// File: internal/user/service.go
package user

// BAD: producer defines an interface for its own single implementation
type UserService interface {
    Get(ctx context.Context, id string) (*User, error)
    Create(ctx context.Context, u *User) error
}

type userService struct {
    db *sql.DB
}

// BAD: returns the interface instead of the concrete type
func NewUserService(db *sql.DB) UserService {
    return &userService{db: db}
}
```

#### ✅ PRAGMATIC: Concrete Return + Consumer-Side Interface
```go
// File: internal/user/service.go
package user

import (
    "context"
    "database/sql"
)

type User struct {
    ID string
}

// GOOD: export the concrete type
type Service struct {
    db *sql.DB
}

// GOOD: return the concrete pointer
func NewService(db *sql.DB) *Service {
    return &Service{db: db}
}

func (s *Service) Get(ctx context.Context, id string) (*User, error) {
    // concrete domain logic
    return &User{ID: id}, nil
}

// ---------------------------------------------------------
// File: internal/httpapi/users.go
package httpapi

import (
    "context"

    "example.com/app/internal/user"
)

// GOOD: the consumer declares the one method it needs
type userGetter interface {
    Get(ctx context.Context, id string) (*user.User, error)
}

type Handler struct {
    users userGetter
}

func NewHandler(users userGetter) *Handler {
    return &Handler{users: users}
}
```

---

### Struct Construction: Small Builder vs Pragmatic Constructor

#### ❌ ANTI-PATTERN: Fluent Builder for 3 Fields
```go
// BAD: 40 lines of builder boilerplate for a simple 3-field config
type ClientBuilder struct {
    endpoint string
    timeout  time.Duration
    retries  int
}

func NewClientBuilder() *ClientBuilder {
    return &ClientBuilder{timeout: 30 * time.Second, retries: 3}
}

func (b *ClientBuilder) WithEndpoint(endpoint string) *ClientBuilder {
    b.endpoint = endpoint
    return b
}

func (b *ClientBuilder) WithTimeout(timeout time.Duration) *ClientBuilder {
    b.timeout = timeout
    return b
}

func (b *ClientBuilder) WithRetries(retries int) *ClientBuilder {
    b.retries = retries
    return b
}

func (b *ClientBuilder) Build() (*Client, error) {
    if b.endpoint == "" {
        return nil, errors.New("endpoint required")
    }
    return &Client{endpoint: b.endpoint, timeout: b.timeout, retries: b.retries}, nil
}
```

#### ✅ PRAGMATIC: Config Struct with Defaults
```go
// GOOD: direct and clear; zero values select defaults
type Client struct {
    endpoint string
    timeout  time.Duration
    retries  int
}

type Config struct {
    Endpoint string
    Timeout  time.Duration // zero means 30s
    Retries  int           // zero means 3
}

func NewClient(cfg Config) (*Client, error) {
    if cfg.Endpoint == "" {
        return nil, errors.New("endpoint is required")
    }
    timeout := cfg.Timeout
    if timeout == 0 {
        timeout = 30 * time.Second
    }
    retries := cfg.Retries
    if retries == 0 {
        retries = 3
    }
    return &Client{
        endpoint: cfg.Endpoint,
        timeout:  timeout,
        retries:  retries,
    }, nil
}
```

---

## 7. Package Inspection Recipes

Importing another module's `internal/` package is rejected by `go build` and `go vet`; no separate check is needed.

```bash
# Direct imports of one package
go list -f '{{.ImportPath}}: {{join .Imports " "}}' ./internal/auth

# Everything a package transitively depends on
go list -deps ./internal/auth

# Why the module needs a given dependency
go mod why -m golang.org/x/sync

# Check that downloaded module sources in the cache haven't been modified since download
go mod verify
```
