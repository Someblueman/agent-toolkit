# Local quality checks

Provision actual linters and run repository-defined tests, builds and type checks
automatically through lifecycle hooks. Commands remain available for diagnosis and reruns.
The checker runs locally; it has no GitHub Actions dependency. Python 3.10+ and
macOS/Linux are supported. The Codex adapter uses POSIX file locking.

## Try it

From agent-toolkit:

```sh
tools/quality/bin/quality setup --dry-run
tools/quality/bin/quality setup
tools/quality/bin/quality doctor
tools/quality/bin/quality check
```

The checked-in `quality.json` covers this tool, its Codex adapter, the installer and
leader completion behavior. Historical examples and other skill helpers are not all
covered. Ruff is installed under the ignored `.quality/` directory; Python 3.13.2 is
externally managed for tests. `setup --codex` also registers the shared Codex hooks.

With the hooks active, the first prompt checks project verification setup, tool availability
and declared checks. Relevant edits run Ruff and the installer tests,
including installation of the current packages into a temporary destination. Stop
verifies all automated checks, including the quality and leader completion suites,
with successful results reusable only for identical declared inputs and full selection.
Agents do not have to issue test commands to receive these results.

For another repository, first establish its definition of green as described below.
When a language starter is useful, select its existing tools explicitly:

```sh
/path/to/agent-toolkit/tools/quality/bin/quality --root /path/to/project setup \
  --profile python --profile shell --source src --source scripts --codex --dry-run
# Review the proposal, then repeat without --dry-run.
```

Use one JS profile: `biome` or `eslint`, matching the project's existing toolchain.
Multiple profiles share one source inventory. `--version X.Y.Z` overrides the pin
when selecting a single profile. Once `quality.json` exists, edit its commands and
pins directly; `setup` will not replace it with a newly selected profile.

For a repository that already contains its own `quality.json`, installation on another
machine or repeat installation is one command:

```sh
/path/to/agent-toolkit/tools/quality/bin/quality --root /path/to/project setup --codex
```

This preserves the repository's configuration, provisions its declared tools and
registers hooks only after setup succeeds. Hook conflicts are detected before
provisioning. Select profiles/source roots only for initial configuration; omit them
on subsequent runs. Add `.quality/` to the target repository's ignore rules.

Keep each repository's native test/build commands and dependency inputs in its own
`quality.json`. Do not copy the toolkit's configuration, which tests the toolkit itself.
The shared runner has no dependency on the target repository's language or layout;
the current lifecycle adapter targets Codex on macOS/Linux.

## Define green for the project

`UserPromptSubmit` looks for the current project's configuration, stopping at the nearest
Git boundary. A nested repository cannot inherit its parent's verification policy.
If `quality.json` or its `verification` section is missing, the hook makes setup the first
implementation task. It directs the agent to read that repository's instructions,
development docs, CI and native commands, then record useful acceptance criteria and
run the selected checks to establish a baseline. Read-only requests report missing setup
without authorizing project changes. Outside Git, an explicit `quality.json` identifies
the project; ordinary folders without either remain unaffected.

Add this section to the repository's existing version-1 configuration, alongside the
native commands in `checks`. For example, a game might define:

```json
"verification": {
  "green": "The game builds, existing gameplay regressions pass, and changed controls work in the browser.",
  "manual": ["For gameplay or visual changes, play the affected flow and record the result."]
}
```

`green` describes concrete project acceptance criteria. `manual` lists relevant evidence
that cannot be established by an automated command; use an empty list if none is needed.
The agent/reviewer reports that evidence, justified non-applicability, or unresolved
limitations. The hook cannot certify visual quality or the relevance of a test from an
exit code. Manual-stage commands are also listed as outstanding evidence at Stop.

There is no requirement for a new test, a test count, or a coverage percentage. Use
existing useful tests, builds, type checks, native CLI/browser workflows and proportionate
inspection. Add a test when it catches a plausible failure of the actual change.
Do not weaken existing acceptance checks to make the result green. Starter profiles
only provision language tooling; they deliberately do not generate acceptance claims.

Existing configurations without `verification` still support setup, doctor and explicit
checks. Lifecycle verification reports setup incomplete until the project definition is
present. Hooks do not create the definition, install tools or change repository files.

## What setup provisions

| Profile | Pinned tool | Provisioning and native rules |
|---|---|---|
| python | Ruff 0.16.6 | `uv venv` + exact package under `.quality/ruff`; C901 at 10 and format check. Existing Ruff settings are read; the complexity selection/limit is passed explicitly. |
| biome | Biome 2.5.12 | Existing JS lockfile selects npm/pnpm/Yarn/Bun; exact dev dependency. `quality.biome.json` extends the existing config, overriding cognitive complexity to error at 15. |
| eslint | ESLint 10.10.0 | Exact dev dependency; existing ESLint config/parser and CLI complexity limit 10. Supply the project's flat config and TS parser before checking TS. |
| rust | Rust 1.97.1 | rustup's exact toolchain with rustfmt/Clippy; formatting plus locked, offline Clippy. Select the repository's actual toolchain with `--version`. |
| go | golangci-lint 2.4.0 | `go install` to `.quality/bin`; merge gocyclo 10 and gocognit 15 into native v2 YAML/JSON, preserving unrelated settings and YAML comments. |
| c-cpp | clang-tidy 22.1.8 | Pinned Python distribution under `.quality/clang-tidy`; cognitive limit 15. Adjust the `build` compilation-database path and header/build coverage for the project. |
| haskell | HLint 3.8 | Reuse an installed matching HLint, otherwise exact `cabal install` to `.quality/bin`. No numeric cognitive-complexity claim. |
| shell | ShellCheck 0.11.0 | `shellcheck-py==0.11.0.1` under `.quality/shellcheck`; includes style/info diagnostics such as unquoted expansion. |

Installers (`uv`, a JS package manager, Go, rustup, or Cabal) must already exist.
Missing installers return a setup error; the tool does not install system package managers.
The clang-tidy and ShellCheck Python distributions are third-party packaging of the
native binaries: [clang-tidy-wheel](https://github.com/ssciwr/clang-tidy-wheel) and
[shellcheck-py](https://github.com/shellcheck-py/shellcheck-py). Replace their recipe with
your existing binary path and exact version if preferred.

Setup is the only command that runs installation recipes. Check/doctor run the exact
configured executable, never `npx`, `uvx`, or a download-on-demand fallback. Offline
environment settings also discourage package-manager downloads; these are not a
network sandbox for arbitrary configured commands. Application dependencies must be
provisioned separately for package-level checks such as Clippy.

The version pins identify releases, not a hermetic compiler/OS/dependency environment.
The package managers retain their normal cache/lock behavior. Go installation can need
network access and the appropriate Go compiler; JS package installation updates the
project manifest and lockfile. Inspect the setup dry-run first.

## Repository configuration

`quality.json` is a trusted executable configuration, version 1:

- `verification`: `green` acceptance description and `manual` evidence descriptions.
  Required for lifecycle verification; absent in unconfigured language starters.
- `roots`: explicit files/directories, relative to the repository root.
- `exclude`: repository-relative glob patterns. No blanket exclusion of `packages/`.
- `tools`: executable argument prefix, exact reported version, version arguments and
  explicit installation commands. An empty `install` list means externally managed.
- `checks`: name, tool reference, arguments, source patterns, `fast`/`full`/`manual` stage,
  whether to append matching filenames, and native `failure_codes` (e.g. Cargo 101).
- Optional check `kind`: `lint`, `typecheck`, `test`, `build`, `invariant` or `unspecified`
  (the default for existing configurations). Doctor and automatic preflight use this
  declaration to identify files without an automated behavioral check. This is a
  configuration diagnostic, not measured test coverage or proof of test quality.
- `size`: physical-line threshold and `review` or `error` mode; defaults to advisory 500.

`{root}` expands to the absolute repository path. Commands are argument arrays; shell
expansion is not performed. Filenames are passed with `./` prefixes. Native tools read
their ordinary configuration, including intentional exclusions/suppressions. Review
those settings: a file being passed to a tool does not prove every rule applied to it.

Known source extensions without a matching configured check fail as unavailable. Add
explicit patterns for extensionless scripts or other source formats; source discovery
does not infer every possible language. Empty inventories and empty check selections
also fail. Symlinked source/config paths are rejected. Generated/vendor exclusions must
be declared explicitly; non-source documents in the roots are not linted as code.

The size check counts LF/CRLF physical lines, including comments and blanks, and an
unterminated final line. It does not compute SLOC or parse inline test modules. Halstead
and universal cognitive metrics are not implemented; native coverage is explicit.

`check --fast` runs fast checks; `check` runs every stage, including manual checks.
Register existing focused tests and type checks as `fast`, and broader acceptance
as `full`, with their own tool/version entries. Use `scope: project`, `files: false`
for a suite, and declare its source, test, fixture, configuration and lockfile inputs.
Inputs outside `roots` are supported. Deletions and executable-bit changes also
invalidate results. Starter profiles provide linting; they do not guess behavioral
tests, feature matrices or test directories. Compiler/build failures use each check's
declared exit-code convention.

For example, with `src` and `tests` in `roots` and an externally managed `python-runtime`
tool configured for the repository's interpreter, this check runs automatically at Stop:

```json
{
  "name": "Application behavior",
  "kind": "test",
  "tool": "python-runtime",
  "args": ["-m", "unittest", "discover", "-s", "tests", "-v"],
  "patterns": ["src/*.py", "tests/*.py"],
  "inputs": ["fixtures/*", "pyproject.toml", "uv.lock"],
  "files": false,
  "scope": "project",
  "stage": "full",
  "failure_codes": [1]
}
```

Use deterministic fixtures and declare all relevant inputs before reusing results.
Tests that depend on untracked external service state cannot establish a reusable
source-based result; provide a reproducible local fixture or retain explicit validation
for that external boundary.

The checker detects source/configuration changes during a run rather than recording a
pass for an unstable snapshot. Each command has a 120-second timeout, with process-group
cleanup; use a repository-specific bounded command for a different workload. Split
long suites into focused targets or provide local fixtures so required acceptance
can fit within the hook budget.

Exit codes: **0** = configured checks passed (size review findings may remain);
**1** = native check/build failure or a strict size violation; **2** = unavailable tool,
wrong version, invalid configuration, empty coverage, launch failure or timeout.
Doctor validates configured tools/versions and inventory, lists each stage and check
kind, and reports missing behavioral declarations. It is not a native rule conformance
test. The real-tool boundary tests below provide that additional evidence.

## Codex integration

```sh
quality --root /path/to/project install-codex --dry-run
quality --root /path/to/project install-codex
# Optional: register project setup and verification hooks once for all repositories.
quality install-codex --global --dry-run
quality install-codex --global
```

Use the full executable path above if `quality` is not on PATH. This merges a command
adapter into the project's `.codex/hooks.json`, preserving other events and handlers.
`--global` targets `$CODEX_HOME/hooks.json` (default `~/.codex/hooks.json`) and needs
no project configuration. Project installation reuses matching user-level JSON
registrations and adds only missing events. Existing project handlers are preserved;
pre-existing duplicates are not removed. Duplicate detection covers these two JSON
files; inline TOML, plugins and managed sources remain visible through Codex `/hooks`.
Reinstallation is idempotent; a different existing quality adapter causes a conflict
instead of being overwritten. The command references this checkout with an absolute
path. Keep the checkout at that location or review/update the hook command after moving it.
It does not change feature flags, permissions, hook trust or enablement. Registration
does not establish runtime activation: review the configured sources in Codex `/hooks`.
Keep one enabled registration for each event. This follows the
[Codex registration and trust contract](https://learn.chatgpt.com/docs/hooks).

- `UserPromptSubmit` checks for project-specific verification setup first, then performs
  preflight on the first prompt in a session and after
  quality configuration, source inventory, checker or tool changes. All tools required by automated
  checks must be available, including tools for currently untouched languages.
  Successful preflight is reused while those inputs remain unchanged. It does not
  execute tests/builds or install dependencies.
- The prompt records the initial source/config baseline. Later steering prompts
  preserve edits that are still awaiting completion checks.
- `PostToolUse` checks the source inventory after Bash/patch events when content changed,
  using fast checks. Identical content isn't checked repeatedly.
- `Stop` verifies all configured fast and full checks across the full inventory.
  The initial prompt snapshot is not evidence of passing checks. Valid successful
  results for identical inputs and full selections may be reused. A violation asks
  Codex to continue once. Persistent failure remains unresolved and is reported without
  an endless repair loop; it never becomes a successful baseline.
- Missing tools, invalid configuration, timeouts, busy locks and changing snapshots
  cannot pass completion. Stop requests one retry; `stop_hook_active` continuations
  report a blocker if checking still cannot finish. Post-tool events report the issue
  for the next eligible event. There is no automatic installation.
- Read-only turns can establish the first verified baseline at Stop. Later unchanged
  events reuse valid results. Pre-existing violations are not
  automatically grandfathered; feedback explicitly limits repairs to authorized scope.

The adapter uses per-session state under `~/.cache/agent-toolkit/quality` (override with
`QUALITY_HOOK_STATE_DIR` for tests). This is a cache, not an acceptance certificate. Hooks
outside Git or a directory containing `quality.json` are inert. Missing setup in a
Git repository prompts onboarding and reports incomplete verification at Stop. The final check reconciles
the configured inventory, so shell edits do not have to be inferred from command text.

Codex requires review/trust of new or changed hooks; installation does not establish it.
The adapter follows the [official Codex hook contract](https://learn.chatgpt.com/docs/hooks).
Post-tool feedback cannot undo an edit. Local hooks are guardrails, not an unbypassable
security boundary. Hook activation and trust are separate from protocol verification.

## Verification

```sh
python3 -m unittest discover -s tools/quality/tests -v
QUALITY_NATIVE=python,biome,eslint,rust,go,c-cpp,haskell,shell \
  python3 -m unittest discover -s tools/quality/tests -v
tools/quality/bin/quality check
```

The first command uses real subprocess fixtures without downloads. The second provisions
real linters in temporary directories and needs the installers above; HLint reuses the
installed matching version. It checks actual lint failures and Python/Biome/Go/C numeric
boundaries, plus the real Ruff-to-Codex JSON feedback path. Cabal's fallback installation
and a live Codex desktop turn are not covered by these tests. Hook protocol tests cover
read-only turns, missing tools, retry bounds, repair, idempotence and existing-hook conflicts.

### Local outcome log

Recognized projects append one JSON record per hook invocation under
`~/.cache/agent-toolkit/quality/<sha256-of-repository-path>.jsonl` (or
`QUALITY_HOOK_STATE_DIR`). Records contain UTC time, event, hashed session ID,
duration in milliseconds, checked/skipped status, pass/fail/cached/setup-error outcome,
check stage when applicable, and whether Stop blocked. They contain no source,
command output, or repository path. Logging failures do not alter hook behavior.
These local logs accumulate until removed; they are not uploaded. Aggregate
checked outcomes separately from skipped events, and exclude deliberate trials
when assessing organic catches and repair rates. `cached` means a previous successful
result was reused for identical selected inputs; `skipped` establishes no new result.
The `preflight` flag records successful availability checks separately from executed tests.
`setup_required` means the project definition is missing; `manual_required` means
automated verification cannot establish the remaining declared manual criteria.

### Reporting and concurrent edits

Check results begin with pass/fail summaries, with failed checks first. Long
command output keeps initial and final excerpts; failures show the final excerpt
first so end-of-run regression findings remain visible. Complete long output is
saved with private file permissions under `~/.cache/agent-toolkit/quality/reports/`.
Unlike the metadata-only outcome log, these reports contain raw tool output and
may include source excerpts. They stay local until manually removed.

Concurrent source/configuration changes produce `snapshot_changed` in the outcome
log and a retry-on-stable-sources message, not `setup_error`. The CLI retains exit
code 2 for an inconclusive check. No pass or fast-check cache entry is recorded,
and post-tool events recheck on the next eligible event. At Stop, an inconclusive result
requests one retry before reporting a blocker. Missing tools and genuine setup failures
still report `setup_error`.


### Incremental lifecycle checks and worktrees

Post-tool hooks compare content against the turn baseline and pass only changed files to
file-based checks. This covers Ruff, Biome, ESLint, ShellCheck and HLint. New and
untracked sources are included. Deletions and changes to native configuration,
lockfiles, checker commands or quality policy invalidate the affected scope.
Stop selects every configured source for every automated check, including unchanged
components. Successful full-selection results can be reused at Stop; a cached pass
on a subset cannot certify a larger selection. Failed results are never cached as passes.
Explicit `quality check` always checks the full configured inventory without this cache.
A quiet hook is not proof of meeting every product requirement or manual criterion.

Optional check fields in version 1:

- `scope`: `files` (default with `files: true`), `project` (default otherwise), or
  `translation-units`. Project commands keep their native package/workspace semantics.
  C translation-unit checks select changed C/C++ sources; header changes select all
  configured translation units. File scopes require `files: true`.
- `inputs`: checkout-relative glob patterns for configuration and other dependencies,
  including paths outside `roots`. A matching change selects all files for that check.
  Omission uses conservative common native-config patterns. Literal paths may include
  generated inputs such as `build/compile_commands.json`. Declare custom configs,
  sourced shell libraries and external checker dependencies here.
- `stage: manual`: excluded from lifecycle hooks, retained by explicit `quality check`.
  The C starter keeps full clang-tidy here and uses only cognitive complexity in hooks.
- `{files}` in command arguments: insert selected filenames at this position instead
  of appending them, for commands with trailing compiler arguments.

Rust formatting/Clippy and Go checks retain project scope and native build caches;
small-edit latency depends on project size and cache warmth. Use `scope: project`
for JS rules with cross-file effects or HLint configurations with shared CPP inputs,
and declare relevant dependency files. A one-to-two-second target is realistic for
ordinary file linting, not a guarantee for builds or broad configuration/header edits.

State and locks are keyed by the resolved checkout path, not Git's common directory.
Linked worktrees have independent baselines, success caches and locks. Concurrent
sessions in one checkout receive a busy/retry result instead of running duplicate
checks. A busy result is not a pass. Source changes during checking also require retry.

Each worktree needs its own `quality.json`, provisioned tools/dependencies and hook
registration (`quality --root /path/to/worktree setup`, then `install-codex`). Tracked
configuration follows Git normally; ignored `.quality`, build and node_modules
folders do not. Missing tools are reported without borrowing another checkout's tools
or installing anything during a hook. Global hook registration is not required or
changed. Logs include selected file and reused-check counts when applicable.
