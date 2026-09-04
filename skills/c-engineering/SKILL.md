---
name: c-engineering
description: Implement, review, debug, and optimize C programs, libraries, and systems. Use for C source (.c/.h), memory arenas, pointer safety, bounded buffers, opaque structs, C11 atomics, SIMD intrinsics, sanitizers, and Make/CMake/Meson build systems.
---

# C Systems Engineering

Produce the smallest correct C change or the focused review the user requested. Preserve project conventions, make memory ownership and safety invariants explicit, and support completion claims with proportionate verification evidence.

## Start with the repository

1. Read applicable repository instructions and inspect worktree/branch status, the current diff, build definitions (`Makefile`, `CMakeLists.txt`, `meson.build`), compiler warning flags, CI pipelines, and nearby code or tests. Cap pre-flight discovery to 3-5 directly relevant files. Preserve unrelated and pre-existing changes.
2. Identify whether the request is implementation, diagnosis, review, API design, performance optimization, or build tooling. A review or diagnosis does not authorize edits.
3. Existing repository choices win. Do not change the C standard baseline (C99, C11, C17, C23), compiler requirement (Clang, GCC, MSVC), build system, warning levels, or public API stability contracts unless the request requires it.
4. For a new module or library, default to C11 or C17 with strict compiler warnings (`-Wall -Wextra -Werror -pedantic`). Enable AddressSanitizer and UBSan by default during debug builds and test execution.
5. Read only the references routed below that match the task.

## Cross-cutting rules

- **Explicit Memory Ownership Contracts**: Every function signature must document and enforce memory ownership:
  - *Caller-allocated output buffers*: Prefer passing a caller-provided destination pointer and capacity (`char *out_buf, size_t out_cap`) for bounded writing without heap allocation.
  - *Arena/Region allocation*: For complex multi-object graphs or request-scoped lifecycles, pass an explicit arena allocator (`arena_t *arena`) and deallocate the entire arena in a single bulk operation.
  - *Callee-heap allocation*: If a function must allocate heap memory (`malloc`/`calloc`), the function name and documentation must explicitly state caller ownership and the required deallocation function (e.g. `foo_destroy` or `free`).
- **Single Cleanup Exit Idiom (`goto cleanup;`)**: Use single-exit error handling for multi-resource functions. Declare and initialize all resource handles to `NULL`/zero at the top of the function. On any allocation or system call failure, set an error status and jump to `goto cleanup;`. Deallocate resources in reverse allocation order at the `cleanup:` label before returning.
- **Encapsulation via Opaque Pointers**: Expose only incomplete struct declarations (`typedef struct engine engine_t;`) in public headers. Define the concrete `struct engine { ... };` exclusively inside the private `.c` implementation file. This preserves ABI stability, hides implementation details, and prevents caller field tampering.
- **Anti-Abstraction & Rule of Three**: Write concrete functions and direct struct manipulations first. Do NOT introduce function pointer vtables (`struct driver_ops { int (*init)(void); ... };`) or generic callback dispatch layers unless at least 3 distinct concrete implementations exist in the repository or an external plugin interface requires it.
- **Forbid Small Struct Builders**: For structs with fewer than 5 fields (< 5 fields), forbid builder patterns or multi-stage setter APIs. Use direct struct initialization (`(point_t){ .x = 1.0f, .y = 2.0f }`) or a simple constructor function (`point_create(x, y)`).
- **Single-Path Execution & Atomic In-Place Refactoring**: When refactoring or updating an interface, data structure, or function, perform a clean in-place replacement and atomically update all call sites, internal usages, and tests in the same change wave. Never introduce forwarding wrapper shims, deprecated struct aliases, or ghost/commented-out legacy code.
- **Bounded Buffers & Safe String Handling**: Strictly forbid unsafe legacy libc functions: `strcpy`, `strcat`, `gets`, `sprintf`, and unsized `scanf %s`. Mandate bounded replacements: `snprintf` with truncation checking, length-bounded copy operations, or string slices (`str_view_t`).
- **Integer Overflow Protection**: Prevent integer overflow/wraparound when calculating allocation sizes or array offsets. Use C23 `<stdckdint.h>` (`ckd_mul`, `ckd_add`) or compiler builtins (`__builtin_mul_overflow`, `__builtin_add_overflow`) before calling `malloc` or `realloc`.
- **C11 Atomics & Concurrency Discipline**: Use `<stdatomic.h>` with the weakest necessary memory ordering (acquire-release for synchronization, relaxed for independent counters). Forbid raw volatile variables for thread synchronization. Always wrap `pthread_cond_wait()` inside a `while (!condition)` predicate check.
- **Hardware-Aware SIMD & Memory Layout**: Align performance-critical structures to 64-byte cache lines (`alignas(64)`) to avoid false sharing. Prefer Structure-of-Arrays (SoA) over Array-of-Structures (AoS) for vectorized computational kernels. Use `restrict` pointers to enable compiler auto-vectorization.
- **Zero-Warning Compiler Baseline**: All C code must compile cleanly with zero warnings under `-Wall -Wextra -Werror -pedantic -Wconversion -Wshadow -Wformat=2`.

## Verification

Discover and follow the repository's own commands first. Match validation scope to the change and widen it when risk warrants:

1. **Tier 1 (Fast-Path)**: For bug fixes, localized refactors, minor features, internal helpers, or unit tests, run targeted compiler and test invocations:
   - Direct Clang/GCC Fast-Path invocation with ASan and UBSan:
     ```bash
     clang -std=c11 -fsanitize=address,undefined -g -Wall -Wextra -Werror -pedantic -Iinclude src/module.c tests/test_module.c -o /tmp/test_mod && /tmp/test_mod
     ```
   - Targeted CTest filter:
     ```bash
     ctest --test-dir build --output-on-failure -R "<test_regex>"
     ```
   - Targeted Make test target:
     ```bash
     make test_<module> && ./build/test_<module>
     ```
   - Targeted Meson test:
     ```bash
     meson test -C build <test_name> --print-errorlogs
     ```
2. **Tier 2 (Full Verification)**: For core architectural modifications, public header ABI changes, concurrency/atomics primitives, memory allocators, or release builds, run full workspace verification:
   - Full CMake build with sanitizers:
     ```bash
     cmake -B build -DCMAKE_BUILD_TYPE=Debug -DENABLE_SANITIZERS=ON && cmake --build build && ctest --test-dir build --output-on-failure
     ```
   - ThreadSanitizer data race detection:
     ```bash
     cmake -B build_tsan -DCMAKE_C_FLAGS="-fsanitize=thread -g" && cmake --build build_tsan && ctest --test-dir build_tsan --output-on-failure
     ```
   - Valgrind leak check:
     ```bash
     valgrind --leak-check=full --show-leak-kinds=all --track-origins=yes --error-exitcode=1 ./build/bin/app_test
     ```
   - Static analysis:
     ```bash
     clang-tidy src/*.c -- -Iinclude -std=c11
     ```
3. Check formatting without creating unrelated churn: `clang-format --dry-run --Werror src/*.c include/*.h`. Inspect diffs before applying in-place formatting in a dirty tree.

Do not hide a pre-existing failure by changing unrelated code. Report the exact command, whether it passed, and any baseline or environmental blocker.

## References

- Memory ownership contracts, arena allocators, scratchpads, safe `realloc`, and `goto cleanup` idiom: read [references/memory-arenas.md](references/memory-arenas.md).
- Bounded buffer manipulation, safe string slices (`str_view_t`), integer overflow checks, and format string safety: read [references/buffer-string-safety.md](references/buffer-string-safety.md).
- Opaque pointer types (`PIMPL`), header include minimalism, compilation units, Rule of Three, and single-path refactoring: read [references/api-headers-architecture.md](references/api-headers-architecture.md).
- POSIX threads (`pthreads`), C11 atomics (`<stdatomic.h>`), memory orderings, and lock-free SPSC ring buffers: read [references/concurrency-atomics.md](references/concurrency-atomics.md).
- Cache line alignment, false sharing prevention, AoS vs SoA data layout, SIMD intrinsics (AVX2/NEON), and branchless programming: read [references/performance-simd.md](references/performance-simd.md).
- Compiler warning baselines, AddressSanitizer, UBSan, TSan, Valgrind, CMake/Make/Meson, and Fast-Path test recipes: read [references/tooling-sanitizers-ci.md](references/tooling-sanitizers-ci.md).

When several areas interact, read the smallest combination that covers the decision. Do not load every reference for a routine edit.
