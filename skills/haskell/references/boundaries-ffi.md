# Text, Parsers, Serialization, FFI, and Unsafe Boundaries

Use this page when values cross a syntax, byte, process, network, database, or foreign-language boundary.

## Text and Bytes

- Use `Text` for Unicode text and `ByteString` for uninterpreted or encoded bytes; use `String` where project compatibility or very small code makes it appropriate.
- Name encodings at every text/byte conversion and choose explicit invalid-input behavior.
- Do not assume Unicode code points are user-perceived characters. Specify normalization, case folding, collation, or grapheme behavior when the domain depends on it.
- Choose strict or lazy representations from lifetime, streaming, and evaluation requirements.

## Parser Contracts

- Decide whether success requires full consumption. For complete messages/files, require end-of-input; for incremental protocols, return and specify leftovers.
- Specify whitespace, ambiguity, backtracking, error location, recovery, nesting depth, token length, and total input-size limits.
- Put bounds before allocation or recursion controlled by untrusted lengths.
- Preserve numeric intent: distinguish exact integers/rationals/decimals from floating approximation, and define overflow and exponent limits.
- Ensure repeated alternatives cannot accept empty input indefinitely.
- Test valid boundaries, malformed prefixes/suffixes, truncation, trailing data, ambiguous cases, adversarial size/depth, and incremental chunk splits.
- A parser/printer round trip alone is insufficient; also test acceptance boundaries and canonical output.

## Serialization and Stable Formats

- **Single-Path Codecs & Clean Replacement**: When modifying Aeson `FromJSON`/`ToJSON` instances, binary parsers (`binary`, `cereal`, `store`), or wire formats during refactoring, perform a clean in-place replacement and atomically update all call sites, internal usages, and test fixtures in the same change wave.
- **Ban Zombie Decoders & Dual-Format Fallbacks**: Never use `<|>` in `FromJSON` or parser combinators to accept legacy or obsolete formats alongside new formats (e.g. `parseNewFormat <|> parseLegacyFormat`) unless the requirement explicitly mandates multi-version backwards compatibility. Obsolete decoders create silent deserialization bugs and mask schema drift.
- **Ban Shim Multiplication**: Do not introduce or retain pass-through forwarding functions or alias wrappers (e.g. `legacyDecode = newDecode . adapt`) around refactored serialization logic.
- **Ban Paranoid Dual-Writing & Ghost Code**: Never mutate both legacy and new stores, fields, or endpoints concurrently during refactoring. Never retain dead parser branches, commented-out old codecs, or unused definitions in `_legacy` modules.
- **Ban Preemptive Deprecation Staging**: Do not introduce `{-# DEPRECATED #-}` pragmas or migration scaffolding when an immediate clean replacement is feasible.
- Define versioning, tags, field ordering, canonical representation, unknown-field policy, duplicate-field policy, and trailing-byte behavior.
- Reject or bound hostile lengths before allocation. Bound nesting and collection counts.
- Test decode/encode round trips, canonicalization, independent golden vectors, older supported versions (when explicitly commanded), corrupt data, and truncation.
- Do not accidentally make derived `Generic`, `Show`, constructor order, or record layout a stable wire format.
- Separate semantic validation from syntactic decoding, while ensuring unchecked values cannot enter the trusted core.

## FFI Checklist

- Match the exact ABI and C types; do not infer that Haskell `Int` matches C `int`, `long`, or pointer width.
- Choose `unsafe`, `safe`, or `interruptible` foreign calls from call duration, callbacks into Haskell, blocking, and cancellation behavior. A blocking or unbounded call must not be declared `unsafe`, because it can block a capability and starve unrelated Haskell work. Verify threaded-runtime, scheduler-progress, and callback requirements against the supported GHC contract.
- `safe` permits other Haskell work while a call runs but does not make arbitrary foreign computation cancellable. Use `interruptible` only for suitable blocking calls with a defined interruption/`EINTR` contract, and test actual cancellation behavior.
- Document pointer ownership, nullability, aliasing, lifetime, pinning, and which allocator/free function pair applies.
- Validate `Storable` size, alignment, offsets, padding, and endianness against the foreign definition.
- Keep buffers and callbacks alive for the required duration. Manage `StablePtr`, `FunPtr`, and callback teardown explicitly.
- Treat finalizers as nondeterministic backup, not the primary release mechanism for scarce resources.
- Never allow a Haskell exception to cross a foreign ABI boundary unless an explicit bridge translates it safely.
- Test on every supported architecture/platform whose ABI matters, ideally against a tiny foreign oracle.

## Unsafe Operations Are Proof Boundaries

- `unsafePerformIO` is sound only if the exposed result is observationally pure under evaluation order, duplication, optimization, and concurrency. Never hide a live handle, resource owner, or polymorphic mutable reference behind it.
- Isolate each use and give a concrete optimizer/concurrency argument. `NOINLINE` is only a containment measure, not a soundness proof; common-subexpression elimination and let-floating/full-laziness may also matter. Test optimized and unoptimized builds plus concurrent first evaluation when relevant, and do not combine it casually with STM.
- `unsafeCoerce` requires a concrete representation proof, including roles, levity, runtime representation, and version assumptions. Prefer `coerce` when it expresses the valid relationship.
- Unsafe pointer operations require explicit size, alignment, lifetime, aliasing, and initialization invariants.
- Keep unsafe code in a small module with a safe exported API and focused tests. Review optimized and unoptimized builds where optimizer interaction matters.
- Safe Haskell annotations and compiler acceptance are useful signals, not substitutes for the invariant argument.
