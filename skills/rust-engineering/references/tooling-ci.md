# Tooling, Tests, and CI

Read this when changing Rust formatting, lints, tests, dependency policy, MSRV checks, safety tooling, benchmarks, or CI. Treat this as a menu: preserve the repository's toolchain and acceptance policy, then add only lanes justified by the code and release risk.

## Proportionate validation

Scale verification effort directly to the scope and risk of the change:

- **Tier 1 (Fast-Path)**: For bug fixes, localized refactors, minor feature additions, internal helpers, documentation, or config changes: run ONLY the targeted test suite/filter for the affected module and fast linter/typecheck. Do not run whole-workspace test suites or heavy integration benchmarks for localized edits.
- **Tier 2 (Full Verification)**: For core architectural modifications, cryptographic primitives, public crate/library APIs, unsafe/FFI boundaries, concurrency/memory-safety invariants, durable data schema migrations, or release preparation: run the full repository acceptance command, complete workspace test suite, doc tests, strict linters, and any relevant fuzz/property/Miri tests.

### Fast-Path Command Cookbook (Tier 1)

Execute the cheapest focused check for the modified component:

```bash
# Fast typecheck (no code generation or linking)
cargo check -p <pkg>

# Fast unit test filter (runs only tests matching <test_name> in the crate library)
cargo test -p <pkg> --lib -- <test_name>

# Fast integration test suite (runs only the specified integration test file)
cargo test -p <pkg> --test <suite> -- <test_name>

# Fast binary target test (runs tests in a specific binary target)
cargo test -p <pkg> --bin <bin> -- <test_name>

# Fast targeted Clippy lint check
cargo clippy -p <pkg> -- -D warnings
```

### Full Verification Commands (Tier 2)

```bash
# Workspace-wide typecheck across all targets
cargo check --workspace --all-targets

# Complete workspace test suite execution
cargo test --workspace --all-targets

# Workspace documentation and doctests
RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps
cargo test --doc --workspace

# Workspace-wide strict Clippy lint check
cargo clippy --workspace --all-targets -- -D warnings

# Targeted Miri execution for unsafe blocks (when applicable)
cargo +nightly miri test -p <pkg>
```

| Change | Tier | Useful evidence |
|---|---|---|
| Local implementation or bug fix | Tier 1 | focused test, affected package build/check, formatting and Clippy in relevant scope |
| Public library API | Tier 2 | above plus doctests/docs, feature combinations, MSRV and compatibility review |
| Declarative or procedural macro | Tier 1/2 | expansion behavior, downstream compile-pass and compile-fail cases, diagnostics and supported editions/features |
| Build script or generated/native code | Tier 2 | rerun triggers, clean rebuild, package contents, and promised host/target combinations |
| Unsafe or FFI | Tier 2 | targeted Miri where supported, fuzz/property tests, sanitizer/platform tests as applicable |
| Concurrent state machine | Tier 2 | pending/cancellation tests, Loom model where practical, stress tests |
| Release preparation | Tier 2 | repository's full workspace, platform, dependency, package, and release gates |
| Performance claim | Tier 1/2 | correctness plus the before/after protocol in `performance.md` |

Run the cheapest focused discriminator first, then widen. `cargo check` catches type errors quickly but does not replace linking or running the affected target. Use `cargo build` or tests when link behavior matters.

Cargo scope flags are part of the evidence:

- `-p crate_name` means one selected package;
- `--workspace` means every workspace member not excluded by workspace configuration;
- `--all-targets` includes configured libraries, binaries, examples, tests, and benches for the selected packages;
- `--all-features` is valid only when features are designed to compose;
- `--locked` is appropriate when CI must not rewrite `Cargo.lock`.

State the actual scope rather than calling a package-only command a workspace gate.

## Formatting

- Follow the repository's rustfmt configuration and pinned toolchain. Stable and unstable rustfmt options vary; validate configuration with the project's formatter rather than assuming an option is portable.
- Check with `cargo fmt --all -- --check`. Before running write-mode formatting in a dirty tree, inspect whether it would touch unrelated files.
- Formatting an edited file is normally in scope; broad historical reformatting is a separate change.
- Edition and rustfmt style edition are distinct concepts. Do not opt a repository into a nightly-only style setting merely because the crate uses Edition 2024.

## Lints

Cargo manifest lint configuration is useful when supported by the repository's MSRV. Workspace inheritance keeps policy consistent:

```toml
# workspace root
[workspace.lints.rust]
unsafe_op_in_unsafe_fn = "warn"
unreachable_pub = "warn"

[workspace.lints.clippy]
all = { level = "warn", priority = -1 }
undocumented_unsafe_blocks = "warn"

# each participating member
[lints]
workspace = true
```

- Give a lint group lower priority than individual overrides; same-priority group/lint conflicts have no guaranteed ordering.
- Enable `clippy::all` as a useful baseline when it fits existing policy. Adopt `pedantic`, `nursery`, `cargo`, and restriction lints selectively; they contain policy choices and can change between toolchains.
- Prefer a narrow `#[expect(lint, reason = "...")]` when supported, or a reasoned `#[allow]`, over crate-wide suppression.
- Escalating warnings with `-- -D warnings` is a CI policy, not a universal local command. New compiler or Clippy versions can add warnings, so use the repository's pinned/MSRV lanes for required gates and treat beta/newest-toolchain linting as advisory unless policy says otherwise.
- Safety comments and `# Safety` docs are requirements of sound review even if a specific toolchain does not warn. Enable the corresponding lints explicitly rather than relying on their current default groups.
- For Edition 2024 FFI or exported symbols, also review `missing_unsafe_on_extern` and `unsafe_attr_outside_unsafe`; enable the migration lints that match the repository's edition policy.

## Test organization and runners

- Put unit tests near the code when private behavior matters. Integration tests exercise the public surface; remember that each top-level `tests/*.rs` file is a separate test crate and has link-time cost.
- Doctests validate public examples and run under `cargo test --doc`. Select `-p` or `--workspace` explicitly when claiming broader coverage, and keep this lane even when another test runner does not support doctests.
- Nextest is useful for process isolation, filtering, timeouts, JUnit output, sharding, and configured retries. Do not assume a fixed speedup. Retries are opt-in; if CI must reject flakes, configure retry and flaky-result policy explicitly.
- Property tests fit parsers, serializers, state transitions, algebraic laws, and boundary-heavy code. Commit minimized regression inputs or seeds in the form expected by the chosen framework.
- Snapshot tests fit intentionally reviewable structured output. Normalize nondeterminism, review changes, and prevent CI from silently accepting new snapshots.
- Use compile-pass and compile-fail/UI tests when rejection is part of the contract: macro inputs, trait bounds, type-state APIs, unsafe trait obligations, or compiler diagnostics. Follow the repository's harness; `trybuild` is one option for downstream-style cases. Assert the meaningful error and span without coupling every test to incidental wording when the harness permits it.
- Pair every important compile-fail case with a nearby valid case. A test that fails for an unrelated missing import, stale feature, or earlier parse error does not prove the intended rejection.
- Test failure paths, not just successful values: partial I/O, closed queues, cancellation, panics from collaborators, invalid UTF-8/bytes, overflow boundaries, and platform differences relevant to the code.

## Dependencies and supply chain

- Use `cargo audit` for a focused RustSec advisory check. Use `cargo deny` when the project wants one policy tool for advisories, licenses, duplicate/banned crates, and registry or Git sources. They overlap but are not identical.
- Advisory data changes without source changes, so security checks often need a scheduled lane as well as pull-request checks.
- Use `cargo machete` or another dependency analyzer when unused dependencies are a real maintenance or build-time concern; review macro/build-script false positives before removal.
- High-assurance projects may use `cargo vet` and imported audit sets. Do not impose that process on an ordinary crate without an organizational trust model.
- Pin or update CI actions and downloaded binaries according to the repository's supply-chain policy. A Rust skill should not silently choose a hosting provider or third-party action set.

## Documentation, MSRV, features, and releases

- Check public docs with `RUSTDOCFLAGS="-D warnings" cargo doc --no-deps` in the intended package/feature scope, repeating supported feature or target scopes when they change the public docs. Run doctests separately.
- Test the exact declared MSRV with the required targets and feature sets; a bare `cargo +1.xx check` covers only its selected defaults. The toolchain must be installed and compatible with the manifest.
- For feature-heavy crates, define supported combinations. A feature powerset tool can automate this, but exclude intentionally incompatible combinations.
- `cargo-semver-checks` supports public-API compatibility review, but choose an explicit baseline such as a published version or baseline revision. It is evidence, not a complete semantic compatibility proof.
- Before publishing, run the repository's packaging checks and inspect `cargo package --list`; compile or test the packaged artifact when generated files or include/exclude rules matter.

## Unsafe, FFI, and concurrency tools

### Miri

```bash
rustup +nightly component add miri
cargo +nightly miri setup
cargo +nightly miri test
MIRIFLAGS="-Zmiri-strict-provenance" cargo +nightly miri test
```

- Target the tests that exercise unsafe boundaries. Miri can be slow and does not support every platform API, syscall, network operation, or foreign call.
- Ignore a test under `cfg(miri)` only after confirming the unsupported operation; keep native coverage elsewhere.
- Miri explores the executions and seeds it runs. Consider multiple seeds or target interpretation when relevant, and never treat a green run as proof of soundness.

### Fuzzing and properties

- Fuzz parsers, decoders, protocol boundaries, unsafe safe-wrappers, and other attacker-controlled inputs. Keep targets narrow enough to reach deep states.
- Preserve minimized crashing inputs as regressions. Replay unsafe-related failures under Miri when the path is supported.
- Scheduled short fuzz jobs provide continuity; serious public attack surfaces may warrant longer dedicated or hosted fuzzing.

### Sanitizers

- Rust sanitizer support is nightly-, sanitizer-, and target-specific. Follow the current [Rust sanitizer guide](https://doc.rust-lang.org/stable/unstable-book/compiler-flags/sanitizer.html).
- Pass an explicit target so sanitizer flags do not instrument host build scripts or proc macros unintentionally.
- Add `-Zbuild-std` with the `rust-src` component when the sanitizer requires or benefits from an instrumented standard library; set `RUSTDOCFLAGS` as well if doctests are included.
- Use sanitizers for native/FFI paths Miri cannot execute. Verify supported platforms instead of copying one Linux target command into every project.

### Loom and stress tests

- Model small synchronization protocols with Loom by replacing synchronization primitives behind a test configuration. Assert invariants across modeled interleavings.
- Keep model state and loop bounds small enough to finish. Use native stress tests as complementary evidence for code and platform behavior outside the model.

## Mutation hazards

Some “checks” rewrite the working tree:

- ordinary Cargo commands can create `Cargo.lock` when none exists, and dependency resolution can update it unless `--locked` is used with an existing lockfile;
- `cargo update` and minimal-version experiments modify `Cargo.lock`;
- snapshot review can rewrite expected files;
- fuzzers add corpus or crash artifacts;
- formatters can touch files outside the requested change.

Run these in a disposable checkout/worktree or preserve and review the exact diff. Cargo currently warns that transitive `-Z minimal-versions` is not recommended because dependency lower bounds are often inaccurate; prefer `-Z direct-minimal-versions` when that narrower experiment answers the question. Treat the result as evidence about declared lower bounds, not a routine gate.

## CI lanes

Build CI from project risk instead of copying a canonical matrix:

1. **Baseline:** format check, relevant build/check, tests, and Clippy.
2. **Public library:** docs/doctests, MSRV, supported features, and compatibility checks.
3. **Platform:** only the operating systems and targets the project promises.
4. **Safety:** targeted Miri, fuzzing, sanitizers, or Loom where code justifies them.
5. **Dependencies:** advisory/policy checks on pull requests and a schedule.
6. **Performance:** a benchmark lane designed around the measurement limits in `performance.md`.

Required baseline lanes should be reproducible and bounded. Record tool versions or use the repository's pinning strategy. Treat rolling beta/nightly/dependency-update lanes as bounded early-warning checks, and isolate their drift so it does not masquerade as a regression in unchanged code.
