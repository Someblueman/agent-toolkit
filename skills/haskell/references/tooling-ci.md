# Tooling, Packaging, Dependencies, and CI

Use this page when selecting commands, configuring warnings or extensions, preparing a release, or reviewing CI evidence.

## Establish Build Authority

- Inspect `cabal.project`, `.cabal` files, `stack.yaml`, `package.yaml`, Nix/flake files, CI, contributor docs, and pinned toolchain files.
- Cabal metadata can coexist with a Stack-managed workflow. A `package.yaml` can be the editable source for generated Cabal metadata. Do not choose or rewrite one merely from file presence.
- In a mixed setup, follow the path demonstrated by CI/docs or ask for an explicit choice. Record the compiler/resolver and important project flags.
- Build the actual package/component graph. Compiling a convenient module or a monolithic executable does not prove an exposed library component builds.

## Language and Warnings

- Prefer the repository's explicit language edition, then enable additional extensions narrowly and document semantic ones.
- Preserve the supported compiler range before adopting syntax, extension behavior, or solver features.
- Treat `-Wall` as a baseline. Add `-Wmissing-export-lists` (to mandate explicit export lists across all modules) and `-Wmissing-import-lists` (or qualified imports) along with context-relevant warnings for incomplete patterns, missing signatures, missing home modules, orphans, type defaults, unsafe behavior, and compatibility.
- Do not rely on deferred type errors or deferred out-of-scope variables in acceptance builds.
- Use `-Werror` where repository policy requires warning-clean code, but keep compiler-version matrices maintainable by separating selected warning policy from newly introduced upstream warnings when appropriate.
- A suppression should be local and explain why the warning is a false positive or an accepted invariant.

## Formatting, HLint, and HLS

- Use the configured formatter and version. Do not alternate Fourmolu and Ormolu or format generated/vendor files.
- Format only the intended tracked or nonignored source set; review formatter diffs before accepting them.
- HLint suggestions are semantic proposals, not guaranteed improvements. Use project config and review each nontrivial rewrite, especially in strictness-, fusion-, or law-sensitive code.
- Treat HLS as editor support. Add `hie.yaml` only when cradle discovery is actually wrong and the file reflects authoritative components.

## Tiered Verification & Fast-Path Command Cookbook

Align verification effort with the change scope (Tier 1 Fast-Path for localized bug fixes/refactors; Tier 2 Full Verification for architectural/data/crypto/release changes):

### Tier 1 (Fast-Path) Commands

```bash
# Ultra-fast typechecking without code generation
ghc -fno-code src/Package/Core/Module.hs
cabal build --ghc-options="-fno-code"

# Targeted component build
cabal build lib:<pkg-name>
cabal build exe:<exe-name>
stack build <pkg-name>:lib
stack build <pkg-name>:test:<suite-name> --no-run-tests

# Targeted test filtering by pattern / test name (Tasty & Hspec)
cabal test <pkg-name>:<suite-name> --test-options="-m \"<pattern>\""
cabal test <pkg-name>:<suite-name> --test-options="--match=\"<pattern>\""
stack test <pkg-name>:<suite-name> --test-arguments="-m \"<pattern>\""
```

### Tier 2 (Full Verification) by Project Type

For Cabal projects, use the relevant subset and widen for release work:

```text
cabal build all
cabal test all
cabal haddock all
cabal check
cabal sdist
```

- Run `cabal check` for each package whose `.cabal` file is being released.
- Inspect or list the source distribution and build/test/docs from a clean unpacked archive when package contents matter.
- Use component selectors for focused work, then `all` for the affected package set.

For Stack projects, use the pinned resolver and project package set:

```text
stack build --test --no-run-tests
stack test
stack haddock
```

If Hpack is authoritative, edit `package.yaml` and regenerate through the repository's normal Stack/Hpack workflow. Review the generated Cabal diff if it is committed.

For Nix-managed projects, preserve the pinned shell/build inputs and run the repository's flake or derivation checks in addition to the underlying Cabal/Stack tests when those checks are part of acceptance.

## Dependencies and Bounds

- Add a dependency only when it reduces total complexity and its maintenance, portability, licensing, and transitive cost fit the project.
- Library bounds describe supported combinations and should be tested at meaningful lower/upper points when releases promise them.
- Application freezes or lock snapshots improve reproducibility but do not substitute for truthful library bounds.
- Test multiple supported GHC/dependency combinations when algebraic behavior, type inference, TH/plugins, FFI, or optimizer behavior is version-sensitive.
- Record the exact compiler/resolver for benchmarks and difficult regressions.

## CI and Release Evidence

- CI should identify toolchain versions, cache keys, project flags, and platform matrix clearly.
- Keep formatting/lint, build, unit/property tests, documentation, packaging, and benchmarks as distinct evidence so skips are visible.
- A green job that skipped tools or components is incomplete evidence.
- For releases, verify metadata, source inclusion, generated modules, exposed/other/autogen module declarations, licenses, Haddock, and clean archive reproducibility.
- Include `-Wmissing-home-modules` or an equivalent module-accounting check where it catches undeclared sources.

## Fallback Quality Script

`scripts/haskell_quality_check.sh` is a repository-agnostic fallback, not an authority override.

- Use `--tool=cabal` or `--tool=stack` when both project surfaces exist.
- Use `--strict` for acceptance or CI; it returns an incomplete status when a requested check is unavailable or ambiguous.
- Use `--formatter=...` when formatter intent is not established by config.
- `--fix` may change source files, so inspect the source set and diff first.
- Read the final passed/failed/skipped summary. A non-strict zero exit with skips means “no observed failures,” not “all checks passed.”
- A strict invocation with every check disabled is reported as incomplete rather than meaningful acceptance evidence.
- Benchmarks and clean unpacked source-archive builds are intentionally repository-specific and remain outside this fallback script.
