# Haskell Skill Source Map

Use these sources to audit or refresh prescriptions. Prefer current upstream documentation and repository-local contracts over cached examples or fashion. Re-check version-sensitive claims before changing the skill.

## Language, Types, and Runtime

- [GHC extensions control](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/exts/control.html): language editions and explicit extension control.
- [GHC GADTs](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/exts/gadt.html): constructor evidence, refinement, and pattern matching.
- [GHC type families](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/exts/type_families.html): open/closed families, reduction, arity, injectivity, and compatibility.
- [GHC roles](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/exts/roles.html): nominal, representational, and phantom roles and annotations.
- [GHC deriving strategies](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/exts/deriving_strategies.html): `stock`, `newtype`, `anyclass`, and `via` selection.
- [GHC strictness extensions](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/exts/strict.html): bang patterns, strict bindings/fields, `Strict`, and `StrictData`.
- [`Control.Exception`](https://ghc.gitlab.haskell.org/ghc/doc/libraries/base-4.22.0.0-inplace/Control-Exception.html): evaluation, bracketing, masking, interruptibility, and asynchronous exceptions. Follow the supported `base` version when working in a repository.
- [`GHC.IO.Unsafe`](https://ghc.gitlab.haskell.org/ghc/doc/libraries/base-4.22.0.0-inplace/GHC-IO-Unsafe.html): optimizer, duplication, ordering, and type-safety hazards around unsafe I/O. Follow the repository's `base` version.
- [`Control.DeepSeq`](https://hackage.haskell.org/package/deepseq/docs/Control-DeepSeq.html): NF, `NFData`, `deepseq`, and `force`.
- [GHC STM](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/exts/stm.html): transaction semantics and retry behavior.
- [`async`](https://hackage.haskell.org/package/async/docs/Control-Concurrent-Async.html): scoped child lifetime, exception propagation, cancellation, and structured combinators.
- [GHC FFI](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/exts/ffi.html): calling conventions, safety annotations, marshaling, and callbacks.
- [GHC profiling](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/profiling.html): time/allocation, cost centres, heap profiling, and ticky/eventlog routes.

## Algebra and Testing

- [`Eq`](https://hackage.haskell.org/package/base/docs/Data-Eq.html), [`Ord`](https://hackage.haskell.org/package/base/docs/Data-Ord.html), [`Semigroup`](https://hackage.haskell.org/package/base/docs/Data-Semigroup.html), and [`Monoid`](https://hackage.haskell.org/package/base/docs/Data-Monoid.html): current class contracts and documented customary laws.
- [GHC numeric infelicities](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/bugs.html): implementation-specific overflow behavior and other semantic caveats that must not be generalized to all numeric domains.
- [`Functor`](https://hackage.haskell.org/package/base/docs/Data-Functor.html), [`Applicative`](https://hackage.haskell.org/package/base/docs/Control-Applicative.html), and [`Monad`](https://hackage.haskell.org/package/base/docs/Control-Monad.html): class methods and laws.
- [`Foldable`](https://hackage.haskell.org/package/base/docs/Data-Foldable.html) and [`Traversable`](https://hackage.haskell.org/package/base/docs/Data-Traversable.html): folds/traversals and consistency laws.
- [QuickCheck](https://hackage.haskell.org/package/QuickCheck/docs/Test-QuickCheck.html): generation, shrinking, classification, coverage, replay, and `checkCoverage`.
- [SmallCheck](https://hackage.haskell.org/package/smallcheck): bounded exhaustive testing.
- [Tasty](https://hackage.haskell.org/package/tasty): composing test providers and test-tree execution.

## Build, Packaging, and Documentation

- [GHC warnings](https://ghc.gitlab.haskell.org/ghc/doc/users_guide/using-warnings.html): the actual contents of warning groups and targeted warning flags.
- [Cabal commands](https://cabal.readthedocs.io/en/stable/cabal-commands.html): `build`, `test`, `haddock`, `check`, and `sdist` behavior.
- [Cabal package description](https://cabal.readthedocs.io/en/stable/cabal-package-description-file.html): components, modules, metadata, common stanzas, language, options, and package content.
- [Stack project configuration](https://docs.haskellstack.org/en/stable/configure/yaml/project/): resolver/snapshot, project packages, and Hpack inputs.
- [Hpack](https://github.com/sol/hpack): `package.yaml` generation and committed/generated Cabal behavior.
- [Haskell Language Server configuration](https://haskell-language-server.readthedocs.io/en/latest/configuration.html): cradle discovery and editor configuration.
- [Fourmolu](https://hackage.haskell.org/package/fourmolu) and [Ormolu](https://hackage.haskell.org/package/ormolu): formatter modes and configuration.
- [HLint](https://hackage.haskell.org/package/hlint): lint behavior and configuration.
- [Haddock markup](https://haskell-haddock.readthedocs.io/latest/markup.html): public documentation syntax.
- [Haskell Package Versioning Policy](https://pvp.haskell.org/): public API versioning and dependency-bound policy.

## Secondary Design Sources

Use these for design rationale, not as language/tool authority:

- [Parse, don't validate](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/): boundary parsing and valid internal representations.
- [Kowainik Haskell style guide](https://kowainik.github.io/posts/2019-02-06-style-guide): readable declarations, signatures, and import/export tradeoffs.

## Refresh Rules

- Re-open the relevant current documentation before adding a version-specific command, extension claim, warning membership, or runtime guarantee.
- Prefer repository policy when it is explicit and internally consistent; report conflicts rather than silently replacing it.
- Do not turn one library's conventions into universal algebraic or architectural rules.
- Keep proof claims separate from compiler acceptance, finite tests, and randomized evidence.
