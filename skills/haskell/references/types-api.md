# Types, Totality, and Public APIs

Use this page when modeling a domain, reviewing public functions, designing failures, or documenting a library.

## Start at the Semantic Boundary

- Determine whether the surface is a stable library API, an internal application boundary, or a prototype. Spend abstraction budget accordingly.
- Parse and validate untrusted values at the edge. Keep core values valid by construction when the invariant is important and enforceable.
- Prefer ordinary sums and products, `newtype`, precise containers such as `NonEmpty`, and smart constructors before advanced type machinery.
- Hide constructors only when doing so actually protects an invariant. Export the observations and eliminators callers need.
- Do not encode a property in a type if every useful operation immediately escapes or reconstructs unchecked values.

## Totality Is More Than Pattern Coverage

| Risk | Typical evidence | Preferred response |
| --- | --- | --- |
| Incomplete pattern | GHC warnings and constructor tests | Cover the cases or make impossibility explicit in the input type |
| Partial library function | Review plus failure tests | Return a typed alternative or accept an input type that proves the precondition |
| Pure exception | Force the promised result in tests | Remove it, return a typed failure, or deliberately contain it at an `IO` boundary |
| Nontermination | Structural argument, fuel, or termination reasoning | Make progress evident and test time/size boundaries |
| Hidden bottom under laziness | Force the result to the API's promised depth | Change the contract or ensure construction cannot hide failure |

Avoid casual use of `head`, `tail`, `init`, `last`, `fromJust`, partial record selectors, `read`, `undefined`, and `error`. A warning-clean definition can still diverge or throw. Equational reasoning normally assumes the relevant values are total; `seq`, exceptions, and bottoms can distinguish definitions that agree on total values.

Assertions are useful diagnostics but may be disabled and are not invariant enforcement. A private partial operation can be justified when its precondition is local, mechanically maintained, documented beside the call, and directly tested.

## Failure Design

- Use `Maybe` when absence is the only useful information.
- Use `Either` or a domain error sum when callers need to distinguish failures.
- Use an accumulating validation abstraction only when errors are independent and accumulation is part of the contract.
- Keep pure, predictable domain failures typed. Reserve exceptions primarily for `IO`, resource failures, cancellation, and violations that cannot be handled locally.
- Make errors precise enough for the next decision without leaking unstable implementation details.
- Document whether `IO` functions may block, allocate external resources, throw synchronous exceptions, or be interrupted.
- Avoid a generic effect abstraction when the project has one implementation and no demonstrated need for substitution.

## Module and Instance Boundaries

- **Mandatory Explicit Export Lists on ALL Modules**: Every module in the codebase—libraries, executables, test suites, internal helpers, and CLI entry points—must have an explicit export list (`module Package.Foo (Type(..), func, ...) where`). Implicit exports leak internal implementation details, defeat dead-code elimination, break encapsulation, and risk exposing unvalidated data constructors.
- **3-Tier Hierarchical Namespace Architecture**:
  - *Layer 1: Core Domain (`Package.Core.*` / `Package.Domain.*`)*: Houses pure domain types, invariant-enforcing smart constructors, pure business logic, and algebraic models. Zero external I/O, zero database libraries, zero HTTP/network dependencies.
  - *Layer 2: Storage & Network Adapters (`Package.Storage.*`, `Package.Network.*`)*: Houses database access (PostgreSQL, SQLite, Redis), HTTP client/server adapters, file system I/O, and external wire format mappings.
  - *Layer 3: Application Wiring & CLI (`Package.CLI.*`, `Package.App.*`, `Main.hs`)*: Houses CLI argument parsing (`optparse-applicative`), configuration loading, adapter instantiation, dependency wiring, and top-level execution loops.
  - *Unidirectional Layering Rule*: Imports flow unidirectionally from outer layers to inner layers (`CLI` -> `Storage` -> `Core`). Inner domain modules must never import outer adapters or application modules.
  - *God Module Decomposition*: Decompose monolithic modules exceeding ~500–1000 lines into focused, cohesive submodules following this hierarchical structure.
- **`Package.Internal.*` Isolation Protocol**:
  - Place raw data constructors, unchecked helper functions, and test-only escape hatches into `Package.Internal.*` or `Package.Foo.Internal` submodules.
  - Public facade modules (`Package` or `Package.Foo`) export only opaque types, smart constructors, and validated operations.
  - Mark `.Internal` modules as `other-modules` in `.cabal` or document them with prominent Haddock warnings (`Unstable Internal API`). Standard application code and external library users must never import `.Internal` modules.
- **Signatures and Imports**: Give all public and nontrivial top-level bindings explicit type signatures. Prefer explicit or qualified imports to make dependencies visible and prevent symbol collisions.
- **Instances**: Keep a class and its canonical instances near the type or class. Orphan instances represent ambient global behavior and require exceptional justification. Treat `Eq`, `Ord`, `Show`, numeric, serialization, and collection instances as API decisions, not boilerplate.

## Anti-Abstraction: Concrete-First Design

- **Rule of Three for Typeclasses**: Define concrete data types and functions first. Do NOT introduce a custom typeclass (`class MonadUserRepo m`, `class StorageBackend s`) unless there are at least 3 distinct concrete implementations in the active repository or an established standard contract (`Aeson.ToJSON`, `Eq`, `Ord`, `Semigroup`) requires it.
- **Records of Functions over Typeclasses**: When dependency injection or interface abstraction is genuinely needed for testing or swapping adapters, prefer a plain record of functions:
  ```haskell
  data UserRepo = UserRepo
    { findUser :: UserId -> IO (Maybe User)
    , saveUser :: User -> IO ()
    }
  ```
  Passing records of functions eliminates complex typeclass dictionaries, multi-parameter functional dependencies, and existential type plumbing.
- **Monad Simplicity (`ReaderT Env IO`)**: For application architecture, prefer a concrete `ReaderT Env IO a` (or plain functions taking an explicit `Env` record of dependencies/handles) over deep custom transformer stacks (`ReaderT C (ExceptT E (StateT S IO))`) or heavy extensible effect frameworks (Polysemy, Freer, Eff). Concrete `ReaderT Env IO` provides clear stack traces, predictable exception handling via `bracket` and `catch`, and zero type-level debugging friction.

## Public Haddock Contract

For nontrivial public types and functions, document what a caller cannot safely infer from the signature:

- valid inputs and construction invariants;
- equality, ordering, normalization, and algebraic laws;
- totality and failure behavior;
- strictness or demanded evaluation depth when observable;
- units, encodings, resource lifetime, blocking, and cancellation;
- meaningful complexity guarantees;
- a small example that compiles under the supported toolchain.

Do not claim a function is “safe,” “total,” or “lawful” without stating the domain and observations under which that claim holds.
