---
name: rust-engineering
description: Implement, review, debug, and optimize Rust crates or workspaces. Use for Rust source, Cargo, public APIs, macros, unsafe or FFI, async and concurrency, performance, tests, dependencies, targets, or Rust CI. Do not use for non-Rust work or generic project management.
---

# Rust Engineering

Produce the smallest correct Rust change or the focused review the user requested. Preserve project policy, make costs and invariants visible, and support completion claims with proportionate evidence.

## Start with the repository

1. Read applicable repository instructions and inspect worktree/branch status, the current diff, relevant `Cargo.toml` and toolchain files, CI configuration, and nearby code or tests. Preserve unrelated and pre-existing changes.
2. Identify whether the request is implementation, diagnosis, review, API design, performance work, or project tooling. A review or diagnosis does not authorize edits.
3. Existing repository choices win. Do not change the edition, MSRV, toolchain, features, dependency policy, lint policy, release profiles, public API, or formatting scope unless the request requires it.
4. For a new crate, use the latest stable edition supported by the chosen toolchain. Set `rust-version` to the actual minimum supported compiler; it declares an MSRV, not a toolchain pin. Add a toolchain pin only when reproducibility or project policy calls for one.
5. Read only the references routed below that match the task.

## Cross-cutting rules

- Default to a single crate with a clean internal module hierarchy. Split into a multi-crate workspace only when justified by separate distribution artifacts, procedural macro boundaries (`proc-macro = true`), target/platform/dependency isolation, or measured compilation barriers. Ban speculative micro-crates (e.g. `app-types`, `app-utils`).
- Enforce tight visibility boundaries: default to private or `pub(crate)` visibility. Ban unqualified `pub` across internal module boundaries or crate-private plumbing.
- Maintain unidirectional layering: Core Domain (pure types, domain logic, zero I/O or CLI dependencies) -> Storage & Adapters (I/O, database, network protocols) -> Application & CLI (CLI parsing, orchestration). Lower layers must never depend on higher layers.
- Apply the Rule of Three for traits: write concrete structs and methods first; do not extract a trait or generic parameter unless at least 3 distinct concrete implementations exist in the repository or an established framework contract requires it. Ban speculative `dyn Trait` dynamic dispatch when concrete types, enums, or generics suffice.
- Forbid builder patterns for structs with fewer than 5 fields (< 5 fields); use direct struct literal instantiation, `new()` constructors, or `Default` + struct update syntax. Reserve builders for structs with 5 or more fields or staged fallible validation.
- Enforce single-path execution and atomic in-place refactoring: when modifying types, functions, or interfaces, cleanly update all call sites, internal usages, and tests in the same change wave. Ban `#[deprecated]` enum variants in internal types, forwarding shim functions, zombie serde alias decoders, and ghost/commented-out code.
- Prefer a straightforward safe design. Add a dependency only when it reduces total complexity enough to justify its maintenance and build cost.
- Return an actionable error for failures callers can handle, with a typed error when callers need to branch on failure kinds. Panic for violated programmer contracts or impossible internal states, not ordinary input, I/O, or network failures.
- Take borrowed forms such as `&str`, `&[T]`, and `&Path` when only reading. Take ownership when storing, consuming, transferring, or transforming ownership; do not borrow merely to clone immediately.
- Treat `unsafe` as a proof boundary: state the invariant, keep the unsafe surface small, document each obligation, and ensure every safe caller preserves soundness. Tests and Miri support the proof but do not establish it.
- Do not hold a blocking lock guard or a `RefCell` borrow across `.await`. Keep significant blocking or CPU-heavy work off async executor workers.
- Make no performance claim without a reproducible, representative before/after measurement. Runtime claims normally require an optimized build; compile-time claims require the same defined build mode and cache state.
- Comments explain invariants, safety obligations, non-obvious tradeoffs, or why a decision was made. Do not narrate syntax.

## Verification

Discover and follow the repository's own commands first. Match validation scope to the change and widen it when risk warrants:

1. **Tier 1 (Fast-Path)**: For bug fixes, localized refactors, minor features, internal helpers, documentation, or config edits, run targeted commands on the affected package:
   - Typecheck: `cargo check -p <pkg>`
   - Unit test filter: `cargo test -p <pkg> --lib -- <test_name>`
   - Integration test suite: `cargo test -p <pkg> --test <suite> -- <test_name>`
   - Binary test filter: `cargo test -p <pkg> --bin <bin> -- <test_name>`
   - Targeted lint: `cargo clippy -p <pkg>`
2. **Tier 2 (Full Verification)**: For core architectural modifications, public crate APIs, unsafe/FFI boundaries, data migrations, or release gates, run full workspace verification:
   - Full workspace test suite: `cargo test --workspace --all-targets`
   - Workspace doctests: `cargo test --doc --workspace`
   - Strict workspace lint: `cargo clippy --workspace --all-targets -- -D warnings`
   - Workspace docs check: `RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps`
3. Check formatting without creating unrelated churn: `cargo fmt --all -- --check`. Inspect the diff before applying write-mode formatter output in a dirty tree.
4. Run Clippy on the relevant packages, targets, and feature sets. Use `--workspace` only when claiming workspace coverage, and `--all-features` only when features are designed to compose.
5. Run broader MSRV (`cargo +<msrv> check`), safety (Miri, sanitizers), or release lanes when the task or repository acceptance policy requires them.

Do not hide a pre-existing failure by changing unrelated code. Report the exact command, whether it passed, and any baseline or environmental blocker. If a requested gate cannot run, state that rather than weakening the completion claim.

## References

- Public APIs, error types, trait semantics, compatibility, crate layout, features, or MSRV policy: read [references/api-design.md](references/api-design.md).
- Declarative macros, procedural macros, generated syntax, hygiene, spans, or macro diagnostics: read [references/macros.md](references/macros.md).
- Ownership, borrow-checker design, collections, memory representation, arenas, interning, unsafe, or FFI: read [references/memory-layout.md](references/memory-layout.md).
- Async, Tokio, threads, channels, locks, atomics, cancellation, or Rayon: read [references/concurrency-async.md](references/concurrency-async.md).
- Runtime or compile-time speed, profiling, benchmarks, build profiles, allocation, hashing, or I/O hot paths: read [references/performance.md](references/performance.md).
- Build scripts, generated code, native dependencies, cross-compilation, `no_std`, OS interfaces, or target portability: read [references/targets-build.md](references/targets-build.md).
- Lints, formatting, tests, dependency checks, Miri, fuzzing, sanitizers, coverage, or CI: read [references/tooling-ci.md](references/tooling-ci.md).

When several areas interact, read the smallest combination that covers the decision. Do not load every reference for a routine edit.
