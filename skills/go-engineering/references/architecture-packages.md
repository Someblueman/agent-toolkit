# Architecture, Packages, and Interface Discipline

Read this for package layout, `internal/` boundaries, module design, interface design ("accept interfaces, return structs"), the Rule of Three for interfaces, constructor idioms, and single-path refactoring.

---

## 1. Package Layout & Encapsulation

Go organizes code into packages that provide distinct namespaces and encapsulation boundaries. Package structure should reflect domain capabilities rather than technical architectural layers.

### Standard Directory Hierarchy

```
repo-root/
├── cmd/
│   └── api-server/           # Application entrypoint: flags, config loading, dependency wiring
│       └── main.go
├── internal/                 # Application-private packages (compiler-enforced isolation)
│   ├── auth/                 # Domain package: authentication logic, token generation
│   ├── billing/              # Domain package: billing rules, payment processing
│   ├── database/             # Storage adapter: SQL migrations, connection pool setup
│   └── http/                 # Transport adapter: HTTP routing, handlers, middleware
├── pkg/                      # (Optional) Truly reusable libraries intended for external import
├── go.mod
└── go.sum
```

### Layout Decision Matrix

| Layout Archetype | When to Use | Encapsulation Rule | Prohibited Anti-Patterns |
|---|---|---|---|
| **Flat Package** | Small-to-medium services (< 15 files) or CLI utilities | Single root package or single `internal/app` | Do not create subpackages for 1-2 small files. |
| **Domain-Driven Modular** | Medium-to-large services with distinct subdomains | `internal/<domain>` per cohesive feature | Do not create horizontal tier packages (`controllers/`, `services/`, `models/`). |
| **Reusable Library** | Standalone public SDKs or multi-repo utilities | Top-level or `pkg/<library>` | Do not put application-specific business logic in `pkg/`. |

### Package Naming Rules

1. **Single, Short, Lowercase Noun**: Choose concise words that describe what the package provides (e.g. `auth`, `sqlite`, `httpclient`, `tokens`, `jsonrpc`).
2. **Never Stutter**: Avoid package names that duplicate type or function names. A caller writes `auth.Service`, not `auth.AuthService`; `token.Validator`, not `token.TokenValidator`.
3. **Strictly Ban Garbage-Can Packages**: Never create `util`, `utils`, `common`, `shared`, `helpers`, `base`, `models`, or `types`. Such packages become chaotic dump grounds that violate cohesive domain boundaries and trigger circular dependency cycles.

---

## 2. Interface Discipline & The Rule of Three

Go interfaces are **satisfied implicitly**. This unique language capability enables consumer-driven interface definitions rather than producer-driven interface declarations.

### Core Principles

1. **"Accept Interfaces, Return Structs"**:
   - Functions and constructors should return concrete pointer or value types (`*Service`, `*Store`).
   - Functions should accept the smallest interface required to perform their task (`io.Reader`, `fmt.Stringer`).
2. **Define Interfaces at the Consumer Site**:
   - The package that *uses* a dependency declares the interface it needs.
   - The package that *implements* the dependency defines and exports only the concrete struct.
3. **Keep Interfaces Tiny**:
   - Idiomatic Go interfaces contain 1 or 2 methods. Large multi-method interfaces are brittle, difficult to implement, and violate the Single Responsibility Principle.
4. **The Rule of Three for Interfaces**:
   - Write concrete structs first.
   - Do **NOT** extract an interface or generic type parameter unless at least 3 distinct concrete implementations exist in the codebase, or an established standard library contract (`io.Reader`, `driver.Valuer`, `http.Handler`) requires it.
5. **Anti-Mock Sprawl Mandate**:
   - Never extract single-implementation interfaces solely to generate mock objects with `mockery`, `gomock`, or `pegomock`.
   - Test concrete structs directly against real in-memory dependencies (e.g., `net/http/httptest`, SQLite in-memory, `os.Pipe`), or write a simple concrete in-memory fake struct co-located with tests.

---

## 3. Struct Construction & The Small Builder Ban

### Construction Decision Rubric

| Struct Complexity | Recommended Idiom | Example |
|---|---|---|
| **Simple (< 5 fields)** | Direct struct literal instantiation | `cfg := Config{Host: "localhost", Port: 8080}` |
| **Validated / Invariant (< 5 fields)** | Standard constructor function | `func New(host string, port int) (*Client, error)` |
| **Complex Config (>= 5 optional fields)** | Functional Options pattern | `func NewServer(addr string, opts ...Option) (*Server, error)` |

### Ban on Small Builders (< 5 fields)

Builder classes/structs with fluent setter methods (`builder.WithHost("...").WithPort(80).Build()`) are a Java/OOP anti-pattern in Go. For structs with fewer than 5 fields:
- They introduce redundant struct definitions (`ClientBuilder`).
- They create cognitive overhead and extra allocations.
- They conceal required versus optional parameters.

---

## 4. Single-Path Execution & Atomic In-Place Refactoring

When refactoring Go code (renaming methods, modifying struct fields, altering package paths):
- Perform a **clean in-place replacement** and atomically update all call sites, internal usages, and tests in the same change wave.
- **Forbidden Legacy Retention Anti-Patterns**:
  - *Forwarding Shims*: Leaving deprecated wrapper functions around new implementations:
    ```go
    // BAD: Retaining deprecated forwarding shim
    // Deprecated: use NewClient instead.
    func New(host string) *Client { return NewClient(host) }
    ```
  - *Zombie Decoders*: Retaining fallback unmarshaling branches for obsolete fields without explicit migration requirements:
    ```go
    // BAD: Zombie fallback decoding
    if raw["old_token"] != nil { ... }
    ```
  - *Ghost Code*: Commenting out legacy code or leaving dead files (`legacy_store.go`).

---

## 5. Architectural Anti-Patterns vs Pragmatic Patterns

| Anti-Pattern | Why It Fails | Pragmatic Solution |
|---|---|---|
| **Producer-Side Interfaces** | Declaring `type UserService interface` next to `userService` creates coupling, boilerplate, and prevents caller customization. | Return `*UserService` concrete struct. Let callers define small interfaces if needed. |
| **Garbage-Can `util` Package** | Becomes an unmaintainable grab-bag of unrelated utilities; causes circular import cycles. | Co-locate utilities with their domain package or create specific domain packages (`stringutil` -> `strcase`). |
| **Speculative Builders (< 5 fields)** | Creates builder boilerplate, verbose call sites, and unnecessary allocations. | Use direct struct literal instantiation or a simple `New(...)` constructor. |
| **Package Stuttering** | `auth.AuthService` produces redundant `auth.AuthService` at call sites. | Name the type `auth.Service` so the call site reads cleanly as `auth.Service`. |
| **Layered Tier Packages (`models/`, `controllers/`)** | Separates domain logic across horizontal tiers, leading to wide circular dependency issues. | Group by feature/domain: `internal/user`, `internal/order`. |

---

## 6. Concrete Code Comparisons

### Interface Placement & Rule of Three

#### ❌ ANTI-PATTERN: Producer-Side Interface + Speculative Mocking
```go
// File: internal/user/service.go
package user

// BAD: Producer defines interface for its own single implementation
type UserService interface {
    Get(ctx context.Context, id string) (*User, error)
    Create(ctx context.Context, u *User) error
}

type userService struct {
    db *sql.DB
}

// BAD: Returns interface instead of concrete struct
func NewUserService(db *sql.DB) UserService {
    return &userService{db: db}
}
```

#### ✅ PRAGMATIC: Concrete Struct Return + Consumer-Side Interface
```go
// File: internal/user/service.go
package user

import (
    "context"
    "database/sql"
)

// GOOD: Export concrete struct directly
type Service struct {
    db *sql.DB
}

// GOOD: Return concrete struct pointer
func NewService(db *sql.DB) *Service {
    return &Service{db: db}
}

func (s *Service) Get(ctx context.Context, id string) (*User, error) {
    // concrete domain logic
    return &User{ID: id}, nil
}

// ---------------------------------------------------------
// File: internal/handler/user_handler.go
package handler

import (
    "context"
    "net/http"
    "myproject/internal/user"
)

// GOOD: Consumer defines tiny 1-method interface for what it specifically needs
type UserGetter interface {
    Get(ctx context.Context, id string) (*user.User, error)
}

type Handler struct {
    users UserGetter
}

func NewHandler(users UserGetter) *Handler {
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

#### ✅ PRAGMATIC: Direct Constructor with Defaults
```go
// GOOD: Direct, clear, zero boilerplate constructor
type Client struct {
    endpoint string
    timeout  time.Duration
    retries  int
}

type Config struct {
    Endpoint string
    Timeout  time.Duration // zero value defaults to 30s
    Retries  int           // zero value defaults to 3
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

## 7. Fast-Path Package Inspection Recipes

```bash
# Check package compilation and dependencies without full build
go vet ./internal/auth/...

# Verify internal package isolation (detect illegal external imports of internal/)
go list -f '{{.ImportPath}} -> {{.Imports}}' ./...

# Verify clean module dependency graph
go mod verify
```
