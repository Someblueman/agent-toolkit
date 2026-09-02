# Pattern Stripping and Hierarchy Flattening

## 1. The Design Pattern Overuse Trap

Design patterns originated in the early 1990s as workarounds for limitations in legacy object-oriented languages that lacked first-class functions, closures, algebraic data types, and structural pattern matching.

In modern languages (Rust, Go, Modern Python 3.10+, C++20, TypeScript, Haskell), many classic Gang of Four (GoF) patterns represent **pure accidental boilerplate**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        MODERN PATTERN EQUIVALENCE MATRIX                               │
├──────────────────────────┬─────────────────────────────┬───────────────────────────────┤
│ Legacy GoF Pattern       │ Modern Language Replacement │ Architectural Benefit         │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ Strategy Pattern         │ First-class lambda / fn ptr │ Zero classes, direct inlining │
│ Factory / Abstract Factory│ Standalone constructor fn   │ Eliminates class explosion    │
│ Visitor Pattern          │ Tagged Union + `match/case` │ Compile-time exhaustiveness   │
│ State Pattern            │ Enum State + Match Table    │ Explicit transitions, no heap │
│ Command Pattern          │ Closure / Async Future      │ Direct lexical scope capture  │
│ Builder Pattern          │ Struct default / Named args │ Eliminates builder boilerplate│
└──────────────────────────┴─────────────────────────────┴───────────────────────────────┘
```

---

## 2. Stripping Over-Engineered Patterns: Step-by-Step

### 2.1 Strategy Pattern $\to$ Pure Functions / Lambdas

#### Anti-Pattern (OOP Strategy Explosion):
```python
# Before: 4 classes and an interface for simple sorting
class SortStrategy(ABC):
    @abstractmethod
    def sort(self, items: list[int]) -> list[int]: pass

class AscendingStrategy(SortStrategy):
    def sort(self, items: list[int]) -> list[int]: return sorted(items)

class DescendingStrategy(SortStrategy):
    def sort(self, items: list[int]) -> list[int]: return sorted(items, reverse=True)

class SorterContext:
    def __init__(self, strategy: SortStrategy): self._strategy = strategy
    def execute(self, items: list[int]) -> list[int]: return self._strategy.sort(items)
```

#### Simplified Pattern:
```python
# After: Direct higher-order function or key parameter
def sort_items(items: list[int], reverse: bool = False) -> list[int]:
    return sorted(items, reverse=reverse)
```

---

### 2.2 Visitor Pattern $\to$ Algebraic Data Types & Pattern Matching

#### Anti-Pattern (Double-Dispatch Boilerplate in C++ / Rust):
The Visitor pattern requires modifying every class in the hierarchy to add `accept(Visitor&)`, and every visitor to implement $N$ methods for $N$ subclasses.

#### Simplified Pattern (C++20 `std::variant` & `std::visit`):
```cpp
#include <variant>
#include <string>
#include <iostream>

struct Circle { double radius; };
struct Rectangle { double width, height; };
struct Triangle { double base, height; };

using Shape = std::variant<Circle, Rectangle, Triangle>;

double calculate_area(const Shape& shape) {
    return std::visit([](const auto& s) -> double {
        using T = std::decay_t<decltype(s)>;
        if constexpr (std::is_same_v<T, Circle>)
            return 3.1415926535 * s.radius * s.radius;
        else if constexpr (std::is_same_v<T, Rectangle>)
            return s.width * s.height;
        else if constexpr (std::is_same_v<T, Triangle>)
            return 0.5 * s.base * s.height;
    }, shape);
}
```

---

### 2.3 Factory Pattern $\to$ Concrete Constructor Functions

#### Anti-Pattern:
```csharp
// Before: 4 Factory interfaces and provider registrations
public interface IDatabaseConnectionFactory {
    IDatabaseConnection CreateConnection(string connectionString);
}
public class PostgresConnectionFactory : IDatabaseConnectionFactory {
    public IDatabaseConnection CreateConnection(string connectionString) => new PostgresConnection(connectionString);
}
```

#### Simplified Pattern:
```csharp
// After: Standalone static factory function or direct instantiation
public static class DatabaseConnection {
    public static PostgresConnection OpenPostgres(string connectionString) =>
        new PostgresConnection(connectionString);
}
```

---

## 3. Collapsing Deep Inheritance and Trait Hierarchies

Deep inheritance hierarchies ($>2$ levels) introduce the **Fragile Base Class Problem**, where changes in base classes silently alter the behaviors of deeply nested subclasses.

```
       [BaseEntity]
            │
      [AuditableEntity]
            │
      [TenantScopedEntity]
            │
      [SecuredTenantEntity]
            │
      [UserEntity] ───> Over 4 levels of hidden state & implicit lifecycle hooks!
```

### 3.1 Composition over Inheritance with Flat Structs

Replace multi-tier inheritance trees with flat structs containing explicit, reusable component records:

```rust
// Flattened Data Struct (Rust)
pub struct AuditMetadata {
    pub created_at: u64,
    pub created_by: String,
    pub updated_at: u64,
}

pub struct TenantContext {
    pub tenant_id: u64,
    pub region: String,
}

pub struct User {
    pub id: u64,
    pub username: String,
    pub email: String,
    pub audit: AuditMetadata,
    pub tenant: TenantContext,
}
```

### 3.2 Monomorphization Pruning: Generic Type Bounds

Over-parameterizing functions with deep trait bounds (`<T: AsRef<str> + Clone + Send + 'static>`) leads to code bloat, slow compiler monomorphization, and large binary sizes.

#### Pruning Rule:
- If a function is internal to an application binary (not a public library API), accept concrete slices (`&str`, `&[T]`, `std::span<T>`) rather than generic trait parameters.

---

## 4. Haskell Monad Transformer Stack Flattening

In Haskell, stacking multiple monad transformers (`ReaderT Config (StateT AppState (ExceptT AppError (WriterT [Log] IO))) a`) creates significant cognitive complexity and requires endless `liftIO` calls and complex typeclass resolution.

### The ReaderT Design Pattern (Snoyman Standard)

Collapse the transformer stack into a single unified environment record wrapped in `ReaderT Env IO`:

```haskell
-- Unified Application Environment
data Env = Env
    { envConfig :: !Config
    , envDbPool :: !ConnectionPool
    , envState  :: !(IORef AppState)
    , envLogger :: !(LogMessage -> IO ())
    }

-- Unified Monad Type
newtype App a = App { unApp :: ReaderT Env IO a }
    deriving (Functor, Applicative, Monad, MonadIO, MonadReader Env)

runApp :: Env -> App a -> IO a
runApp env app = runReaderT (unApp app) env
```

#### Advantages:
1. **Zero Monad Stack Lifting**: No `lift . lift . liftIO`.
2. **Deterministic State Lifetimes**: Explicit mutable references (`IORef`, `TVar`) clarify concurrency semantics.
3. **Rapid Compilation**: GHC compiles direct `ReaderT Env IO` code significantly faster than deeply nested transformer stacks.
