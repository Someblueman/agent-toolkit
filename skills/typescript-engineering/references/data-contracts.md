# Durable Data, Serialization, and Schema Evolution

Use this reference when data crosses a process boundary or can outlive the code that wrote it: database rows, files, caches persisted across deploys, events, queue messages, API payloads, snapshots, or signed/hashed representations. Transient internal objects do not need a versioning framework merely because they can be serialized.

## 1. Separate domain values from encoded data

An in-memory TypeScript type is not a storage or wire format. Treat the transition as an explicit codec:

```text
unknown bytes/value
  -> identify supported format version
  -> validate that version's encoded schema
  -> migrate to the current representation when required
  -> construct the trusted domain value
```

Encode in the opposite direction through an intentional current wire type. Keep domain-only values such as methods, prototypes, brands, `Date`, `Map`, `Set`, and `bigint` out of a JSON contract unless the codec defines their representation.

- Put an explicit version or stable discriminant at an inspectable envelope boundary when independent readers or durable history exist.
- Keep the supported-version policy explicit. Backward or forward compatibility is a requirement to discover, not a default to invent.
- Reject unknown future versions unless the contract defines a safe preservation or forwarding behavior. Never coerce an unknown version into the latest shape.
- Validate the encoded shape before migration and validate or construct the current domain invariant afterward.
- Keep migrations deterministic and free of clocks, network calls, ambient configuration, and unrelated side effects. Pass required context explicitly.
- Decide whether migration happens on read, at startup, in a one-off job, or during a coordinated rollout. Do not accidentally combine strategies.

## 2. Make serialization semantics deliberate

For JSON, account for runtime behavior rather than trusting the TypeScript annotation:

- Object properties whose values are `undefined`, functions, or symbols are omitted; such array elements become `null`.
- `NaN` and positive or negative `Infinity` serialize as `null`.
- `Date` normally becomes a string through `toJSON`; decoding does not restore a `Date` automatically.
- A `bigint` is not JSON-serializable without an explicit representation and codec.
- JavaScript `number` cannot exactly represent every integer. Use a validated decimal string or another specified encoding when values can exceed the safe-integer range.
- Absence, `null`, and an explicit default are different states unless the schema deliberately equates them.
- Do not use ordinary `JSON.stringify` output as a signing, hashing, or equality canonical form unless the protocol specifies canonicalization, ordering, Unicode, and numeric rules.

Choose and document timestamp and duration semantics:

- representation and unit (`epochMs`, seconds, or an ISO/RFC timestamp);
- UTC/offset handling and whether the original offset matters;
- precision and rounding;
- wall-clock instant versus monotonic elapsed time;
- inclusive/exclusive expiry boundaries.

Parse timestamps and large integers at the boundary, reject invalid or out-of-range values, and keep units visible in names or domain constructors.

Sources: [ECMAScript `JSON.stringify`](https://tc39.es/ecma262/multipage/structured-data.html#sec-json.stringify), [ECMAScript `Date.prototype.toJSON`](https://tc39.es/ecma262/multipage/numbers-and-dates.html#sec-date.prototype.tojson), [ECMAScript safe integers](https://tc39.es/ecma262/multipage/numbers-and-dates.html#sec-number.max_safe_integer), [RFC 8259 JSON interoperability](https://www.rfc-editor.org/rfc/rfc8259.html#section-6).

## 3. Evolve schemas intentionally

Before changing a durable or independently consumed schema, inventory:

- existing persisted versions and their volume/lifetime;
- every reader and writer, including old binaries, workers, CLIs, exports, and rollback paths;
- whether readers and writers can be deployed atomically;
- the required rollback, retention, and deletion behavior;
- whether unknown fields must be preserved when data is read and rewritten.

Then choose the smallest strategy that meets those requirements:

- **Breaking clean replacement (Default for internal schemas)**: For internal, ephemeral, process-local, or single-agent schema refactors where multi-version persistence is not required, perform an immediate clean replacement. Update all codecs, call sites, and tests in one change wave. Delete obsolete parsers and schema branches completely.
- **Read-old/write-new**: When multi-version persistence is an explicit requirement, decode supported historical versions, migrate in memory, and emit only the current version.
- **Coordinated migration**: Transform durable data with a replayable, observable job before removing old readers.
- **Rolling compatibility**: Temporarily support an overlap window only when independently deployed readers/writers strictly require it; define the removal gate up front.

### Forbidden legacy retention anti-patterns

Never introduce or retain:
- **Zombie Decoders & Dual-Format Fallbacks**: Do not retain obsolete serialization/deserialization logic, legacy schema parsers, or dual-format fallback decoders alongside new formats unless explicit multi-version persistence requirements demand it.
- **Paranoid Dual-Writing**: Do not mutate both legacy and new stores, fields, payload properties, or endpoints concurrently during single-agent refactors.
- **Preemptive Deprecation Scaffolding**: Do not add `@deprecated` wrappers, runtime fallback branching, or migration scaffolding for internal types when clean in-place replacement is feasible.
- **Ghost Code**: Do not leave commented-out schema decoders or dead parser utilities in the codebase.

An additive field is not automatically compatible. Requiredness, defaults, unknown-field handling, signatures/hashes, validators, and older exhaustive consumers can still break. Renaming a TypeScript property is a wire-format change if the property name is encoded.

## 4. Preserve atomicity and recoverability

- Use the storage system's transaction or atomic replace primitive when a logical record must change as one unit.
- For files, write and validate a temporary sibling, flush when durability requires it, then use the platform's atomic replacement primitive where supported.
- Do not overwrite the only copy before the new representation is known to decode successfully when reversibility matters.
- Make migrations restartable. Record progress or use idempotent transformations rather than assuming a one-shot process cannot fail.
- Keep backups, rollback artifacts, or dual-read logic only when the actual recovery requirement justifies them.
- Report partial migration and unsupported records explicitly; do not silently substitute defaults that turn corruption into plausible data.

## 5. Test the contract independently

Exercise the real codec and persistence/message path with:

- one checked-in golden fixture for every supported historical version;
- the current version, unknown future versions, malformed envelopes, missing fields, extra fields, and truncated data;
- `null` versus absent values, zero/negative/boundary numbers, unsafe integers, non-finite numeric input, Unicode, and maximum accepted sizes;
- timestamp offset, daylight-saving boundary, precision, expiry-boundary, and invalid-date cases when time matters;
- migration restart and repeated execution when a job can be interrupted;
- encode/decode round trips plus independent expected fixtures, because a symmetric bug can pass a round-trip test.

Use property-based testing or fuzzing when the input space is combinatorial, the parser is security-sensitive, or invariants can be stated more clearly than examples. Prefer an existing repository tool; do not add a dependency for a handful of ordinary cases.
