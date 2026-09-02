# Idiomatic Language Simplification Patterns

This reference manual catalogs battle-tested simplification patterns across modern systems languages, managed runtimes, and functional ecosystems: **Rust, Go, Python, C++, and Haskell**.

---

## 1. Rust Simplification Patterns

### 1.1 Unwinding `Rc<RefCell<T>>` Cycles to Arena Index Graphs
- **Problem**: Self-referential and cyclic graphs built with `Rc<RefCell<Node>>` incur runtime borrow checking overhead, memory leak risks on drop, and cache-unfriendly pointer chasing.
- **Simplification**: Store nodes in a flat `Vec<Node>` and reference neighbors via `NodeId(usize)` index handles.
```rust
// Simplified Arena Graph
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct NodeId(pub usize);

pub struct ArenaGraph {
    nodes: Vec<Node>,
}
```

### 1.2 Unified Error Handling with `thiserror` and `anyhow`
- **Problem**: Manually implementing `std::fmt::Display` and `std::error::Error` for dozens of custom error types across crates.
- **Simplification**: Use `thiserror` for structured library domain errors and `anyhow` for top-level application binaries.
```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum DatabaseError {
    #[error("Connection timed out after {timeout_ms}ms")]
    Timeout { timeout_ms: u64 },
    #[error("Query failed: {0}")]
    QueryFailure(#[from] sqlx::Error),
}
```

### 1.3 Concrete Slices over Over-Generic Trait Bounds
- **Problem**: `fn process<T: AsRef<str>, I: IntoIterator<Item = T>>(items: I)` explodes compilation times and creates large monomorphized binaries.
- **Simplification**: Accept concrete `&[&str]` or `&[T]` unless multiple distinct types must be polymorphically accepted at the public API boundary.

---

## 2. Go Simplification Patterns

### 2.1 "Accept Interfaces, Return Concrete Structs"
- **Problem**: Functions returning interfaces hide concrete fields and methods, prevent compiler inlining, and force heap escape allocations.
- **Simplification**: Return concrete pointers or values. Let consumers define small, localized (1-2 method) interfaces where needed.
```go
// Good: Return concrete struct
func NewUserRepository(db *sql.DB) *UserRepository {
    return &UserRepository{db: db}
}

// Consumer defines minimal local interface for testing/mocking
type UserFinder interface {
    FindUser(id string) (*User, error)
}
```

### 2.2 Mutex Pragmatism over Channel Multiplexing
- **Problem**: Overusing goroutines, channels, and complex `select` multiplexing loops for simple local mutable state adds $10\times$ scheduling overhead and race/deadlock risks.
- **Simplification**: Use `sync.Mutex` or `sync.RWMutex` for localized state updates. Reserve channels strictly for pipeline streaming, producer-consumer queues, and shutdown cancellation signals.

---

## 3. Python Simplification Patterns

### 3.1 Modern `@dataclass(slots=True)` & `match/case`
- **Problem**: Verbose boilerplate classes with manual `__init__`, `__repr__`, `__eq__`, and `__dict__` memory overhead.
- **Simplification**: Use `@dataclass(slots=True, frozen=True)` for 30–50% memory reduction and Python 3.10+ `match / case` for structural pattern matching.
```python
from dataclasses import dataclass

@dataclass(slots=True, frozen=True)
class OrderCreated:
    order_id: str
    amount: float

@dataclass(slots=True, frozen=True)
class OrderCancelled:
    order_id: str
    reason: str

Event = OrderCreated | OrderCancelled

def handle_event(event: Event) -> None:
    match event:
        case OrderCreated(oid, amt) if amt > 1000.0:
            print(f"High-value order {oid}: ${amt}")
        case OrderCreated(oid, amt):
            print(f"Standard order {oid}: ${amt}")
        case OrderCancelled(oid, reason):
            print(f"Cancelled {oid}: {reason}")
```

### 3.2 Context Managers & Generator Pipelines
- **Problem**: Custom iterator classes with manual state flags and repetitive `try/finally` cleanup blocks.
- **Simplification**: Use `@contextlib.contextmanager` and generator expressions (`yield`).

---

## 4. Modern C++ Simplification Patterns

### 4.1 C++20 Concepts and `std::span` over SFINAE
- **Problem**: Inscrutable template metaprogramming using `std::enable_if_t`, `std::void_t`, and raw pointers.
- **Simplification**: Use C++20 `concepts`, `requires` clauses, and `std::span<const T>`.
```cpp
#include <span>
#include <concepts>
#include <numeric>

template<std::integral T>
T sum_buffer(std::span<const T> buffer) {
    return std::accumulate(buffer.begin(), buffer.end(), T{0});
}
```

### 4.2 Value-Semantic `std::variant` over Virtual Inheritance
- **Problem**: Abstract base classes with `virtual` methods, `std::unique_ptr<Base>`, dynamic dispatch indirection, and heap allocations.
- **Simplification**: Use `std::variant` and `std::visit` for value polymorphism, contiguous storage, and direct compiler optimization.

---

## 5. Haskell Simplification Patterns

### 5.1 The ReaderT Application Pattern
- **Problem**: 5-layer monad transformer stacks (`ReaderT (StateT (ExceptT ...)))`) requiring endless `liftIO` calls.
- **Simplification**: A unified `ReaderT Env IO a` where `Env` holds configuration, DB pools, and explicit `IORef` / `TVar` states.

### 5.2 Strict Worker-Wrapper & Space Leak Elimination
- **Problem**: Lazy accumulator expressions in loops/folds (`go (acc + x)`) build thunks on the heap, causing space leaks and GC thrashing.
- **Simplification**: Apply `{-# LANGUAGE BangPatterns #-}` to worker arguments (`!acc`) or use strict left folds (`Data.List.foldl'`), compiling to unboxed CPU registers.
```haskell
{-# LANGUAGE BangPatterns #-}

sumStrict :: [Int] -> Int
sumStrict xs = go xs 0
  where
    go [] !acc = acc
    go (y:ys) !acc = go ys (acc + y)
```
