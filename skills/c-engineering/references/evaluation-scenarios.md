# Maintainer Evaluation Scenarios for C Systems Engineering

This document contains 10 behavioral evaluation scenarios for maintainers to assess whether code changes, reviews, or agent implementations strictly adhere to the `c-engineering` skill principles.

---

## Scenario 1: Multi-Resource Allocation Leak on Error Path

### Context
A parser function allocates dynamic memory buffers, opens a file descriptor, and initializes an internal state object. If parsing fails at any intermediate stage, all acquired resources must be cleanly released.

### ❌ REJECT: Multiple Return Points with Leaks
```c
int parse_config_file(const char *path, config_t *out) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;

    char *buf = malloc(4096);
    if (!buf) {
        fclose(f);
        return -1;
    }

    int *ids = malloc(sizeof(int) * 64);
    if (!ids) {
        // ❌ Leaks buf and f!
        return -1;
    }

    if (fread(buf, 1, 4096, f) == 0) {
        // ❌ Leaks ids, buf, and f!
        return -1;
    }

    free(ids);
    free(buf);
    fclose(f);
    return 0;
}
```

### ✅ ACCEPT: Deterministic `goto cleanup;` Single Exit
```c
int parse_config_file(const char *path, config_t *out) {
    int status = -1;
    FILE *f = NULL;
    char *buf = NULL;
    int *ids = NULL;

    if (!path || !out) goto cleanup;

    f = fopen(path, "r");
    if (!f) goto cleanup;

    buf = malloc(4096);
    if (!buf) goto cleanup;

    ids = malloc(sizeof(int) * 64);
    if (!ids) goto cleanup;

    if (fread(buf, 1, 4096, f) == 0) goto cleanup;

    // Process config...
    status = 0; // Success

cleanup:
    free(ids);
    free(buf);
    if (f) fclose(f);
    return status;
}
```

**Evaluation Rubric**: Reject any code with multiple error exits duplicating resource cleanup. Accept only single-exit `goto cleanup;` with pointers initialized to `NULL` and deallocated in reverse order.

---

## Scenario 2: Unsafe String Formatting vs Bounded `snprintf`

### Context
A logging utility formats an error message containing user-provided strings and integer codes into a fixed-size buffer.

### ❌ REJECT: Unbounded `sprintf` or Unchecked `snprintf`
```c
void format_log_entry(char *buf, size_t cap, const char *msg, int code) {
    // ❌ sprintf can overflow buf; return value is ignored
    sprintf(buf, "[ERROR %d] %s", code, msg);
}
```

### ✅ ACCEPT: Bounded `snprintf` with Truncation Detection
```c
int format_log_entry(char *buf, size_t cap, const char *msg, int code) {
    if (!buf || cap == 0 || !msg) return -1;

    int written = snprintf(buf, cap, "[ERROR %d] %s", code, msg);
    if (written < 0 || (size_t)written >= cap) {
        buf[0] = '\0'; // Truncation or formatting failure
        return -1;
    }

    return 0;
}
```

**Evaluation Rubric**: Reject any call to `sprintf`, `strcpy`, or unchecked `snprintf`. Accept bounded `snprintf` with explicit truncation check (`written >= cap`).

---

## Scenario 3: Premature Vtable Abstraction vs Direct Concrete API

### Context
A project requires saving telemetry metrics to local disk storage. Only local disk storage exists in the project.

### ❌ REJECT: Speculative Function Pointer Vtable (Rule of Three Violation)
```c
// ❌ Anti-pattern: Over-engineered vtable for single implementation
typedef struct telemetry_ops {
    int (*init)(void *ctx, const char *path);
    int (*write)(void *ctx, const uint8_t *data, size_t len);
    void (*close)(void *ctx);
} telemetry_ops_t;

typedef struct telemetry_sink {
    telemetry_ops_t *ops;
    void *ctx;
} telemetry_sink_t;
```

### ✅ ACCEPT: Direct Concrete API
```c
// ✅ Pragmatic: Direct concrete functions until 3 distinct storage sinks exist
typedef struct disk_sink disk_sink_t;

disk_sink_t *disk_sink_create(const char *path);
int disk_sink_write(disk_sink_t *sink, const uint8_t *data, size_t len);
void disk_sink_destroy(disk_sink_t *sink);
```

**Evaluation Rubric**: Reject speculative function pointer structs or generic callback tables when fewer than 3 implementations exist. Accept direct concrete function signatures.

---

## Scenario 4: Encapsulation via Opaque Pointers (PIMPL)

### Context
A cryptography library exports an encryption context struct in its public header.

### ❌ REJECT: Leaking Internal Struct Fields in Public Header
```c
// public include/crypto_engine.h
// ❌ Exposes internal OpenSSL/kernel types and fields directly to callers
#include <openssl/evp.h>

typedef struct crypto_engine {
    EVP_CIPHER_CTX *ctx;
    uint8_t key[32];
    uint8_t iv[16];
    size_t block_size;
} crypto_engine_t;
```

### ✅ ACCEPT: Opaque Pointer in Header with Private Struct in `.c`
```c
// public include/crypto_engine.h
#ifndef CRYPTO_ENGINE_H
#define CRYPTO_ENGINE_H

#include <stddef.h>
#include <stdint.h>

// ✅ Opaque type: ABI stable, zero internal dependencies leaked
typedef struct crypto_engine crypto_engine_t;

crypto_engine_t *crypto_engine_create(const uint8_t *key, size_t key_len);
void crypto_engine_destroy(crypto_engine_t *engine);
int crypto_engine_encrypt(crypto_engine_t *engine, const uint8_t *in, size_t in_len, uint8_t *out, size_t *out_len);

#endif /* CRYPTO_ENGINE_H */
```

**Evaluation Rubric**: Reject struct definitions in public headers containing private state or implementation headers. Accept opaque pointer typedefs.

---

## Scenario 5: Concurrency, Atomics, and False Sharing

### Context
A multi-threaded queue shares head and tail indexes between producer and consumer threads.

### ❌ REJECT: Adjacent Atomics Causing False Sharing and Unsynchronized Volatile
```c
typedef struct queue {
    // ❌ Volatile is not thread-safe; adjacent variables cause false sharing
    volatile size_t head;
    volatile size_t tail;
    void *buffer[1024];
} queue_t;
```

### ✅ ACCEPT: Cache-Line Padded C11 Atomics with Acquire/Release
```c
#include <stdatomic.h>
#include <stdalign.h>

typedef struct queue {
    void *buffer[1024];
    
    // ✅ 64-byte alignment isolates cache lines to prevent false sharing
    alignas(64) atomic_size_t head;
    alignas(64) atomic_size_t tail;
} queue_t;
```

**Evaluation Rubric**: Reject `volatile` used for thread synchronization and adjacent atomic counters. Accept `alignas(64)` with C11 `<stdatomic.h>` and acquire/release ordering.

---

## Scenario 6: Integer Overflow Prevention in Memory Allocation

### Context
A vector resize function dynamically allocates an array of `count * sizeof(element_t)` bytes based on user input.

### ❌ REJECT: Unchecked Arithmetic Overflow
```c
int vector_resize(vector_t *v, size_t new_count) {
    // ❌ If new_count is large, multiplication wraps to a tiny size
    size_t bytes = new_count * sizeof(uint64_t);
    void *tmp = realloc(v->data, bytes);
    if (!tmp) return -1;
    v->data = tmp;
    v->capacity = new_count;
    return 0;
}
```

### ✅ ACCEPT: Checked Arithmetic via Builtin or C23
```c
int vector_resize(vector_t *v, size_t new_count) {
    if (!v || new_count == 0) return -1;

    size_t bytes = 0;
    // ✅ Checked multiplication detects wraparound before allocation
    if (__builtin_mul_overflow(new_count, sizeof(uint64_t), &bytes)) {
        return -1; // Overflow detected
    }

    void *tmp = realloc(v->data, bytes);
    if (!tmp) return -1;

    v->data = tmp;
    v->capacity = new_count;
    return 0;
}
```

**Evaluation Rubric**: Reject raw `count * size` passed to `malloc`/`realloc`. Accept checked arithmetic (`__builtin_mul_overflow` or C23 `ckd_mul`).

---

## Scenario 7: Single-Path Execution & Refactoring

### Context
A packet header struct `packet_t` is updated to replace a 16-bit field `flags` with a 32-bit field `extended_flags`.

### ❌ REJECT: Forwarding Shim and Deprecated Alias Retention
```c
// ❌ Retaining legacy shims and zombie unions
typedef struct packet {
    union {
        uint16_t flags; // Deprecated shim
        uint32_t extended_flags;
    };
} packet_t;

// Deprecated wrapper shim
uint16_t packet_get_flags(const packet_t *p) {
    return (uint16_t)p->extended_flags;
}
```

### ✅ ACCEPT: Clean Atomic In-Place Replacement
```c
// ✅ Clean replacement: updated struct and call sites atomically
typedef struct packet {
    uint32_t extended_flags;
} packet_t;

uint32_t packet_get_flags(const packet_t *p) {
    return p ? p->extended_flags : 0;
}
```

**Evaluation Rubric**: Reject legacy forwarding shims, zombie union decoders, or commented-out code. Accept clean in-place replacement across all call sites and tests.

---

## Scenario 8: SIMD Vector Unaligned Memory Crash

### Context
A matrix math function processes 8 single-precision floats per loop iteration using AVX2.

### ❌ REJECT: Aligned SIMD Load on Arbitrary Pointer
```c
#include <immintrin.h>

void add_arrays_avx2(float *out, const float *a, const float *b, size_t n) {
    for (size_t i = 0; i < n; i += 8) {
        // ❌ _mm256_load_ps crashes (SIGSEGV/SIGBUS) if pointer is not 32-byte aligned!
        __m256 va = _mm256_load_ps(&a[i]);
        __m256 vb = _mm256_load_ps(&b[i]);
        __m256 vres = _mm256_add_ps(va, vb);
        _mm256_store_ps(&out[i], vres);
    }
}
```

### ✅ ACCEPT: Unaligned Load (`_mm256_loadu_ps`) with Scalar Remainder Loop
```c
#include <immintrin.h>

void add_arrays_avx2(float * restrict out, const float * restrict a, const float * restrict b, size_t n) {
    size_t i = 0;
    // ✅ Safe unaligned vector load handles arbitrary pointer alignments
    for (; i + 7 < n; i += 8) {
        __m256 va = _mm256_loadu_ps(&a[i]);
        __m256 vb = _mm256_loadu_ps(&b[i]);
        __m256 vres = _mm256_add_ps(va, vb);
        _mm256_storeu_ps(&out[i], vres);
    }

    // ✅ Scalar remainder loop handles n % 8 != 0
    for (; i < n; ++i) {
        out[i] = a[i] + b[i];
    }
}
```

**Evaluation Rubric**: Reject aligned SIMD loads (`_mm256_load_ps`) unless pointers are proven aligned via `posix_memalign`. Reject missing scalar remainder loops. Accept `_mm256_loadu_ps` and scalar tail loops.

---

## Scenario 9: Stack Pointer Escape Bug Detected by ASan

### Context
A helper function parses a host string and returns a socket address structure.

### ❌ REJECT: Returning Pointer to Local Stack Variable
```c
struct sockaddr_in *parse_host(const char *host, uint16_t port) {
    struct sockaddr_in addr; // Local stack allocation
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    inet_pton(AF_INET, host, &addr.sin_addr);
    return &addr; // ❌ Address of stack memory escapes function; undefined behavior!
}
```

### ✅ ACCEPT: Pass-by-Reference Caller-Allocated Destination
```c
int parse_host(const char *host, uint16_t port, struct sockaddr_in *out_addr) {
    if (!host || !out_addr) return -1;

    memset(out_addr, 0, sizeof(*out_addr));
    out_addr->sin_family = AF_INET;
    out_addr->sin_port = htons(port);
    if (inet_pton(AF_INET, host, &out_addr->sin_addr) != 1) {
        return -1;
    }

    return 0;
}
```

**Evaluation Rubric**: Reject functions returning pointers to stack variables. Accept caller-allocated output parameters verified with AddressSanitizer (`-fsanitize=address`).

---

## Scenario 10: Tier 1 Fast-Path Test Execution

### Context
A developer makes a one-line bug fix inside `src/arena.c` and wants to verify the fix with unit tests.

### ❌ REJECT: Full Workspace Multi-Target Rebuild
```bash
# ❌ Excessive ceremonial overhead: builds entire release suite and runs long integration tests
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --target all
ctest --test-dir build --all-targets
```

### ✅ ACCEPT: Fast-Path Compiler & Unit Test Invocation with ASan
```bash
# ✅ Fast-Path: Under 500ms compilation and test execution with AddressSanitizer
clang -std=c11 -fsanitize=address,undefined -g -Wall -Wextra -Werror -pedantic \
  -Iinclude src/arena.c tests/test_arena.c -o /tmp/test_arena && /tmp/test_arena
```

**Evaluation Rubric**: Reject running full multi-minute integration pipelines for localized edits. Accept targeted Fast-Path single-module test commands with sanitizers enabled.
