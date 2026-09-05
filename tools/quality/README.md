# Local quality checks

Provision actual linters, enable complexity rules, and feed findings back to Codex.
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

The checked-in `quality.json` deliberately covers this new tool and its Codex adapter,
not every historical example or skill in the toolkit. Ruff is installed under the
ignored `.quality/` directory. Setup does not install Codex hooks.

For another repository, select its existing language tools explicitly:

```sh
/path/to/agent-toolkit/tools/quality/bin/quality --root /path/to/project setup \
  --profile python --profile shell --source src --source scripts --dry-run
# Review the proposal, then repeat without --dry-run.
```

Use one JS profile: `biome` or `eslint`, matching the project's existing toolchain.
Multiple profiles share one source inventory. `--version X.Y.Z` overrides the pin
when selecting a single profile. Once `quality.json` exists, edit its commands and
pins directly; `setup` will not replace it with a newly selected profile.

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

- `roots`: explicit files/directories, relative to the repository root.
- `exclude`: repository-relative glob patterns. No blanket exclusion of `packages/`.
- `tools`: executable argument prefix, exact reported version, version arguments and
  explicit installation commands. An empty `install` list means externally managed.
- `checks`: name, tool reference, arguments, source patterns, `fast`/`full` stage,
  whether to append matching filenames, and native `failure_codes` (e.g. Cargo 101).
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

`check --fast` runs fast checks; `check` runs both stages. Add the repository's existing
type checks and invariant tests as full-stage commands with their own tool/version
entries. The starter profiles do not guess acceptance tests, feature matrices or test
directories. Compiler/build failures use each check's declared exit-code convention.

The checker detects source/configuration changes during a run rather than recording a
pass for an unstable snapshot. Each command has a 120-second timeout, with process-group
cleanup; use a repository-specific bounded command for a different workload. Long test
suites are better invoked explicitly until their duration fits the hook budget.

Exit codes: **0** = configured checks passed (size review findings may remain);
**1** = native check/build failure or a strict size violation; **2** = unavailable tool,
wrong version, invalid configuration, empty coverage, launch failure or timeout.
Doctor validates configured tools/versions and inventory; it is not a native rule
conformance test. The real-tool boundary tests below provide that additional evidence.

## Codex integration

```sh
quality --root /path/to/project install-codex --dry-run
quality --root /path/to/project install-codex
```

Use the full executable path above if `quality` is not on PATH. This merges a command
adapter into the project's `.codex/hooks.json`, preserving other events and handlers.
Reinstallation is idempotent; a different existing quality adapter causes a conflict
instead of being overwritten. The command references this checkout with an absolute
path. Keep the checkout at that location or review/update the hook command after moving it.
It does not change the global Codex installer, feature flags, permissions or hook trust.

- `UserPromptSubmit` records the source/config baseline for this turn.
- `PostToolUse` checks the source inventory after Bash/patch events when content changed,
  using fast checks. Identical content isn't checked repeatedly.
- `Stop` runs full checks when content changed. A violation asks Codex to continue once.
  Persistent failure is then reported without an endless repair loop.
- Setup errors are reported as unavailable, never passed and never an automatic install.
- Read-only turns with unchanged content remain inert. Pre-existing violations are not
  automatically grandfathered; feedback explicitly limits repairs to authorized scope.

The adapter uses per-session state under `~/.cache/agent-toolkit/quality` (override with
`QUALITY_HOOK_STATE_DIR` for tests). This is a cache, not an acceptance certificate. Hooks
outside a repository containing `quality.json` are inert. The final check reconciles
the configured inventory, so shell edits do not have to be inferred from command text.

Codex requires review/trust of new or changed hooks; installation does not establish it.
The adapter follows the [official Codex hook contract](https://learn.chatgpt.com/docs/hooks).
Post-tool feedback cannot undo an edit. Local hooks are guardrails, not an unbypassable
security boundary. No live desktop hook was enabled by this implementation session.

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
