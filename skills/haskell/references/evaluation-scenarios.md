# Haskell Skill Evaluation Scenarios

Use these prompts to test whether revisions produce sound judgment rather than keyword compliance. A good response states assumptions, selects only relevant references, distinguishes evidence levels, and proposes proportionate verification.

## 1. Numeric Abstraction

“Generalize a polynomial normalization algorithm from `Integer` to `Num a`; the existing QuickCheck properties pass for `Int`.”

Expected judgment: refuse to infer ring laws from `Num`; identify equality, overflow, zero/canonical form, exponent/domain constraints, and the concrete carriers to support; preserve an honest test/proof ceiling.

## 1a. Quotient and Partial Division

“Represent rational functions with several equivalent syntax trees, expose representation-derived `Eq`/`Ord`, normalize after operations, and make division throw on a zero denominator.”

Expected judgment: define denotational equality and canonical form; require termination, idempotence, and denotation preservation of normalization; prove/test operation congruence and invariant preconditions; align equality/order/hash/serialization; and choose an explicit restricted or typed-failure division API with laws scoped to its valid domain.

## 2. Vacuous Law Test

“Our group inverse property uses `suchThat` to exclude zero and QuickCheck reports 100 successes.”

Expected judgment: inspect generator acceptance and distribution, generate valid values directly, preserve invariants during shrinking, require coverage where meaningful, add boundary/model or finite tests, and avoid claiming proof.

## 3. Abstract Units and Roles

“Constructors for `Quantity unit` are hidden, so users cannot mix metres and seconds. Add `GeneralizedNewtypeDeriving`.”

Expected judgment: inspect inferred roles and `Coercible`; explain why constructor hiding may not protect a phantom/representational unit parameter; add a role annotation or redesign; add compile-fail coercion tests and law tests.

Also reject blindly derived numeric/order instances: role safety does not establish that addition, multiplication, division, or result-unit indices implement the intended unit algebra.

## 4. Hidden Bottom

“This function is total because `-Wall -Werror` passes and every pattern is covered. The test only calls `length` on the returned list.”

Expected judgment: separate pattern completeness from divergence, pure exceptions, and bottoms; determine the promised observation depth; force suitable values and test boundaries without indiscriminately forcing productive infinite structures.

## 5. Resource and Pure Exception

“Read a lazy file under `withFile`, return the parsed tree, and catch parser exceptions outside the bracket.”

Expected judgment: keep consumption/evaluation within the resource scope, specify WHNF/NF needed, prefer explicit streaming or strict input as appropriate, and make parse failures typed when predictable.

Acceptance oracle: demonstrate that every permitted post-bracket observation succeeds, or reject/redesign the escaping value.

## 6. Cancellation-Safe Worker Pool

“Use `forkIO` for one thread per input and catch `SomeException` so jobs keep running.”

Expected judgment: require bounded structured concurrency, observed child failures, cancellation semantics, exception rethrow/preservation, resource cleanup, shutdown ordering, and deterministic cancellation/failure tests.

Acceptance oracle: all workers and owned resources either terminate within the specified shutdown deadline, or the documented stuck-worker fallback is observed and satisfies its stated safety and invariant policy.

## 7. STM Side Effect

“Inside `atomically`, update a `TVar` and append an audit line to a file; use `retry` if the queue is full.”

Expected judgment: reject external `IO` in a retryable transaction, keep the invariant-changing transition atomic, move audit delivery to an explicit outbox/worker design, bound queues, and test retry/wakeup behavior.

Acceptance oracle: transaction retries cannot duplicate or lose an audit record, and wakeups/starvation match the declared protocol.

## 8. Network Parser and Canonical Encoding

“The parser succeeds on a prefix, ignores leftovers, uses `Double` for amounts, and `encode . decode` round-trips our fixtures.”

Expected judgment: establish full/incremental consumption, length/depth limits, exact numeric semantics, canonicalization, corrupt/trailing/ambiguous inputs, independent vectors, and version policy.

## 9. FFI Fast Path

“Mark a blocking C call `unsafe` for speed, marshal a C struct with `Storable`, and use `unsafePerformIO` to cache the handle.”

Expected judgment: verify ABI/layout/ownership, choose FFI safety from blocking/callback behavior, design deterministic resource lifetime, isolate any unsafe boundary with a representation/referential-transparency argument, and test supported platforms and optimization modes.

Acceptance oracle: unrelated Haskell work progresses during a blocking foreign call; cancellation matches the declared contract; optimized/unoptimized and concurrent first evaluation do not duplicate or reorder hidden effects. A live cached handle behind `unsafePerformIO` is rejected.

## 10. Ambiguous Project Tooling

“The repository has `stack.yaml`, `cabal.project`, three nested packages, and `package.yaml`. Run the quality script and declare it green.”

Expected judgment: inspect CI/docs for authority or require `--tool`; do not assume Cabal because `.cabal` exists; cover the package/component graph; treat skipped/ambiguous tools as incomplete under strict mode.

## 11. Library Release

“All unit tests pass locally; publish the package.”

Expected judgment: verify warnings, public docs, properties/compile tests as relevant, `cabal check`, source distribution contents, clean unpacked build/test/docs, exposed/other/autogen modules, supported GHC/dependency bounds, metadata, and versioning.

## 12. Performance Claim

“Adding bangs made the benchmark twice as fast.”

Expected judgment: confirm equivalent demanded work and optimized flags, distinguish WHNF/NF, inspect allocation/residency and variability, run correctness tests, assess changed exception/termination semantics, and scope the claim to the measured workload.

## 13. God Module and Hierarchical Namespace Boundary

“Our `App.hs` module has grown to 8,500 lines containing domain types, database queries, HTTP handlers, CLI options, and unvalidated helper functions without an explicit export list. Add a new feature to it.”

Expected judgment: refuse to add features directly into the 8k-line God module; decompose into a 3-tier hierarchical architecture (`Package.Core.*` pure domain models and invariants, `Package.Storage.*` / `Package.Network.*` database and HTTP adapters, `Package.CLI.*` application wiring); isolate raw constructors and test hooks into `Package.Internal.*`; add mandatory explicit export lists across all modules; enforce strict unidirectional imports (CLI -> Storage -> Core).

## 14. Rule of Three and Monad Stack Bloat

“Abstract over our single SQLite database backend by introducing a `MonadUserRepository m` typeclass with functional dependencies, and wrap our application handlers in a 5-layer transformer stack: `ReaderT Config (ExceptT AppError (StateT AppState (LoggingT IO))) a`.”

Expected judgment: reject the speculative `MonadUserRepository` typeclass as a violation of the Rule of Three (there is only one backend); reject the 5-layer transformer stack bloat; simplify to concrete records of functions (`data UserRepository = UserRepository { ... }`) and a single `ReaderT Env IO a` (or plain IO with explicit `Env`); preserve straightforward error handling with `Either` or standard `catch`/`bracket`.

## 15. Single-Path JSON Codec Refactor and Zombie Decoders

“Refactor our Aeson `User` codec to rename the field `user_email` to `email`. To avoid breaking old payloads, add `parseNew <|> parseOld` in `FromJSON`, and keep `oldUserFunc` as a deprecated forwarding wrapper.”

Expected judgment: reject the `<|>` zombie fallback decoder and shim multiplication (violating single-path execution policy); perform a clean in-place replacement of the `FromJSON` and `ToJSON` instances; atomically update all call sites, internal usages, and test fixtures in the same change wave; delete obsolete fallback branches and deprecated wrapper scaffolding.

## 16. Tier 1 Fast-Path Test Execution

“We fixed a localized bug in `Package.Core.Tax.calculateTotal`. Before submitting, run the full multi-package build, entire integration test suite, and Haddock generation.”

Expected judgment: apply tiered verification by matching verification effort to change scope; use Tier 1 Fast-Path for localized fixes: ultra-fast typechecking via `ghc -fno-code src/Package/Core/Tax.hs` or `cabal build --ghc-options="-fno-code"`, targeted component build `cabal build lib:mypkg`, and targeted test pattern filter `cabal test mypkg:unit-tests --test-options="-m \"Package.Core.Tax\""`; reserve Tier 2 full verification (`cabal build all && cabal test all && cabal haddock all`) for CI or architectural/release acceptance.
