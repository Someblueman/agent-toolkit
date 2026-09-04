---
name: haskell
description: Implement, review, debug, and test Haskell packages and applications. Use for Haskell source, Cabal or Stack, algebraic APIs and laws, type-level code, evaluation and strictness, effects and concurrency, parsers, FFI, performance, dependencies, or Haskell CI. Do not use for non-Haskell work or generic project management.
---

# Haskell Engineering

Make the smallest change that is correct for the repository's actual contract. Make invariants, algebraic assumptions, evaluation depth, effects, and failure behavior explicit. Distinguish compiler evidence, executable tests, and mathematical proof.

## Repository Workflow

1. Inspect instructions, worktree state, the surrounding diff, Cabal/Stack/Hpack/Nix files, compiler and resolver pins, CI, formatting and HLint config, custom Prelude, language edition, warning policy, exposed components, tests, and benchmarks.
2. Classify the request. For review or diagnosis, gather evidence and report without editing. For implementation, preserve established semantics unless the request changes them.
3. Write down the relevant contract: accepted inputs, invariants, equality or normalization, laws, failure modes, evaluation depth, effects, concurrency, resource ownership, public instances, and compatibility constraints.
4. Identify the authoritative build path from repository evidence. In mixed Cabal/Stack/Nix setups, inspect CI and contributor docs; do not guess from file presence.
5. Load only the reference pages relevant to the risk areas below, then implement in small reviewable steps.

## Cross-Cutting Rules

- Parse and validate at boundaries. Use sums, products, `newtype`, smart constructors, and precise containers to encode useful invariants without turning routine domain logic into unnecessary type-level machinery.
- Prefer total public interfaces, but do not equate exhaustive patterns with totality: divergence, bottoms, pure exceptions, and delayed failures under laziness remain possible.
- For algebraic code, state the carrier, equality, normalization, partial operations, and laws. A typeclass instance or passing property suite is evidence, not a proof.
- Treat instances and deriving choices as public semantics. Check coherence, laws, representation dependence, constructor ordering, and `Coercible` roles.
- Make resource lifetime, exception behavior, cancellation, concurrency bounds, and evaluation depth visible at API boundaries.
- Treat `unsafePerformIO`, `unsafeCoerce`, FFI, rewrite rules, and manual representation code as proof boundaries. Isolate them and document the invariant that makes each use sound.
- Make performance changes only against a representative baseline with the demanded result forced to a stated depth.

## Codebase Architecture & Namespace Boundaries

- Use explicit exports at public and invariant-enforcing boundaries; preserve reasonable conventions for executable and test modules. Export lists control API visibility, not a blanket guarantee about optimization.
- Preserve the repository's module structure. Separate pure logic from effects when that clarifies dependencies, without imposing a three-tier namespace. Review large modules for cohesion rather than splitting mechanically.
- **`Package.Internal.*` Isolation Protocol**: Isolate unvalidated data constructors, unchecked internal primitives, and white-box test escape hatches in `Package.Internal.*` or `Package.Foo.Internal` submodules. Public API modules (`Package` or `Package.Foo`) must export only opaque types, smart constructors, and safe operations. Mark internal modules as `other-modules` in `.cabal` or document them with explicit Haddock warnings (`Unstable Internal API`). Standard application code and external library consumers must never import `.Internal` modules.

## Pragmatic Anti-Abstraction & Single-Path Execution

- Prefer concrete code; introduce an abstraction when it simplifies a current requirement or expresses a necessary boundary or invariant.
- **Concrete Records over Monad Transformer / Effect Bloat**: Prefer `ReaderT Env IO a` (or plain functions taking a concrete `Env` record of functions/handles) over deep custom transformer stacks (`ReaderT C (ExceptT E (StateT S IO))`) or heavy extensible effect libraries (Polysemy, Freer, Eff).
- **Single-Path Codecs & Clean Replacement**: When updating data models, serialization schemas, or function signatures, perform a clean in-place replacement and atomically update all call sites, internal usages, and tests in the same change wave.
  - *Ban Zombie Decoders / Dual-Format Fallbacks*: Never use `<|>` in `FromJSON` or parser combinators to parse obsolete legacy formats alongside new formats unless published, durable-data or cross-process contracts require compatibility or migration.
  - *Ban Shim Multiplication*: Do not retain deprecated functions or aliases as pass-through forwarding wrappers around new implementations.
  - *Ban Preemptive Deprecation Staging*: Replace definitions cleanly instead of introducing `{-# DEPRECATED #-}` pragmas when immediate refactoring is feasible.
  - *Ban Paranoid Dual-Writing & Ghost Code*: Never write to both old and new stores/fields concurrently during refactors. Never leave commented-out implementations, unused fallback branches, or dead code in `_legacy` files.

## Verification Ladder

Match verification effort directly to the scope and risk of the change:

- **Tier 1 (Fast-Path)** for localized bug fixes, helper additions, internal refactors, documentation, or config changes:
  - Ultra-fast typechecking without code generation:
    - `ghc -fno-code src/Package/Core/Module.hs`
    - `cabal build --ghc-options="-fno-code"`
  - Targeted component build:
    - `cabal build lib:<pkg-name>` or `cabal build exe:<exe-name>`
  - Targeted test execution by pattern or test name (Tasty / Hspec):
    - `cabal test <pkg>:<suite> --test-options="-m \"<pattern>\""`
    - Hspec: `cabal test <pkg>:<suite> --test-options='--match pattern'`; Tasty: `cabal test <pkg>:<suite> --test-options='-p pattern'`. Confirm the selected runner with its `--help`.
    - `stack test <pkg>:<suite> --test-arguments="-m \"<pattern>\""`
- **Tier 2 (Full Verification)** for core architectural modifications, cryptographic primitives, concurrency/STM invariants, durable data schema migrations, or public library published APIs:
  - Full workspace build and test: `cabal build all && cabal test all` (or `stack test`)
  - Run the repository formatter on changed files; treat HLint as advisory unless repository policy makes it authoritative.
  - Build with the repository warning policy (`-Wall -Werror -Wmissing-export-lists`) and exercise success, failure, boundary, law, and evaluation behavior.
  - Packaging and documentation: `cabal haddock all && cabal check && cabal sdist`
  - Fallback quality script: `scripts/haskell_quality_check.sh --strict` (in CI or acceptance work). Report exact commands and scope.

## Reference Routing

- Load `references/types-api.md` for domain modeling, explicit export lists, repository module boundaries, `Internal` isolation, totality, failures, and concrete-first design.
- Load `references/boundaries-ffi.md` for text/bytes, parsers, single-path serialization (no zombie decoders or shims), FFI, and unsafe operations.
- Load `references/tooling-ci.md` for Cabal/Stack/Hpack/Nix, warnings (`-Wmissing-export-lists`), Fast-Path command cookbook, packaging, and CI.
- Load `references/advanced-types.md` for Concrete-First Design on typeclasses, GADTs, type families, constraints, deriving, roles, and compile-time tests.
- Load `references/algebraic-laws.md` for algebra, numeric domains, instances, normalization, and property testing.
- Load `references/evaluation-performance.md` for laziness, WHNF/NF, strictness, profiling, Core, and optimization.
- Load `references/effects-concurrency.md` for exceptions, resources, asynchronous exceptions, STM, structured concurrency, and streaming.
- Load `references/source-map.md` when auditing or refreshing this skill's authority.

## Maintenance

When changing this skill, keep prescriptions tied to `references/source-map.md` and validate the package with the skill-creator checks. Prefer durable semantic guidance over version-specific fashion.
