# Accidental Complexity Diagnostic Rubric

## 1. Executive Summary & Foundational Definitions

Every software system exhibits two distinct forms of complexity (Fred Brooks, *No Silver Bullet*, 1986):

1. **Essential Complexity**: Inherent to the problem domain itself. For example, computing a Fourier transform, resolving elliptic curve cryptography, parsing an arbitrary BNF grammar, or enforcing ACID distributed transactions.
2. **Accidental Complexity**: Incidental baggage introduced by engineering choices, premature abstractions, speculative flexibility, deep inheritance trees, convoluted type acrobatics, and design-pattern over-engineering.

```
Total System Complexity = Essential Domain Complexity + Accidental Engineering Complexity
                                (Minimize / Retain)              (Systematically Strip)
```

The goal of the **Code Simplification Skill** is the systematic diagnosis and excision of accidental complexity, driving systems toward minimal cognitive overhead, maximal maintainability, and optimal execution performance.

---

## 2. Quantitative Complexity Metrics

To objectively detect accidental complexity, four complementary quantitative metrics are evaluated:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        QUANTITATIVE COMPLEXITY METRIC SUITE                            │
├──────────────────────────┬──────────────────────────┬──────────────────────────────────┤
│ Metric                   │ Calculation Basis        │ Simplification Threshold         │
├──────────────────────────┼──────────────────────────┼──────────────────────────────────┤
│ McCabe Cyclomatic (CC)   │ $V(G) = E - N + 2P$      │ Function CC $\le 10$ (Target $\le 5$) │
│ Sonar Cognitive (CogC)   │ Nesting-weighted breaks  │ Function CogC $\le 15$ (Target $\le 8$)│
│ Maximum AST Nesting      │ Tree control-depth level │ Depth $\le 3$ (Target $\le 2$)   │
│ Semantic Density / LOC   │ Non-boilerplate lines    │ Signal Ratio $\ge 70\%$          │
└──────────────────────────┴──────────────────────────┴──────────────────────────────────┘
```

### 2.1 Cyclomatic Complexity vs. Cognitive Complexity

- **Cyclomatic Complexity ($V(G)$)** measures the number of linearly independent execution paths through a program's control flow graph. While useful for measuring minimum test case count, it treats a flat switch of 20 cases identically to 20 deeply nested `if-else` blocks.
- **Cognitive Complexity** measures how difficult the control flow is for a human engineer to understand. It assigns nesting penalties: an `if` at level 1 adds $+1$, but an `if` nested at level 4 adds $+4$ to cognitive load.

#### Mathematical Formulation of Cognitive Complexity:
$$\text{Cognitive Score} = \sum_{i=1}^{B} (1 + \text{NestingLevel}(i))$$
Where $B$ is the set of control flow branching constructs (`if`, `while`, `for`, `catch`, `match_case_guard`).

---

## 3. The Accidental Complexity Smells & Diagnostic Rubric

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                          ACCIDENTAL COMPLEXITY TAXONOMY                               │
├──────────────────────────┬────────────────────────────────────────────────────────────┤
│ Smell Category           │ Structural Manifestation & Detection Vector                │
├──────────────────────────┼────────────────────────────────────────────────────────────┤
│ 1. Premature Abstraction │ Single-implementation interfaces, speculative generic type │
│                          │ parameters (`<T, U, V>`), abstract base classes with 1 child│
│ 2. Russian Nesting Dolls │ Over-wrapped types: `Option<Arc<Mutex<Box<dyn Service>>>>` │
│ 3. Speculative YAGNI     │ Extension points, pluggable drivers, or unused hook methods│
│                          │ designed for hypothetical future requirements.             │
│ 4. Layer-Cake Indirection│ Request travels through 6 pass-through classes that merely │
│                          │ forward arguments: Controller -> Facade -> Service ->      │
│                          │ Manager -> Handler -> Repository -> DAO -> Entity.         │
│ 5. Type-Level Acrobatics │ Complex template metaprogramming, GADTs, or type families  │
│                          │ where simple enum variants or records suffice.            │
└──────────────────────────┴────────────────────────────────────────────────────────────┘
```

### 3.1 Premature Abstraction & Single-Implementation Interfaces

#### The Anti-Pattern:
Creating an interface `IUserService` and an implementation `UserServiceImpl` when only a single implementation will ever exist in the codebase. This doubles symbol count, impairs IDE navigation, slows compilation, and introduces unnecessary indirection.

```java
// Anti-Pattern: 1-to-1 Interface-to-Implementation Pair
public interface IUserService {
    User findUserById(UUID id);
}

public class UserServiceImpl implements IUserService {
    private final UserRepository repo;
    public UserServiceImpl(UserRepository repo) { this.repo = repo; }
    @Override
    public User findUserById(UUID id) { return repo.get(id); }
}
```

#### Diagnostic Rule:
> Prefer concrete code. Extract an abstraction when a current boundary, invariant or simplification justifies it; there is no implementation-count quota.

#### Refactored Simplification:
```java
// Simplified: Direct concrete domain struct / class
public class UserService {
    private final UserRepository repo;
    public UserService(UserRepository repo) { this.repo = repo; }
    public User findUserById(UUID id) { return repo.get(id); }
}
```

---

### 3.2 Russian Nesting Dolls: Wrapper Type Stripping

#### The Anti-Pattern (Rust / C++):
Excessive wrapping of types across architectural layers, leading to unreadable signatures, double pointer indirection, and borrow-checker friction:
```rust
// Anti-Pattern: 5 layers of wrapping for a configuration cache
pub struct CacheManager {
    inner: Arc<Mutex<Option<Box<HashMap<String, Arc<RwLock<ConfigRecord>>>>>>>,
}
```

#### Simplification Strategy:
1. **Flatten Ownership**: Store values directly in the container without extra `Box`.
2. **Coalesce Synchronization**: Protect the collection at the coarsest necessary granularity rather than nesting lock inside lock.
3. **Use Concrete Types**:
```rust
// Simplified: Direct synchronized map
pub struct CacheManager {
    inner: RwLock<HashMap<String, ConfigRecord>>,
}
```

---

### 3.3 Layer-Cake Indirection (The 7-Hop Forwarding Trap)

When investigating a feature or bug, trace the execution call graph. Count the number of **non-transforming hops**—functions whose sole purpose is to call another function with identical arguments:

```
[HTTP Handler] ────(hop 1)───> [UserFacade]
                                   │ (hop 2)
                                   ▼
                              [UserService]
                                   │ (hop 3)
                                   ▼
                             [UserManager]
                                   │ (hop 4)
                                   ▼
                            [UserRepository]
                                   │ (hop 5)
                                   ▼
                            [UserDAO]
                                   │ (hop 6)
                                   ▼
                            [SQL Database Execution]
```

#### Diagnostic Threshold:
If more than **2 intermediate layers** perform zero validation, mutation, caching, or business logic transformation, collapse them into a direct domain service.

---

## 4. Complexity Diagnostic Checklist

Before writing new abstractions or refactoring existing code, evaluate against this 6-question diagnostic checklist:

1. **Concrete Reusability**: Are there at least 3 genuine production call sites that require this generic type or polymorphic interface today?
2. **Cognitive Hop Count**: Can a new engineer understand the primary data flow without jumping through more than 2 files?
3. **Nesting Depth**: Does every function maintain an AST indentation depth $\le 3$?
4. **Locality of Behavior**: Is related business logic located together in a single module rather than scattered across 5 design-pattern classes?
5. **Zero-Cost Abstraction Audit**: Does this abstraction incur runtime heap allocation, dynamic dispatch, or cache line misses?
6. **YAGNI Verification**: Does this code satisfy a requirement from current sprint tickets, or is it speculative scaffolding for hypothetical future features?
