# Memory Management, Ownership Contracts, Arenas, and Cleanup

Read this for explicit memory ownership contracts, arena allocator implementation, scratchpads, safe dynamic reallocation, and deterministic error cleanup idioms. Bounded string safety belongs in `buffer-string-safety.md`; opaque API encapsulation in `api-headers-architecture.md`; sanitizer configuration in `tooling-sanitizers-ci.md`.

---

## Memory Ownership Decision Matrix

In C, memory safety bugs (use-after-free, double-free, memory leaks) stem from ambiguous ownership. Every API must establish unambiguous ownership contracts:

| Allocation Pattern | When to Use | Ownership Contract | Deallocation Obligation |
|---|---|---|---|
| **Caller-Allocated Buffer** | Fixed-size or bounded output data (strings, path buffers, single structs) | Caller allocates on stack/heap; passes pointer + capacity to callee | Callee writes up to capacity; caller retains ownership and frees if needed |
| **Arena / Region Allocation** | Request lifecycles, AST/parser nodes, graph algorithms, batch tasks | Callee allocates out of caller-provided `arena_t` | Zero individual frees; caller frees entire arena in a single $O(1)$ operation |
| **Scratchpad / Temp Arena** | Intermediate transformations, string formatting, temporary filtering | Sub-lifetime within an arena; marks and restores arena offset | Restores arena offset via `arena_temp_end()`; zero heap allocations |
| **Callee-Allocated Heap** | Dynamically-sized objects whose lifetime exceeds caller scope | Callee invokes `malloc`/`calloc` and returns pointer | Caller takes sole ownership; must call designated destructor (`foo_destroy` or `free`) |

---

## Caller-Allocated Buffers vs Callee Heap Allocation

Avoid allocating heap memory inside utility or parsing functions when the caller can provide storage.

### ❌ ANTI-PATTERN: Hidden Callee Allocations
```c
// Anti-pattern: Callee forces malloc; caller frequently forgets to free()
char *format_user_greeting(const char *name) {
    if (!name) return NULL;
    size_t len = strlen(name) + 32;
    char *out = malloc(len);
    if (!out) return NULL;
    snprintf(out, len, "Hello, %s!", name);
    return out; // Caller owns out, but ownership is implicit and easily leaked
}
```

### ✅ PRAGMATIC: Caller-Provided Bounded Destination
```c
// Pragmatic: Caller passes buffer and capacity; zero heap allocation, bounded write
int format_user_greeting(const char *name, char *out_buf, size_t out_cap, size_t *out_len) {
    if (!name || !out_buf || out_cap == 0) return -1;

    int written = snprintf(out_buf, out_cap, "Hello, %s!", name);
    if (written < 0 || (size_t)written >= out_cap) {
        return -1; // Truncation or formatting error
    }

    if (out_len) *out_len = (size_t)written;
    return 0;
}
```

---

## Arena Allocator Architecture

An arena (bump allocator) pre-allocates a contiguous memory block and satisfies allocation requests by bumping an internal offset. It eliminates heap fragmentation and makes deallocation instantaneous.

### Arena Implementation (`arena.h` / `arena.c`)

```c
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct arena {
    uint8_t *buffer;
    size_t capacity;
    size_t offset;
} arena_t;

// Initialize arena with fixed capacity
int arena_init(arena_t *a, size_t capacity) {
    if (!a || capacity == 0) return -1;
    a->buffer = malloc(capacity);
    if (!a->buffer) return -1;
    a->capacity = capacity;
    a->offset = 0;
    return 0;
}

// Allocate memory with strict alignment
void *arena_alloc(arena_t *a, size_t size, size_t align) {
    if (!a || !a->buffer || size == 0 || a->offset > a->capacity) return NULL;
    if (align == 0) align = _Alignof(max_align_t);
    if ((align & (align - 1)) != 0) return NULL; // Power of two required
    uintptr_t current = (uintptr_t)(a->buffer + a->offset);
    size_t padding = (align - (current & (align - 1))) & (align - 1);
    size_t remaining = a->capacity - a->offset;
    if (padding > remaining || size > remaining - padding) return NULL;
    size_t start = a->offset + padding;
    void *ptr = a->buffer + start;
    a->offset = start + size; // Bounded by capacity above
    memset(ptr, 0, size); // Zero initialization
    return ptr;
}

// Reset arena offset to reuse allocated memory block
void arena_reset(arena_t *a) {
    if (a) a->offset = 0;
}

// Free arena backing memory
void arena_free(arena_t *a) {
    if (a && a->buffer) {
        free(a->buffer);
        a->buffer = NULL;
        a->capacity = 0;
        a->offset = 0;
    }
}
```

---

## Scratchpads / Temporary Arenas

When a function requires intermediate memory for processing without leaking or fragmenting the arena, use temporary marks (`arena_temp_t`).

```c
typedef struct arena_temp {
    arena_t *arena;
    size_t saved_offset;
} arena_temp_t;

static inline arena_temp_t arena_temp_begin(arena_t *a) {
    arena_temp_t temp = { .arena = a, .saved_offset = a ? a->offset : 0 };
    return temp;
}

static inline void arena_temp_end(arena_temp_t temp) {
    if (temp.arena) {
        temp.arena->offset = temp.saved_offset;
    }
}

// Example usage of temporary scratchpad
int process_intermediate_tokens(arena_t *arena, const char *raw_data) {
    arena_temp_t scratch = arena_temp_begin(arena);
    
    // Allocate temporary working buffers from arena
    char *temp_copy = arena_alloc(arena, 4096, 8);
    if (!temp_copy) {
        arena_temp_end(scratch);
        return -1;
    }

    // Perform intermediate operations...
    
    // All temporary allocations reverted; zero memory leaked or fragmented
    arena_temp_end(scratch);
    return 0;
}
```

---

## Single Cleanup Exit Pattern (`goto cleanup;`)

Multi-resource functions must use deterministic single-exit cleanup to prevent resource leaks across all error return paths.

### ❌ ANTI-PATTERN: Multiple Returns with Duplicated Cleanup
```c
// Anti-pattern: Duplicated cleanup prone to leaks when new resources are added
int parse_config_bad(const char *filename) {
    FILE *f = fopen(filename, "r");
    if (!f) return -1;

    char *buf = malloc(1024);
    if (!buf) {
        fclose(f); // Must remember to close f
        return -1;
    }

    int *ids = malloc(sizeof(int) * 100);
    if (!ids) {
        free(buf); // Must remember to free buf
        fclose(f); // Must remember to close f
        return -1;
    }

    if (fread(buf, 1, 1024, f) == 0) {
        // Leaks ids, buf, and f!
        return -1;
    }

    free(ids);
    free(buf);
    fclose(f);
    return 0;
}
```

### ✅ PRAGMATIC: Standard Single-Exit Cleanup
```c
// Pragmatic: Single cleanup exit guarantees zero leaks on all success and failure paths
int parse_config_clean(const char *filename) {
    int status = -1;
    FILE *f = NULL;
    char *buf = NULL;
    int *ids = NULL;

    f = fopen(filename, "r");
    if (!f) goto cleanup;

    buf = malloc(1024);
    if (!buf) goto cleanup;

    ids = malloc(sizeof(int) * 100);
    if (!ids) goto cleanup;

    if (fread(buf, 1, 1024, f) == 0) {
        goto cleanup; // Resource cleanup is centralized below
    }

    status = 0; // Success

cleanup:
    // Deallocate in reverse order of acquisition; free(NULL) is safe
    free(ids);
    free(buf);
    if (f) fclose(f);
    return status;
}
```

---

## Safe Dynamic Array Reallocation (`realloc`)

Never assign the result of `realloc` directly to the existing pointer. If `realloc` fails, it returns `NULL`, leaving the original allocation active but unreferenced (causing an immediate memory leak).

### ❌ ANTI-PATTERN: Unsafe Realloc Overwrite
```c
// Anti-pattern: If realloc fails, ptr is overwritten with NULL; original memory leaks!
void *ptr = malloc(100);
ptr = realloc(ptr, 200); // ❌ Memory leaked on allocation failure
if (!ptr) return -1;
```

### ✅ PRAGMATIC: Intermediate Pointer Reallocation
```c
// Pragmatic: Preserve original pointer until realloc succeeds
int resize_buffer(uint8_t **buf_ptr, size_t *cap_ptr, size_t new_cap) {
    if (!buf_ptr || !cap_ptr || new_cap == 0) return -1;

    void *tmp = realloc(*buf_ptr, new_cap);
    if (!tmp) {
        // Original buffer at *buf_ptr remains valid and can be freed cleanly
        return -1;
    }

    *buf_ptr = tmp;
    *cap_ptr = new_cap;
    return 0;
}
```

---

## Anti-Pattern Summary

| Anti-Pattern | Hazard | Pragmatic Replacement |
|---|---|---|
| `ptr = realloc(ptr, sz)` | Leaks memory if allocation fails | `void *tmp = realloc(ptr, sz); if (!tmp) goto cleanup; ptr = tmp;` |
| Multiple `return -1;` without cleanup | Resource, file descriptor, and memory leaks on error paths | Initialize pointers to `NULL`; use `goto cleanup;` with centralized deallocation |
| Fine-grained heap allocations for transient objects | Heap fragmentation, allocation overhead, high leak probability | Use `arena_t` or temporary scratchpads (`arena_temp_t`) |
| Unsized output pointer arguments | Buffer overflow vulnerability | Pass `out_buf` accompanied by `out_cap` and validate length |
| Calling `free()` on already freed pointer | Double-free vulnerability, undefined behavior | Assign pointer to `NULL` immediately after `free(ptr); ptr = NULL;` |

---

## Fast-Path Verification Recipes

Verify memory safety and arena implementations with AddressSanitizer and LeakSanitizer:

```bash
# Compile and run test with ASan and UBSan
clang -std=c11 -fsanitize=address,undefined -g -Wall -Wextra -Werror -pedantic \
  -Iinclude src/arena.c tests/test_arena.c -o /tmp/test_arena && /tmp/test_arena

# Run leak detection check via Valgrind (Linux / x86_64)
valgrind --leak-check=full --show-leak-kinds=all --track-origins=yes --error-exitcode=1 ./build/test_arena
```
