# Targets, Build Scripts, and Portability

Read this for `build.rs`, generated code, native dependencies, cross-compilation, `no_std`, target-specific APIs, paths and OS strings, or portability review. FFI ownership and ABI rules belong in `memory-layout.md`; build-time measurement in `performance.md`; platform CI scope in `tooling-ci.md`.

## Separate host from target

Cargo builds and runs build scripts, procedural macros, and their dependency graphs for the host. Dependencies of the target artifact are compiled for the selected target; one package can therefore be built more than once for different roles.

- In `build.rs`, `cfg!` and `#[cfg]` describe the host build-script binary. Read `TARGET`, `HOST`, and `CARGO_CFG_*` inputs when deciding how to configure the target artifact. See [Cargo build-script inputs](https://doc.rust-lang.org/cargo/reference/build-scripts.html#inputs-to-the-build-script).
- Keep host tools in build dependencies and target libraries in normal dependencies. Do not apply target linker flags to host build scripts or proc macros through broad environment configuration.
- Configure native compilers, assemblers, and linkers for the target triple. The host's default `cc` is not necessarily a valid cross compiler; prefer the repository's established native-build abstraction.
- `cargo check --target ...` checks target type-correctness for the selected scope but does not establish linking, startup, tests, or runtime behavior. Run on the target, a configured runner, an emulator, or representative hardware when the support promise requires it.

## Build-script discipline

- Avoid a build script when static checked-in data or ordinary Cargo configuration is simpler. When one is required, keep it small, deterministic, and explicit about inputs and outputs.
- Write generated files and intermediate artifacts only beneath `OUT_DIR`; do not rewrite `src`, the manifest, lockfile, fixtures, or other checked-in files during a build. Do not assume `OUT_DIR` starts empty.
- Emit precise `rerun-if-changed` and `rerun-if-env-changed` instructions. Use the directive spelling supported by the repository's MSRV: `cargo::KEY=VALUE` requires Cargo 1.77, while older Cargo versions use `cargo:KEY=VALUE`. Without rerun instructions, Cargo may conservatively scan the package and rerun unnecessarily. Do not use `rerun-if-env-changed` for Cargo-provided values such as `TARGET`. See [Cargo build-script outputs and instructions](https://doc.rust-lang.org/cargo/reference/build-scripts.html#outputs-of-the-build-script).
- Register expected custom configuration names and values with `cargo::rustc-check-cfg` before emitting `cargo::rustc-cfg`, subject to the repository's MSRV. Keep configuration names namespaced enough to avoid accidental collisions.
- Preserve the required order of link arguments: Cargo preserves build-script instruction order, which can affect linker resolution. Keep native library discovery and fallback behavior observable in verbose build output.
- Cooperate with Cargo's jobserver when invoking parallel native tools; maintained helpers such as `cc` commonly handle this. Do not multiply Cargo jobs by an independent unbounded worker count.
- Avoid network access during a normal build. Fetch and verify external inputs in an explicit preparation or vendoring step, then make the build consume pinned local artifacts.
- Never print secrets or sensitive environment values as Cargo warnings. Make failures actionable without dumping the full environment or command line.

## Generated code and native dependencies

- Decide deliberately whether generated output is checked in or produced at build time. Checked-in output needs a reproducible regeneration command and drift check; build-time output needs deterministic inputs, package inclusion, and target-aware validation.
- Include generated Rust through a path rooted at `OUT_DIR`. Keep generated APIs behind a hand-written module boundary when that improves documentation, lint control, and compatibility review.
- Record or pin generator and native-tool versions when their output affects correctness, ABI, MSRV, or reproducibility. Stable inputs do not guarantee stable output across generator versions.
- For bindings, verify headers, defines, target layout, allowlists, calling conventions, and link behavior. `bindgen` or `cbindgen` automates syntax; it does not prove ownership, thread safety, ABI availability, or semantic compatibility.
- Inspect `cargo package --list` and compile the packaged artifact when generation depends on files that registry packaging rules might omit.

## `no_std` and capability layering

`#![no_std]` selects the `core` prelude and stops automatic `std` linkage; it does not prevent this crate or a dependency from explicitly requiring `std`.

- Define the actual support tiers: `core` only, `core + alloc`, or `std`. Gate capabilities such as filesystem, networking, threads, and allocation instead of scattering target-name checks throughout domain logic.
- Keep features additive. A conventional optional `std` feature may add integrations and richer capabilities; avoid making the same API silently change core semantics between feature sets.
- Bring `alloc` into scope explicitly when the supported target provides an allocator. Libraries should not install a global allocator or panic handler unless that is their explicit artifact role.
- Check dependency feature defaults. One transitive unconditional `std` dependency can invalidate the advertised target even when the local crate compiles with `--no-default-features` on the host.
- Test the promised configuration with its real target and feature set, for example a scoped `cargo check --no-default-features --target ...`. A host-only build with a synthetic `cfg` is not equivalent.
- Preserve the repository's MSRV when using APIs that have moved from `std` into `core`, or when adopting target and Cargo features introduced in newer toolchains.

See the [Rust Reference on `no_std`](https://doc.rust-lang.org/reference/names/preludes.html#the-no_std-attribute).

## Platform data and target capabilities

- Accept paths as `&Path` or `PathBuf` and OS values as `&OsStr` or `OsString`. Do not require UTF-8 merely for logging or command invocation; use lossy display only at a human-facing boundary where replacement is acceptable.
- Do not assume path separators, case sensitivity, executable suffixes, newline conventions, or filesystem rename and locking semantics transfer across operating systems.
- Treat `usize`, pointer width, endianness, alignment, and available atomic widths as target properties. Use checked conversions and `cfg(target_has_atomic = ...)` or an appropriate fallback for promised targets.
- Centralize platform-specific implementations behind a common contract. Prefer capability-based `cfg` conditions when they express the need; keep unsupported targets as explicit compile errors only when the support policy warrants it.
- Distinguish compilation coverage from behavioral coverage. Cross-target checks find missing symbols and `cfg` mistakes; only execution exposes many filesystem, process, signal, timing, and ABI differences.

## Verification checklist

1. Which code runs on the host, and which artifact runs on the target?
2. Are all build-script inputs, outputs, rerun triggers, and generated-file locations explicit?
3. Can the build run deterministically without network access or repository mutation?
4. Do native tools and headers describe the target rather than the host?
5. Which `core`, `alloc`, `std`, OS, architecture, and atomic capabilities does the public contract promise?
6. Does validation compile, link, package, and run the exact promised target/feature combinations in proportion to risk?
