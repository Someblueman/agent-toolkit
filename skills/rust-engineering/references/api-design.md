# API Design

Read this for public APIs, error types, trait semantics, crate boundaries, features, compatibility, or MSRV decisions. The [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/about.html) are useful considerations, not mandates; apply them to the API's audience and stability promise.

## Establish the contract first

- Distinguish a stable public library API from application code, a prototype, or crate-private plumbing. Compatibility and documentation costs differ sharply.
- Determine whether compatibility is a current requirement. Do not preserve or break it by accident. For a published crate, check the repository's versioning policy and use `cargo-semver-checks` as supporting evidence where available.
- **Single-Path Execution & Atomic In-Place Refactoring**: For internal code, refactor in place and atomically update all call sites, match arms, and tests in the same change wave. Do not preserve backward compatibility unless explicitly required.
- Strictly forbid legacy retention anti-patterns:
  - *Shim Multiplication*: Retaining deprecated functions/methods as pass-through forwarding wrappers around new implementations (`pub fn old_fn(&self) { self.new_fn() }`).
  - *Deprecated Enum Variants*: Adding `#[deprecated]` to enum variants in internal domain or error types instead of updating all match expressions.
  - *Dual-Format Fallbacks & Zombie Decoders*: Keeping obsolete deserialization branches, legacy format parsers, or `#[serde(alias = "...")]` attributes without explicit user instruction.
  - *Ghost Code*: Commenting out old implementations, leaving dead fallback branches, or parking dead code in `_legacy.rs` files.
  - *Paranoid Dual-Writing*: Mutating both old and new fields/stores simultaneously during refactoring.
- Keep the public surface as small as the use case permits. Default to private or `pub(crate)`; use restricted visibility such as `pub(super)` when it expresses a real module boundary. Ban unqualified `pub` across internal module boundaries.
- Keep fields private when the type has invariants or needs representation freedom. Public fields can be appropriate for deliberately transparent data records, but they make construction and field changes part of the contract.
- Seal a public trait only when downstream implementations would prevent intended evolution. Otherwise leave it implementable.

## Naming and predictability

- Follow Rust casing: `UpperCamelCase` for types, traits, and variants; `snake_case` for functions and modules; `SCREAMING_SNAKE_CASE` for constants. Treat acronyms as words (`Uuid`, not `UUID`).
- Use `as_` for cheap borrowed-to-borrowed views, `to_` for conversions that may allocate or do work, and `into_` for consuming conversions.
- Avoid `get_` on ordinary accessors. Collection-like APIs conventionally provide `iter`, `iter_mut`, and `into_iter` when all three semantics exist.
- Use `new` for the primary constructor when that is natural; domain verbs such as `open`, `connect`, or `parse` are often clearer. When zero-argument `new()` is the natural default, implement `Default` and make them agree.
- Implement `Deref` only for genuine smart-pointer behavior, not field forwarding or inheritance.
- Overload operators only when callers will find the algebraic meaning unsurprising.

## Ownership and generic boundaries

- Take `&str`, `&[T]`, and `&Path` when only reading. Take an owned value when storing, consuming, transferring, or transforming its ownership.
- Use `impl Into<String>` when an API stores a string and accepting ownership avoids a copy. Use `AsRef<Path>` or `IntoIterator` at ergonomic public boundaries when the broader caller set is valuable; avoid spreading generic signatures through internals.
- A useful pattern is generic at the edge, concrete inside: normalize the input once, then call a monomorphic implementation. This controls signature complexity and monomorphization.
- Prefer return values over out-parameters. Caller-supplied reusable buffers are an intentional exception when allocation control matters.
- Use `impl Trait` for a simple one-off argument bound or an opaque return. Use a named type parameter when types must relate, callers may need to name it, or the bound is easier to understand that way.
- Decide whether a trait should support `dyn Trait`. Put methods that make it non-dyn-compatible behind `where Self: Sized` when object use is part of the contract.
- Take `R: Read` or `W: Write` by value; callers can still pass `&mut R` through the standard blanket implementations.

## Make invalid states difficult to express

- Use newtypes when two values share a representation but not a meaning, or when validation must happen once at construction.
- Replace ambiguous groups of booleans with named enums or option structs. Keep a boolean when its call-site meaning is already clear.
- `Option<T>` is appropriate when absence is part of the domain. Replace it with a named type only when several optional states or parameters are ambiguous.
- **Struct Construction & Builder Ban**:
  - Choose direct construction, constructors or builders according to validation needs and call-site clarity, not field count.
  - Choose direct construction, constructors or builders according to validation needs and call-site clarity, not field count.
- Use `bitflags` or an equivalent vetted representation for interoperable flag sets instead of hand-maintained masks.
- Prefer static enforcement, then checked construction returning `Result`. An unchecked API is justified only by demonstrated need and must state its safety contract.

## Traits and conversions

- Prefer concrete code; introduce an abstraction when it simplifies a current requirement or expresses a necessary boundary or invariant.
- **Anti-Mock Sprawl**: Never extract single-implementation traits solely to generate mock objects with `mockall` or test doubles. Test concrete structs directly or use concrete in-memory doubles.
- **Ban Speculative Dynamic Dispatch (`dyn Trait`)**: Avoid `dyn Trait` or `Box<dyn Trait>` unless heterogeneous runtime collections or dynamic runtime polymorphism are strictly required. Dynamic dispatch introduces vtable pointer indirection, fat pointers, extra heap allocation, and defeats compiler inlining, dead-code elimination, and devirtualization. Prefer concrete enums or static generics.
- Implement common traits only when their semantics are honest and useful. In particular, `Copy`, `Default`, ordering, hashing, serialization, and `Send + Sync` are contracts, not decoration.
- `Debug` is strongly expected on public data types, except where exposing state would be misleading or sensitive.
- Prefer `From` and `TryFrom`; their blanket implementations provide `Into` and `TryInto`. Implement the latter directly only when coherence prevents the corresponding `From` implementation.
- Collection types should implement `FromIterator` or `Extend` when bulk construction or extension is a real operation, not merely because the type contains elements.
- Optional ecosystem integrations such as Serde belong behind features when unconditional dependency and compatibility costs are not justified.
- Adding or removing trait implementations can affect type inference and downstream code. Include trait-surface changes in compatibility review.

## Errors and panics

- Libraries need structured errors when callers must distinguish failure kinds. A public enum, a `#[non_exhaustive]` enum, or an opaque error with inspectable kinds are all valid depending on evolution needs.
- `thiserror` is a convenient implementation choice, not a requirement. Avoid adding it when a small standard-library error implementation is clearer or dependency cost matters.
- Applications may use `anyhow` with contextual messages when failures are handled at a top-level reporting boundary. Keep typed domain errors below boundaries where code branches on them.
- Preserve error sources with `Error::source` or transparent conversion. Error display text is normally a lowercase sentence fragment without trailing punctuation when it will be embedded in a larger message.
- Panic only for violated programmer contracts or impossible internal states. Return `Result` for ordinary I/O, parsing, user-input, and network failures.
- Use `expect` only when the invariant is locally evident, and make its message explain why the value must exist. Never panic in `Drop`.
- If teardown can fail, expose an explicit `close`, `flush`, or `shutdown` operation. `Drop` remains synchronous and best-effort.

## Modules, features, and workspaces

- **Crate & Workspace Architecture Decision Rules**:
  - *Single-Crate Default*: Default to a single crate with well-structured internal modules (`src/lib.rs` and submodules). A single crate maximizes compiler optimization (LTO, cross-module inlining), simplifies dependency management, and avoids cross-crate boundary churn.
  - *Multi-Crate Workspace Justification*: Split into multiple crates only when at least one of these concrete architectural boundaries exists:
    1. **Distribution Artifact**: Independent publishable packages (e.g. public SDK library vs standalone CLI binary).
    2. **Procedural Macro Boundary**: Compiler mandate where derive/attribute macros must reside in a dedicated crate with `proc-macro = true`.
    3. **Target / Platform / Dependency Isolation**: Isolating `no_std` embedded core logic from `std` host code, or segregating heavy native C/FFI bindings and heavy optional dependencies.
    4. **Measured Compilation Barrier**: Verified compilation bottleneck where crate-level caching significantly and measurably reduces build latency.
  - *Ban Speculative Micro-Crates*: Forbid decomposing an application into arbitrary micro-crates (e.g. `app-types`, `app-utils`, `app-core`, `app-models`) without meeting the above criteria.
- Preserve established module boundaries. Separate pure domain logic from I/O when useful, without imposing three mandatory layers or an unrelated namespace rewrite.
- Re-export the small set of primary public types at an ergonomic path. Do not flatten every implementation detail into the crate root.
- Prefer a shallow, coherent module tree. Do not churn an established `foo/mod.rs` versus `foo.rs` convention without a reason.
- Keep binaries thin when substantial logic benefits from library tests or reuse, but do not create a library solely to satisfy a template.
- Cargo features should be additive because dependency resolution unifies enabled features. Do not use a feature to remove APIs or silently change core semantics. See the [Cargo features reference](https://doc.rust-lang.org/cargo/reference/features.html).
- Test meaningful feature combinations. `--all-features` is not a valid acceptance gate when features are intentionally mutually exclusive.
- Treat `rust-version` as the declared minimum supported compiler, not a pin. Preserve the repository's MSRV and release policy; verify with that toolchain when compatibility matters. See the [Cargo rust-version reference](https://doc.rust-lang.org/cargo/reference/rust-version.html).

## Documentation and review checklist

- Put a quick-start example and the main contract in crate-level docs for a public library. Add examples for primary workflows and non-obvious APIs, not mechanically for every item.
- Document `# Errors`, `# Panics`, and `# Safety` where those conditions exist. Use `?` in examples that demonstrate fallible code.
- Use intra-doc links for crate items. Validate public documentation with rustdoc and doctests.
- Before publishing, verify the registry metadata and package contents with the repository's release process and `cargo package --list` or `cargo package`.

Before approving an API change, ask:

1. Which invalid states or ambiguous calls remain possible?
2. Are ownership, allocation, blocking, and panic costs visible to callers?
3. Which fields, variants, trait implementations, feature behaviors, and error kinds become compatibility commitments?
4. Does the API preserve the repository's MSRV and feature policy?
5. Is the simplest common call straightforward without making internals generically complex?
