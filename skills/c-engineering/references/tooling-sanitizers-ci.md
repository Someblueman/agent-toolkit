# Tooling, Compiler Warnings, Sanitizers, Valgrind, and CI Pipelines

Read this for strict compiler warning baselines, AddressSanitizer (ASan), UndefinedBehaviorSanitizer (UBSan), ThreadSanitizer (TSan), Valgrind memory leak checking, Clang-Tidy, and Make/CMake/Meson build recipes. Memory arenas belong in `memory-arenas.md`; SIMD vectorization in `performance-simd.md`.

---

## Strict Compiler Warning Baseline

All production C code must compile cleanly with zero warnings under modern GCC or Clang. Treat warnings as build-breaking errors:

```makefile
# Strict C compiler warning flags baseline
CFLAGS += -std=c11 \
          -Wall \
          -Wextra \
          -Werror \
          -pedantic \
          -Wconversion \
          -Wsign-conversion \
          -Wshadow \
          -Wdouble-promotion \
          -Wformat=2 \
          -Wformat-security \
          -Wundef \
          -Wstrict-prototypes \
          -Wmissing-prototypes \
          -fno-common
```

### Critical Flag Rationale

| Compiler Flag | Hazard Prevented |
|---|---|
| `-Wconversion` / `-Wsign-conversion` | Implicit truncation or sign change (e.g. `uint32_t` assigned to `uint16_t` or negative `int` passed as `size_t`) |
| `-Wshadow` | Variable shadowing that hides outer variables and causes logic bugs |
| `-Wdouble-promotion` | Silent promotion of `float` to `double` in computational inner loops, causing 50%+ slowdown |
| `-Wformat=2` | Format string vulnerabilities, missing format arguments, or mismatched specifiers |
| `-Wstrict-prototypes` | Declaring functions without explicit parameter types (e.g. `void foo()` in C accepts arbitrary arguments) |
| `-fno-common` | Multiple tentative global variable definitions with identical names across translation units |

---

## Runtime Sanitizers Matrix

Compile with LLVM/GCC sanitizers during development and continuous integration. Never deploy production release builds with sanitizers enabled (they add ~2x CPU and memory overhead).

| Sanitizer | Compiler Flags | What It Detects | Compatibility Notes |
|---|---|---|---|
| **AddressSanitizer (ASan)** | `-fsanitize=address -fno-omit-frame-pointer -g` | Out-of-bounds heap/stack/global access, use-after-free, double-free | Incompatible with TSan; run in separate build |
| **UndefinedBehaviorSanitizer (UBSan)** | `-fsanitize=undefined -g` | Signed integer overflow, null pointer dereference, misaligned pointer access | Compatible with ASan; combine as `-fsanitize=address,undefined` |
| **ThreadSanitizer (TSan)** | `-fsanitize=thread -g` | Concurrent data races, deadlocks, lock order inversions | Mutually exclusive with ASan; requires dedicated test run |
| **LeakSanitizer (LSan)** | `-fsanitize=leak` | Memory leaks on program exit | Enabled automatically inside ASan on Linux |
| **MemorySanitizer (MSan)** | `-fsanitize=memory -fsanitize-memory-track-origins -g` | Reads of uninitialized heap/stack memory | Clang-only; requires all linked libraries compiled with MSan |

---

## Valgrind Leak & Memory Debugging

When sanitizers cannot be used (or for deep heap profiling on Linux/x86_64), use Valgrind Memcheck:

```bash
valgrind --leak-check=full \
         --show-leak-kinds=all \
         --track-origins=yes \
         --error-exitcode=1 \
         ./build/bin/my_program_test
```

---

## Build Systems & Fast-Path Test Recipes

### 1. Direct Clang/GCC Fast-Path (Single File / Unit Test)
For rapid sub-second TDD iterations without triggering heavy full-project rebuilds:

```bash
clang -std=c11 -fsanitize=address,undefined -g -Wall -Wextra -Werror -pedantic \
  -Iinclude src/module.c tests/test_module.c -o /tmp/test_module && /tmp/test_module
```

### 2. CMake Fast-Path & Full Verification
```bash
# Tier 1: Fast-Path targeted test run
cmake --build build --target test_network && ctest --test-dir build -R test_network --output-on-failure

# Tier 2: Full build with ASan + UBSan
cmake -B build -DCMAKE_BUILD_TYPE=Debug -DENABLE_SANITIZERS=ON
cmake --build build -j$(nproc)
ctest --test-dir build --output-on-failure

# Tier 2: ThreadSanitizer build
cmake -B build_tsan -DCMAKE_BUILD_TYPE=Debug -DCMAKE_C_FLAGS="-fsanitize=thread -g"
cmake --build build_tsan -j$(nproc)
ctest --test-dir build_tsan --output-on-failure
```

### 3. Make Fast-Path & Target Recipes
```bash
# Tier 1: Targeted module test
make test_parser && ./build/test_parser

# Tier 2: Full test suite with sanitizers
make clean && make SANITIZE=1 test
```

### 4. Meson Fast-Path Recipes
```bash
# Tier 1: Targeted test
meson test -C build <test_name> --print-errorlogs

# Tier 2: Full sanitizer suite
meson setup build -Db_sanitize=address,undefined
meson compile -C build
meson test -C build --print-errorlogs
```

---

## Clang-Tidy Static Analysis

Run Clang-Tidy to catch subtle bugs before compilation:

```bash
clang-tidy src/*.c \
  -checks='bugprone-*,clang-analyzer-*,cert-*,performance-*,readability-*,-readability-identifier-length' \
  -- -Iinclude -std=c11
```

---

## Anti-Pattern Summary

| Anti-Pattern | Risk / Problem | Pragmatic Replacement |
|---|---|---|
| Compiling with default `-Wall` only | Leaves critical signed conversions and format bugs silent | Add `-Wextra -Werror -pedantic -Wconversion -Wshadow` |
| Skipping sanitizers during local test execution | Memory corruption and race bugs escape to production | Run unit tests with `-fsanitize=address,undefined` |
| Running ASan and TSan in the same binary | Compiler build error (sanitizers conflict) | Separate CI jobs: one for ASan+UBSan, one for TSan |
| Full CMake rebuild for a single function edit | High latency, breaks fast TDD iteration cycle | Use direct compiler invocation or targeted `ctest -R` |
| Using Valgrind on macOS ARM64 | Incompatible / unsupported platform | Use Clang ASan (`-fsanitize=address`) on macOS |
