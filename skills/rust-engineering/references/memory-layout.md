# Ownership, Memory Layout, Unsafe, and FFI

Read this for borrow-checker design, allocation ownership, collections, representation, arenas, interning, unsafe code, or foreign interfaces. Performance measurements belong in `performance.md`; concurrency semantics in `concurrency-async.md`; Miri and sanitizer commands in `tooling-ci.md`.

## Resolve ownership before cloning

| Situation | First option to consider |
|---|---|
| Function only reads owned data | Borrow `&str`, `&[T]`, `&Path`, or `&T` |
| Function stores or transfers the value | Take ownership |
| Input usually passes through, sometimes changes | `Cow` at the boundary |
| Move a field through `&mut self` | `mem::take`, `mem::replace`, or `Option::take` |
| Need disjoint mutable regions | iterators, `split_at_mut`, chunks, or disjoint-entry APIs |
| Check then insert in a map | `entry` API when key construction and ownership fit |
| Drain work while retaining allocation | `drain`, `clear`, or swap reusable buffers |
| Shared data with rare mutation | `Rc::make_mut` or `Arc::make_mut` |

- Do not clone merely to silence a borrow error. First identify whether the conflict is caused by an unnecessarily long borrow, the wrong owner, or a data structure that hides disjointness.
- `Cow` is useful when borrowed and owned results are both common API outcomes. It is not a default field type for speculative allocation avoidance.
- Map entry APIs consume keys. If constructing a key is expensive and hits dominate, consider a borrowed lookup before insertion or a vetted borrowed-entry API.
- Returning an iterator avoids allocation when callers consume once, but a collection is correct when ownership, repeated traversal, sorting, stable storage, or an error boundary requires materialization.

## Shared ownership and interior mutability

| Need | Typical tool |
|---|---|
| Single-owner indirection, recursive value, or trait object | `Box<T>` |
| Shared ownership confined to one thread | `Rc<T>` |
| Shared ownership across threads | `Arc<T>` |
| Single-thread interior mutation of small `Copy` state | `Cell<T>` |
| Single-thread runtime-checked borrowing | `RefCell<T>` |
| Cross-thread mutation | `Mutex<T>`, `RwLock<T>`, or atomics for suitable scalars |

- Choose `Rc` or `Arc` from the actual thread boundary. Let `Send` and `Sync` errors expose incorrect assumptions.
- Prefer a mutex as the simple cross-thread default. Consider an `RwLock` only when the read/write pattern and platform behavior justify it; measure under representative contention.
- A pervasive `Arc<Mutex<T>>` graph often means ownership is unclear. Consider one owner plus messages, a wrapper exposing small lock-scoped operations, sharded state, per-worker state plus reduction, or immutable snapshots swapped as `Arc<T>`.
- Never expose a guard when doing so lets callers hold it across unrelated work or `.await`.

## Data structures and locality

- Start with `Vec`, `HashMap`, and `VecDeque`. Use `BTreeMap` for ordered traversal or range queries. Use linked structures only when their specific cursor, splice, or stable-node behavior has been demonstrated to matter.
- Inline-capacity vectors, alternate hashers, arenas, interning, and struct-of-arrays layouts are optimizations. Adopt them from measured distributions and workload profiles, not type-size folklore.
- Dense graphs and trees often become simpler as arena-owned nodes plus indices or generational keys instead of `Rc<RefCell<Node>>` links. Choose key width from proven bounds and use checked conversions; do not assume `u32` is always sufficient.
- Array-of-structs is the natural default when hot code uses most fields together. Struct-of-arrays can improve locality when hot passes use only a subset; benchmark the real access pattern.

## Representation and layout

Rust layout and code generation are not stable performance contracts. There is no universal byte threshold at which moves become `memcpy`, nor a guaranteed `largest variant + tag` enum formula.

- For performance-sensitive types, measure `size_of`, alignments, profiles, and generated code for the supported target and toolchain. Never derive soundness or wire compatibility from one observed layout.
- `repr(Rust)` guarantees alignment and non-overlapping field storage, although zero-sized fields may share an address. It does not guarantee declaration order, field offsets, ABI, or a particular optimization strategy. See the [Rust Reference](https://doc.rust-lang.org/stable/reference/type-layout.html#the-rust-representation).
- Enums may use explicit discriminants, padding, or niche encodings. Boxing a rare large variant can help when profiling shows size or move costs, but adds an allocation and indirection.
- `repr(C)` supplies the Rust-defined C representation rules; use it only when layout interoperability or a documented layout contract is required. It does not make arbitrary field types FFI-safe.
- `repr(transparent)` is for a one-field wrapper that must share the non-zero-sized field's layout and ABI subject to the Reference's rules.
- `repr(packed)` can create unaligned fields. `&raw` or `addr_of!` avoids forming a reference, but access still needs an appropriate unaligned operation. Avoid packed Rust APIs when parsing bytes explicitly is simpler.
- Niche optimization is guaranteed only for documented cases. For a newtype that relies on the `Option<NonZero*>` representation guarantee, use a transparent wrapper and verify the relevant standard-library guarantee:

```rust
#[repr(transparent)]
#[derive(Clone, Copy)]
struct NodeId(std::num::NonZeroU32);
```

For many instances of immutable variable-length data, `Box<[T]>` or `Arc<[T]>` can remove spare capacity and express the ownership model more directly than `Vec<T>`.

## Arenas and interning

- Arenas fit many allocations with one phase lifetime: parser nodes, IR, request scratch, or frame data. Drop the arena with the phase; a long-lived arena holding short-lived objects retains memory by design.
- Check destructor semantics. Plain `bumpalo` allocation does not run each allocated value's `Drop`; use an ownership form that does when values hold resources.
- Use a generational arena or slot map when individual deletion and slot reuse are required. A bump arena is not a general object store.
- Intern when repeated values are stored, hashed, or compared enough to repay the table and indirection cost. Intern at a boundary, pass symbols internally, and resolve at output so the pipeline does not pay for both strings and symbols.

## Unsafe proof discipline

Unsafe code must be sound for every allowed safe caller, not just observed tests.

1. Write the invariant and identify who establishes and preserves each precondition: construction, private safe code, an `unsafe fn` caller, an unsafe trait implementation, or the foreign side of an FFI boundary.
2. Prefer a safe standard-library or well-maintained crate abstraction whose documented contract exactly matches the need.
3. Keep unsafe operations in the smallest practical module with a safe API that prevents invalid states. Privacy is the primary mechanism preventing arbitrary safe callers from violating module invariants.
4. Put each unsafe operation in an explicit block and explain with `// SAFETY:` why its obligations hold there. Public unsafe functions and traits need a `# Safety` section describing caller obligations.
5. Enforce safety-critical conditions in every build through types, checked operations, explicit validation, or `assert!` for an impossible internal state. Return a checked error for plausible safe-caller input. `debug_assert!` is only an additional diagnostic; it cannot uphold release-build soundness.
6. Account for alignment, initialization and validity, aliasing, lifetimes, provenance, concurrency, unwinding, target features, and destructor behavior as applicable. Avoid `transmute` when explicit construction or parsing makes validity clearer.
7. Enable `unsafe_op_in_unsafe_fn` and `clippy::undocumented_unsafe_blocks` according to the project's lint policy.
8. Run targeted Miri tests and fuzz/property tests over the safe boundary. A passing Miri run is evidence for exercised executions, not a soundness proof; unsupported FFI and platform operations require other tests. See the [Miri limitations](https://github.com/rust-lang/miri#readme).

## Pinning and partial initialization

Use these tools only when the invariant actually requires them. `Pin` is a library contract between unsafe implementations and their callers, not compiler-enforced immovability.

- A value needs pinning only when some state becomes address-sensitive, such as a self-reference or an intrusive link. Ordinary futures may need to be pinned for polling without requiring application code to invent a self-referential type.
- `Pin<P>` constrains how the pointee can be accessed. For `T: Unpin`, pinning adds no restriction and safe APIs permit ordinary mutable access. Do not add `Unpin` to an address-sensitive type merely to make an API compile.
- Treat `Pin::new_unchecked`, handwritten projection, and moving fields out of a pinned value as proof obligations. Prefer a vetted projection abstraction when it matches the repository's dependency policy.
- Structural projection includes destruction: a structurally pinned field must remain valid at its address until its destructor runs. Review replacement, manual allocation, panic-in-`Drop`, and storage reuse against the [pinning drop guarantee](https://doc.rust-lang.org/std/pin/#subtle-details-and-the-drop-guarantee).
- `MaybeUninit<T>` suspends the initialization invariant for its contents; it does not relax the validity rules once a `T`, reference, or slice is formed. Call `assume_init` only after every byte and field required for a valid `T` is initialized. Zero initialization is valid only for types whose all-zero representation is valid.
- For element-by-element or field-by-field construction, track exactly which elements or fields have initialized and use a guard or equivalent RAII cleanup for early return and unwinding. Dropping a `MaybeUninit<T>` does not drop an initialized `T` inside it.
- Avoid duplicating ownership with repeated `assume_init_read` or raw reads. Prove whether the operation moves, copies, or leaves a value that must still be dropped.
- Keep `ManuallyDrop` state private behind methods that make double-drop and use-after-drop unrepresentable. Public generic `ManuallyDrop` fields and derived trait implementations can expose already-dropped values to safe code.

Test safe wrappers at their boundary, including partial failure and destructor paths. Miri is useful for exercised cases but cannot replace the written pinning, initializedness, and cleanup argument.

## FFI boundary checklist

- Match the foreign ABI explicitly (`extern "C"`, `extern "system"`, or deliberately `C-unwind`) and use `#[repr(C)]` or `#[repr(transparent)]` only where the corresponding layout contract is required.
- In Edition 2024, attributes with safety obligations use unsafe-attribute syntax, including `#[unsafe(no_mangle)]`, `#[unsafe(export_name = "...")]`, and `#[unsafe(link_section = "...")]`. Document why the exported symbol or section contract is sound.
- Use `core::ffi` C-width types when matching C declarations. Do not assume Rust `i32`, `i64`, or `usize` matches a platform C typedef.
- Do not model a C enum or bitfield as a Rust enum without proving the foreign side can emit only valid Rust discriminants. Integer types plus validated wrappers often handle unknown values safely.
- Define nullability, pointer lifetime, aliasing, mutability, thread-safety, callback lifetime, and ownership for every pointer. State which allocator and function release returned memory.
- Handle foreign allocation failure and every early-return path explicitly. Use RAII where possible and test success, null/error, panic containment, no-leak, and no-double-free behavior at each ownership transfer.
- Never reconstruct `CString` ownership from a pointer not produced by the matching Rust ownership-transfer API. Foreign allocations need their foreign deallocator.
- Prevent Rust panics from crossing a non-unwinding foreign ABI. Use `extern "C-unwind"` only when cross-language unwinding is intentionally supported and tested. See the [Reference on FFI unwinding](https://doc.rust-lang.org/stable/reference/panic.html#unwinding-across-ffi-boundaries).
- Prefer generated bindings such as `bindgen` or `cbindgen` for maintained interfaces, then test sizes, alignments, calling conventions, symbols, and ownership behavior on supported targets. Generation does not validate semantic ownership or thread-safety.
