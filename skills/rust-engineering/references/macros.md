# Macros

Read this for `macro_rules!`, procedural macros, derives, attributes, generated syntax, hygiene, spans, or macro diagnostics. Public API compatibility belongs in `api-design.md`; compile-fail harnesses and CI in `tooling-ci.md`; build-host and target behavior in `targets-build.md`.

## Decide whether a macro is the right boundary

- Prefer a function, trait, generic, or ordinary derive when Rust syntax already expresses the operation. A macro is justified when the caller must generate syntax, repeat syntax-shaped input, define items, or inspect tokens at compile time.
- Use `macro_rules!` when token matching and transcription express the grammar without a compiler plugin and its extra crate, build time, and maintenance surface.
- Use a procedural macro for function-like token transformations, custom derives, or attributes that require parsing and generating arbitrary token streams. Keep reusable domain logic in an ordinary library crate so it can be tested without invoking the compiler.
- Treat accepted input forms, expansion semantics, generated names and visibility, required trait bounds, diagnostics, and feature/edition behavior as part of a public macro's contract.

## Declarative macros

- Match with the narrowest fragment specifier that represents the input. Avoid accepting arbitrary `tt` sequences when the macro relies on expression, type, path, item, or pattern structure.
- Remember that the edition of the macro definition controls relevant fragment behavior. Review `expr`/`expr_2021` and `pat`/`pat_param` choices when changing editions or maintaining cross-edition callers. See the [Reference on macro metavariables](https://doc.rust-lang.org/stable/reference/macros-by-example.html#metavariables).
- In exported macros, use `$crate` for helpers owned by the defining crate. `$crate` does not bypass visibility, so any helper reached from an external expansion must still be accessible. Prefer explicit paths over requiring callers to import incidental names.
- Evaluate caller expressions exactly as the API promises. Do not duplicate an expression with side effects or move a captured value more than once. Use an expression block and hygienic local bindings when one evaluation is required.
- Keep generated items and imports from colliding with the caller's namespace. Limit their scope, use deliberately obscure private names where hygiene cannot help, or move helpers into the defining crate.
- Order rules from specific to general and produce an intentional fallback error when that improves diagnostics. The expander commits to the first successfully matched rule; it does not retry later rules after transcription fails.
- Avoid recursive token munching when a clearer repetition or procedural parser is more maintainable. If recursion is necessary, test realistic upper bounds and do not raise recursion limits globally without understanding compile-time cost.

## Procedural macros

Procedural macros are unhygienic: their output behaves as caller-adjacent source. Resolve names and spans deliberately.

- Parse token streams as Rust syntax rather than converting the entire input to a string. Preserve useful input spans through transformations and attach errors to the token that callers can act on.
- Return compiler errors for invalid user input instead of panicking. A panic can remain appropriate for a genuinely impossible internal invariant, but it is not an input-validation strategy.
- Prefer qualified paths in generated code and account for dependency renaming, facade re-exports, `no_std`, and supported editions. Test expansion from a downstream fixture crate rather than only inside the defining workspace.
- Generate the smallest code required. Avoid hidden allocations, repeated evaluation, surprising control flow, private-trait leakage, or stronger bounds than the source contract needs.
- Keep expansion deterministic. Do not depend on network access, wall-clock time, unordered filesystem traversal, or ambient environment unless that input is an explicit documented contract with rebuild tracking.
- Treat filesystem and process access as supply-chain-sensitive. A procedural macro executes on the build host with the compiler process's permissions.
- Use established parsing and quoting libraries when their dependency and compile-time cost are justified. Do not recreate a partial Rust parser for arbitrary syntax.

## Diagnostics and review

- Prefer one primary error at the most relevant span, with additional errors when they reveal independent actionable problems. Preserve compiler type errors when they are clearer than a custom message.
- Inspect expanded code when diagnosing hygiene or generated bounds, but do not treat expansion inspection as a correctness test.
- Review macro changes for semver effects: newly accepted or rejected syntax, changed expansion types, generated visibility, trait implementations, name resolution, evaluation count, diagnostics, and MSRV or edition requirements.
- Keep documentation examples small and compilable. Show the resulting caller-visible behavior, not a large dump of generated code.

## Verification

Use the smallest set justified by the macro's contract:

1. Unit-test parsing and generation logic that lives in ordinary functions.
2. Add downstream-style compile-pass tests for supported forms, editions, features, crate renaming, and `no_std` where promised.
3. Add compile-fail/UI tests for rejected forms and verify that the intended diagnostic points at the useful token.
4. Run behavioral tests against the expanded API, including expression side effects, ownership, and generated trait bounds.
5. Check the declared MSRV and package contents; a proc-macro workspace split or generated fixture may behave differently after publication.

Choose an existing UI harness when present. `trybuild` is a reasonable project dependency when snapshot-based compiler diagnostics fit the maintenance policy, but it is not mandatory. Normalize or update expected diagnostics deliberately across supported compiler versions.
