# Skill Maintenance Evaluation Scenarios

These are behavioral regression cases for maintainers of the Rust engineering skill, not instructions to load for ordinary Rust work. Run a representative subset through an independent agent in disposable workspaces after substantial edits. Judge decisions and artifacts, not exact wording.

## 1. Exported declarative macro

**Request:** Fix an exported `macro_rules!` macro that calls an unqualified internal helper, evaluates `$value:expr` twice, and fails when the dependency is renamed.

**Accept when the response:** inspects repository edition/MSRV and API policy; uses an appropriate fragment; evaluates the expression according to the documented count; resolves owned helpers through `$crate` with sufficient visibility; checks downstream use with a renamed dependency; and considers the macro's accepted syntax and expansion semantics public API.

**Reject when it:** imports helper names into the caller, uses arbitrary `tt` without need, assumes `$crate` bypasses privacy, or proves the change only inside the defining crate.

## 2. Procedural macro diagnostics

**Request:** Review a derive macro that stringifies its input, calls `unwrap()` on malformed attributes, and generates unqualified `Result` and `Error` names with call-site spans.

**Accept when the response:** recommends token/syntax parsing, actionable compile errors at useful spans, qualified or rename-safe generated paths, downstream compile-pass and compile-fail tests, and deterministic expansion. It should separate testable domain logic from the proc-macro entrypoint when useful.

**Reject when it:** treats panics as normal validation, tests only snapshots of expanded text, or ignores hygiene and dependency renaming.

## 3. Cross-compiling a build script

**Request:** Diagnose a `build.rs` that uses `cfg!(target_os = "linux")`, writes generated Rust into `src/`, reruns after every package edit, and invokes the host `cc` while building for an ARM target.

**Accept when the response:** distinguishes host from target; uses `TARGET` or `CARGO_CFG_*`; keeps output under `OUT_DIR`; adds precise rerun triggers; configures a target-aware native compiler; and distinguishes `cargo check` from target linking or execution.

**Reject when it:** changes only the `cfg!`, runs a broad clean as the first step, or claims a host test proves the ARM artifact.

## 4. Unsound pin projection

**Request:** Review a self-referential type that implements `Unpin`, exposes an unchecked mutable field projection, and can replace its pinned field before `Drop`.

**Accept when the response:** states the address-sensitive invariant; explains why `Pin` is a library contract; reviews `Unpin`, projection, replacement, and the drop guarantee together; prefers a vetted projection abstraction when policy permits; and treats Miri as supporting evidence rather than proof.

**Reject when it:** suggests `Box::pin` alone establishes every invariant or focuses only on whether the example currently moves in a test.

## 5. Partial `MaybeUninit` construction

**Request:** Fix array initialization that writes elements through `MaybeUninit`, returns early on element 40, and then either leaks the first 39 values or calls `assume_init` on the incomplete array.

**Accept when the response:** tracks initialized elements, adds unwind/error cleanup, avoids early `assume_init`, preserves exactly-once ownership, and tests partial failure and destructor counts.

**Reject when it:** uses zero initialization for arbitrary `T`, calls `assume_init_read` repeatedly, or presents a green Miri run as the invariant.

## 6. Compile-time regression

**Request:** Reduce a workspace's edit-to-check time by 20% after a new proc-macro dependency doubled local build latency.

**Accept when the response:** defines clean versus incremental and check versus build; records exact packages, features, target, toolchain, linker, cache state, and representative edit; uses Cargo timings and feature/dependency evidence; compares identical modes; and preserves runtime, diagnostics, and API behavior.

**Reject when it:** benchmarks release runtime, compares a warm no-op build with a cold build, deletes a shared target directory without inspection, or claims a win from a single noisy sample.

## 7. Advertised `no_std` support

**Request:** Audit a crate advertising `no_std` because its root has `#![no_std]`, although default dependencies enable `std` and tests run only on the host with default features.

**Accept when the response:** distinguishes `core`, `alloc`, and `std`; inspects transitive feature defaults; defines promised targets and feature sets; uses additive capability gating; and checks the real target with `--no-default-features` plus any promised allocation feature.

**Reject when it:** treats the crate attribute as proof, globally disables useful default features without checking API behavior, or installs allocator/panic infrastructure in an ordinary library.

## 8. Negative type-system contract

**Request:** Add tests for a type-state API that must reject `send()` before authentication while continuing to accept the authenticated path.

**Accept when the response:** adds a focused compile-fail case and a nearby valid compile-pass/behavioral case, verifies failure for the intended trait or method-availability reason, and follows the repository's existing UI harness or justifies a small dependency.

**Reject when it:** asserts only that compilation failed, snapshots an unrelated missing import, or replaces the static contract with a runtime panic.

## 9. Premature trait abstraction and mock bloat (Rule of Three)

**Request:** Refactor a concrete `UserRepository` in an application crate by extracting a `trait UserRepositoryTrait`, converting the caller struct to store `Box<dyn UserRepositoryTrait>`, and adding a `MockUserRepository` generated with `mockall` to unit test 2 business logic functions.

**Accept when the response:** enforces the Rule of Three; rejects speculative trait extraction and dynamic dispatch overhead (`Box<dyn Trait>`) when only one production implementation exists; avoids heavy mock frameworks and boilerplate; and demonstrates testing the concrete struct directly or using a simple concrete in-memory double/fake.

**Reject when it:** encourages extracting single-implementation traits solely for mocking, approves speculative dynamic dispatch, or introduces combinatorial mock test sprawl.

## 10. Single-path refactoring vs deprecated enum shims

**Request:** Refactor an internal crate state enum by renaming `TaskState::Active` to `TaskState::Running` and adding a new required field to `Task`. The developer proposes keeping `#[deprecated] Active` as an alias and adding a forwarding constructor `Task::new_legacy(...)`.

**Accept when the response:** enforces single-path execution and clean in-place replacement; atomically updates all match arms, call sites, and tests to use `TaskState::Running` in the same change wave; removes legacy constructors and forwarding shims; forbids deprecated variants in internal types; and leaves no zombie serialization aliases or ghost code.

**Reject when it:** preserves `#[deprecated]` variants in internal types, creates forwarding shim functions, retains fallback decoders without external requirements, or leaves commented-out legacy code.
