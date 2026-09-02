# Project Configuration, Modules, Tooling, and Tests

Use this reference for `tsconfig`, package/module boundaries, declaration output, lint/format setup, tests, dependencies, and CI. The repository's existing tools and scripts remain authoritative.

## 1. Discover before configuring

Identify:

- package manager from the lockfile and `packageManager` field;
- runtime and version range from `engines`, runtime configuration/lockfiles, CI, deployment files, and test commands;
- application versus published library versus mixed workspace;
- ESM/CJS/bundler behavior from `package.json`, file extensions, compiler settings, and actual launch command;
- whether `tsc` emits, another tool transpiles, or TypeScript is run directly by a loader;
- the active config from `tsc --showConfig`, including inherited settings and references;
- generated files and declaration ownership;
- canonical type-check, lint, format, test, build, and public-run commands.

Do not infer the runtime from `target`, or the module loader from import syntax alone. TypeScript can accept combinations that the deployed runtime or package consumer cannot execute.

## 2. Compiler configuration

### Safety baseline

- New projects: enable `strict`.
- Existing projects: preserve `strict`; migrate additional flags as deliberate scoped work, not incidental churn.
- Consider `noUncheckedIndexedAccess` when dynamic key/index reads are common.
- Consider `exactOptionalPropertyTypes` when omission differs from explicit `undefined`.
- Use `noImplicitReturns`, `noImplicitOverride`, and fallthrough checks when they fit the codebase's contracts.
- Use `isolatedModules` when each file is transpiled independently by Babel, SWC, esbuild, or another single-file tool.
- Use `verbatimModuleSyntax` in modern projects when explicit type/value imports and faithful module emit fit the toolchain. It can correctly expose a mismatched ESM/CJS setup.

Do not enable a flag and then blanket-suppress its findings. Either complete a bounded migration or propose it separately.

Sources: [`strict`](https://www.typescriptlang.org/tsconfig/strict.html), [`noUncheckedIndexedAccess`](https://www.typescriptlang.org/tsconfig/noUncheckedIndexedAccess.html), [`exactOptionalPropertyTypes`](https://www.typescriptlang.org/tsconfig/exactOptionalPropertyTypes.html), [`isolatedModules`](https://www.typescriptlang.org/tsconfig/isolatedModules.html), [`verbatimModuleSyntax`](https://www.typescriptlang.org/tsconfig/verbatimModuleSyntax.html).

### Module/runtime alignment

| Deployment | Direction |
|---|---|
| Node executes emitted JS directly | Use the Node module/resolution mode matching the supported Node runtime; honor package `type` and required relative extensions |
| Bundler-owned browser/application build | Bundler resolution may be appropriate; verify with the actual bundler |
| Deno, Bun, edge worker, or another direct runtime | Use that runtime's resolver, globals, permissions, and test command; do not infer Node compatibility from a successful type-check |
| Published npm library | Model the consumers you support; verify exports, declarations, ESM/CJS conditions, and a packed/consumer install |
| Direct TS loader | `noEmit` may be valid, but execute tests/CLI through that exact loader |

Do not use bundler resolution to make a Node-published library type-check if Node consumers cannot resolve the same imports. Prefer `import type`/`export type` for type-only edges. Avoid new namespaces in module-based code.

Sources: [TypeScript module theory](https://www.typescriptlang.org/docs/handbook/modules/theory.html), [module resolution](https://www.typescriptlang.org/tsconfig/moduleResolution.html), [Node packages](https://nodejs.org/api/packages.html), [type-only imports/exports](https://www.typescriptlang.org/docs/handbook/modules/reference.html#type-only-imports-and-exports).

## 3. Package and declaration hygiene

- Applications may keep their package surface private. Do not add `exports` or declaration machinery speculatively.
- Libraries define a deliberate public surface. `exports` encapsulates subpaths and can break prior deep imports; enumerate intended entry points and matching type declarations.
- Test the packed artifact or an isolated consumer, not only source imports inside the monorepo.
- Inspect generated `.d.ts` files for leaked private types, enormous inferred signatures, incorrect module paths, and unintended globals.
- Keep runtime dependencies in `dependencies` and build/test-only tools in `devDependencies`; follow the package manager's workspace conventions.
- Use the lockfile's frozen/clean install mode in CI. For npm, `npm ci` validates the lockfile and does not rewrite it.
- Add dependencies only when they remove more complexity/risk than they introduce. Prefer an already-installed maintained library over parallel custom machinery.

Sources: [Node package exports](https://nodejs.org/api/packages.html#exports), [TypeScript declaration publishing](https://www.typescriptlang.org/docs/handbook/declaration-files/publishing.html), [`npm ci`](https://docs.npmjs.com/cli/commands/npm-ci).

## 4. Linting and formatting

The compiler owns type correctness. Linting catches semantic hazards and conventions; formatting owns whitespace. Do not make them substitutes for one another.

- Use the existing configuration first. Do not add a linter/formatter during an unrelated feature.
- For a requested new ESLint setup, prefer current flat config and typescript-eslint maintained presets; never enable `all` wholesale.
- Typed linting can catch floating promises, unsafe `any` use, and incorrect async callbacks, but it builds TypeScript program state and costs more. Use `recommendedTypeChecked`/appropriate maintained presets with `projectService` when that value justifies the cost.
- Scope typed linting to files in the intended project. Exclude generated/build/vendor artifacts. Keep default-project exceptions small.
- Adopt stricter or stylistic presets selectively; their stability and opinions differ. Fit the repository rather than rewriting it to a preset.
- Keep suppressions on the narrowest node/line with a concrete reason. Prefer `@ts-expect-error` for intentional compiler-negative tests.
- Run the configured formatter and accept it. Avoid format churn outside touched code unless reformatting is the task.

Sources: [ESLint configuration files](https://eslint.org/docs/latest/use/configure/configuration-files), [typescript-eslint shared configs](https://typescript-eslint.io/users/configs/), [typed linting](https://typescript-eslint.io/getting-started/typed-linting/), [typed-lint performance](https://typescript-eslint.io/troubleshooting/typed-linting/performance/).

## 5. Testing strategy

Choose the smallest test that observes the changed contract, then cover the public path affected by the change.

| Change | Evidence |
|---|---|
| Pure domain rule | Focused unit tests including boundary/invalid cases |
| Parser or validator | Valid, malformed, missing, extra, adversarial, and size-bound inputs |
| Durable or wire schema | Golden fixtures for supported versions, unknown/malformed versions, migration output, serialization edges, and the real persistence/message path |
| Storage/network/process adapter | Integration test against the real adapter or a faithful local substitute |
| Async lifecycle | Rejection, cancellation, timeout, cleanup, late event, and no-leak assertions |
| Retryable effect or shared-state update | Duplicate and concurrent attempts, timeout before/after commit, conflict handling, restart/reconciliation, and observable effect count |
| Public library types | Declaration build plus consumer/type tests; intentional errors use `@ts-expect-error` |
| Module/package config | Actual runtime entry and isolated package consumer/import |
| CLI/server/browser flow | Public command/request/render path, not only internal mocks |
| Performance change | Same before/after workload plus correctness gates |

Prefer fakes at explicit ports over mocking implementation internals. Tests should remain deterministic, isolated from developer credentials/network by default, and clean up temporary state in `finally`/test hooks.

With Node's built-in test runner, import from `node:test` and `node:assert/strict`, await async tests and nested subtests, and preserve the repository's suite partitioning. Do not switch frameworks without a concrete requirement.

### TDD calibration and anti-bloat

- **Calibrate Coverage to Requirement Scope**: Write focused, high-signal tests that verify specified behavior and direct failure boundaries. Avoid speculative test permutation matrices and combinatorial sprawl across permutations that provide zero marginal failure signal.
- **No Redundant Smoke Tests**: Do not create repetitive smoke tests that merely duplicate unit assertions or re-verify simple property getters.
- **Avoid Deep Mocking**: Prefer fakes at explicit ports or in-memory lightweight adapters over deep mocking of internal structs, classes, or private functions. Deep mocking couples tests to ephemeral refactor details and obscures real integration breakages.

Sources: [Node test runner](https://nodejs.org/api/test.html), [`@ts-expect-error`](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-3-9.html#ts-expect-error-comments).

## 6. Tiered verification

Structure verification into distinct tiers according to the risk and scope of the change:

### Tier 1: Fast-Path (TDD & Localized Edits)

During active TDD iteration, bug fixes, localized feature additions, or internal helper refactoring, run ONLY the targeted test runner and fast typecheck:

- **Vitest**:
  ```bash
  vitest run <path/to/test.ts> -t "<pattern>"
  ```
- **Jest**:
  ```bash
  jest <path/to/test.ts> -t "<pattern>"
  ```
- **Node built-in test runner**:
  ```bash
  node --test --test-name-pattern="<pattern>" <path/to/test.ts>
  ```
- **Targeted typecheck**:
  ```bash
  tsc -p <tsconfig.json> --noEmit
  # Or root no-emit:
  tsc --noEmit
  ```

Do not run whole-workspace test suites, heavy integration benchmarks, or global linters on every cycle of localized TDD edits.

### Tier 2: Full Verification (Architectural / Boundary Changes)

For architectural refactors, schema migrations, public library API changes, authentication/authorization changes, or before final handoff:

1. Full type-check across all workspace projects (`tsc --build` or `tsc -p tsconfig.json --noEmit`);
2. Full test suite execution across all test files and integration suites;
3. Configured lint and format checks (`eslint .`, `prettier --check .`);
4. Generated declaration/bundle builds (`npm run build`, `tsc --emitDeclarationOnly`);
5. Real runtime entry point execution (CLI invocation, server launch, browser bundle, or packed package consumer import).

A type-check does not prove runtime validation, a unit test does not prove package resolution, a lint pass does not prove behavior, and a source-tree import does not prove the published artifact.
