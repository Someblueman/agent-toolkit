# Type Design, Boundaries, and Clean APIs

Use this reference for domain modeling, public APIs, runtime validation, generics, assertions, errors, and maintainable module design. Compiler/build performance is in `performance.md`; module and test configuration is in `tooling-testing.md`.

## 1. Static types stop at runtime boundaries

TypeScript erases type annotations and assertions. Values from JSON, environment variables, CLI arguments, databases, files, messages, plugins, and network calls can violate their declared TypeScript types.

Use one inspectable transition:

```text
unknown external value -> parse/validate -> trusted domain value
```

- Accept `unknown`, not `any`, at the boundary.
- Validate structure and semantic constraints: ranges, formats, mutually dependent fields, allowed values, and size limits—not just `typeof` checks.
- Return or throw a useful boundary error that identifies the source without leaking secrets.
- Keep the rest of the domain free from repeated defensive checks once construction has established the invariant.
- Prefer an existing repository schema library. For a small stable shape, a hand-written guard may be simpler; for nested, reused, coercing, or diagnostic-heavy schemas, a maintained validation library is usually safer. Do not add a dependency without weighing its runtime/bundle cost.
- Test validators with malformed, missing, extra, boundary, and adversarial values. A user-defined type predicate can lie as easily as an assertion.

An opaque/branded scalar is useful when mixing values would be expensive (`UserId` versus `RunId`), but the brand is still erased. Only a validating constructor/parser may create it; never brand raw input with a cast.

Sources: [TypeScript erased types](https://www.typescriptlang.org/docs/handbook/typescript-from-scratch.html#erased-types), [runtime behavior](https://www.typescriptlang.org/docs/handbook/typescript-from-scratch.html#runtime-behavior), [`unknown`](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html#unknown), [narrowing](https://www.typescriptlang.org/docs/handbook/2/narrowing.html).

## 2. Model states so changes become compiler-visible

Prefer a literal discriminant and variant-specific fields:

```ts
type LoadState =
  | { readonly kind: "idle" }
  | { readonly kind: "loading"; readonly startedAtMs: number }
  | { readonly kind: "ready"; readonly value: Payload }
  | { readonly kind: "failed"; readonly error: Error };

function assertNever(value: never): never {
  throw new Error(`unhandled state: ${String(value)}`);
}
```

Use an exhaustive `switch` whose default calls `assertNever`, or assign the residual value to `never`. Adding a variant should fail every handler that needs updating.

Do not encode the same model as `{ loading?: boolean; value?: Payload; error?: Error }`: it permits contradictory and meaningless combinations. Optional properties are correct when absence itself is part of the model. With `exactOptionalPropertyTypes`, `{ x?: T }` distinguishes omission from `x: undefined`; opt into that semantic deliberately.

Use `readonly` to communicate non-assignment through an API. It is shallow and does not freeze the runtime object or prevent mutation through another alias.

Sources: [discriminated unions and exhaustiveness](https://www.typescriptlang.org/docs/handbook/2/narrowing.html#discriminated-unions), [`exactOptionalPropertyTypes`](https://www.typescriptlang.org/tsconfig/exactOptionalPropertyTypes.html), [`readonly`](https://www.typescriptlang.org/docs/handbook/2/objects.html#readonly-properties).

## 3. Choose the simplest type mechanism that preserves the relationship

### Anti-abstraction and concrete-first design

Write concrete logic and types first. Choose the simplest concrete implementation that meets current requirements.

- Prefer concrete code; introduce an abstraction when it simplifies a current requirement or expresses a necessary boundary or invariant.
- **Ban Speculative Generic Helper Abstractions**: Avoid implementing custom type-level metaprogramming libraries or complex recursive utility types (e.g., `DeepPartial`, `NestedKeyOf`, custom type-gymnastics combinators) when standard TypeScript types and concrete functions solve the immediate requirement.
- Choose direct construction, constructors or builders according to validation needs and call-site clarity, not field count.

### Interfaces and aliases

- Prefer `interface` for named object contracts that are extended or implemented. TypeScript can cache interface relationships and reports property conflicts more clearly than large intersections.
- Prefer `type` for unions, tuples, primitives, mapped/conditional types, and aliases.
- Do not convert existing code only for style. Change the form when it improves the model, diagnostics, declaration surface, or measured compiler performance.

### Generics

A useful generic parameter relates two or more positions. If it appears only once, the caller gains no relationship and a concrete type or constraint is usually clearer.

- Push type parameters down: accept `T[]` when the implementation needs elements, rather than parameterizing over an entire array subtype.
- Constrain to the exact capabilities used.
- Let inference choose type arguments unless ambiguity or an intentional public contract requires explicit arguments.
- Prefer a union parameter when all variants return the same type. Use overloads when call shapes differ materially or return types correlate with inputs; keep the implementation signature honest.
- Name and simplify conditional/mapped types that recur. If a type-level program is harder to understand than the runtime behavior, redesign it.

### Literal inference

Use `satisfies` for configuration tables that must conform to a shape while retaining literal keys and values. It checks compatibility but does not validate runtime input. Check the pinned TypeScript version first (`satisfies` requires TypeScript 4.9+).

Sources: [generic function guidelines](https://www.typescriptlang.org/docs/handbook/2/functions.html#guidelines-for-writing-good-generic-functions), [generics](https://www.typescriptlang.org/docs/handbook/2/generics.html), [`satisfies`](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-9.html#the-satisfies-operator), [compiler performance guidance](https://github.com/microsoft/TypeScript/wiki/Performance#writing-easy-to-compile-code).

## 4. Assertions and suppressions are proof obligations

- An `as T` assertion changes only the compiler's view. Put it immediately after the runtime fact or library contract that proves it.
- A non-null assertion (`value!`) is acceptable only when a nearby invariant makes absence impossible and restructuring/narrowing cannot express it more clearly.
- Treat `as unknown as T` as a failed boundary by default. Restrict rare uses to a tiny third-party adapter or a deliberate malformed-value test fixture, with an explanation.
- Use `@ts-expect-error` rather than `@ts-ignore` for a deliberate negative type test. Include a reason and keep it on the exact line; the compiler then reports when the expected error disappears.
- Prefer a narrow local lint suppression with a reason. Never disable a rule for an entire file merely to avoid fixing one expression.

Assertions can be appropriate after a runtime parser, for limitations in an external declaration, or in tests that intentionally construct impossible input. They are not a substitute for modeling or validation.

Sources: [type assertions](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html#type-assertions), [`@ts-expect-error`](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-3-9.html#ts-expect-error-comments).

## 5. Error contracts

JavaScript permits throwing any value, so every catch variable starts as `unknown`.

- Throw `Error` objects, not strings or object literals.
- Preserve the original failure with `cause` when wrapping is useful and supported by the target runtime.
- When adding boundary context such as a file path or operation name, create a contextual error with the original value as `cause`; do not return an existing `Error` unchanged and silently lose that context.
- Distinguish expected recoverable domain outcomes from exceptional failures. Use the repository's established `Result`/discriminated-union style when callers must branch; use exceptions for failures that cross many frames or cannot be handled locally.
- Give stable machine-readable codes/discriminants to failures that callers must classify. Human messages alone are not an API.
- Do not log and rethrow at every layer; choose the boundary that has enough context and owns observability.
- An empty catch is almost always a bug. If best-effort cleanup intentionally suppresses a failure, state why and preserve the primary error.

With `strict`, caught variables use `unknown` on supported TypeScript versions. Do not disable that check.

Sources: [`useUnknownInCatchVariables`](https://www.typescriptlang.org/tsconfig/useUnknownInCatchVariables.html), [Node.js error handling](https://nodejs.org/api/errors.html).

## 6. Flat cohesive architecture and single-path refactoring

Structure TypeScript applications and modules for clarity, directness, and clean evolution:

- **Flat Cohesive Architecture**: Colocate domain models, business logic, validation, and direct database/I/O queries in feature modules rather than scattering across redundant layers.
- **Ban Multi-Layer Passthrough Wrappers**: Do not create ceremonial multi-layer wrapper hierarchies (`Controller -> Service -> Manager -> Repository -> DAO`) where intermediate layers merely forward parameters without adding domain logic, transaction boundaries, or distinct polymorphism.
- **Ban Array and Prototype Monkey-Patching**: Never mutate `Array.prototype`, `Object.prototype`, or third-party prototypes with custom helper methods or monkey-patched utilities. Use standard standalone functions or modern ECMAScript built-in methods.
- **Single-Path Atomic In-Place Refactoring**: When updating an interface, data structure, or function, perform a clean in-place replacement and atomically update all call sites, internal usages, and tests in the same change wave:
  - *No Shim Multiplication*: Do not retain deprecated pass-through forwarding wrappers around new implementations.
  - *No Preemptive Deprecation Staging*: Do not introduce `@deprecated` annotations, feature flags, or staged migration scaffolding when an immediate clean replacement is feasible.
  - *No Ghost Code*: Do not comment out old implementations or leave unused fallback branches in the codebase.
- Keep pure transformation and decision logic separate from clocks, storage, network, process, and UI adapters when a real boundary exists.
- Make dependencies explicit parameters or narrow interfaces when tests or alternate implementations need substitution. Avoid service locators and ambient mutable singletons.
- Keep exported surface area deliberate. Export the domain operation, not every helper needed to implement it.
- Prefer cohesive domain modules over catch-all `utils`, `helpers`, or `common` dumping grounds.
- Extract a function or type when the name exposes a concept, isolates a policy, centralizes an invariant, or removes real duplication—not to satisfy an arbitrary line count.
- Follow repository naming and file conventions. Prefer positive boolean names (`isValid`, `hasLease`, `canRetry`) and include units in numeric names.
- Comments document *why*: external contracts, invariants, ordering, precision, complexity, security, and compatibility constraints. Delete comments that merely paraphrase code.

Use primitive types (`string`, `number`, `boolean`, `symbol`) rather than boxed `String`, `Number`, `Boolean`, or catch-all `Object`/`Function` types.

Source: [TypeScript declaration design do's and don'ts](https://www.typescriptlang.org/docs/handbook/declaration-files/do-s-and-don-ts.html).

## 7. Security boundary checklist

Static types do not establish trust, authorization, sanitization, or resource bounds.

- Validate and size-bound attacker/user-controlled input before expensive work.
- Use parameterized database APIs; never interpolate untrusted values into SQL.
- Pass subprocess arguments as an argument array to a non-shell API where possible; do not build a shell command string.
- Resolve and confine filesystem paths before access when a root boundary matters.
- Do not merge untrusted objects into prototypes/configuration without an allowlist of owned keys.
- Redact secrets and sensitive payloads from errors, logs, snapshots, and fixtures.
- Preserve the repository's explicit authorization and least-privilege boundaries.

Source: [Node.js security best practices](https://nodejs.org/en/learn/getting-started/security-best-practices).
