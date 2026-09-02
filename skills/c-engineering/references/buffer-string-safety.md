# Buffer and String Safety, Bounds Checking, and Integer Arithmetic

Read this for bounded buffer operations, safe string views, integer overflow prevention, and format string safety. Arena memory allocation belongs in `memory-arenas.md`; API headers and structs in `api-headers-architecture.md`; sanitizer setup in `tooling-sanitizers-ci.md`.

---

## Banned Libc Functions and Safe Replacements

Unbounded string and memory functions are the primary source of buffer overflows and security vulnerabilities in C. Enforce modern bounded alternatives:

| Banned Unbounded Function | Security Hazard | Safe Replacement | Replacement Idiom |
|---|---|---|---|
| `strcpy(dst, src)` | Unbounded stack/heap buffer overflow | `snprintf` or bounded `memcpy` | `snprintf(dst, sizeof(dst), "%s", src)` or bounds-checked copy |
| `strcat(dst, src)` | Buffer overflow, quadratic scanning time | `snprintf` or offset pointer append | Track remaining capacity: `snprintf(dst + len, cap - len, "%s", src)` |
| `sprintf(dst, fmt, ...)` | Buffer overflow on unexpected input lengths | `snprintf(dst, cap, fmt, ...)` | Check return: `if (ret < 0 || (size_t)ret >= cap) /* handle truncation */` |
| `gets(buf)` | Inherent, unpreventable buffer overflow (removed in C11) | `fgets(buf, sizeof(buf), stdin)` | Read bounded line: `if (fgets(buf, sizeof(buf), stdin) == NULL) ...` |
| `scanf("%s", buf)` | Buffer overflow on long input token | Sized specifier `scanf("%63s", buf)` | Restrict field width: `scanf("%63s", buf)` for a 64-byte buffer |
| `printf(user_string)` | Format string injection / arbitrary memory write | `printf("%s", user_string)` | Always use constant string literals as the format argument |

---

## Bounded Buffer Formatting & Truncation Handling

`snprintf` returns the number of characters that *would have been written* had the buffer been large enough (excluding the null terminator). If `ret >= capacity` or `ret < 0`, truncation or encoding error occurred.

### ❌ ANTI-PATTERN: Ignoring `snprintf` Return Value
```c
// Anti-pattern: Silently ignores truncation; subsequent operations process incomplete strings
void build_path_bad(char *out, size_t cap, const char *dir, const char *file) {
    snprintf(out, cap, "%s/%s", dir, file); // ❌ Return code unchecked!
}
```

### ✅ PRAGMATIC: Explicit Truncation Detection
```c
// Pragmatic: Check for truncation and encoding errors explicitly
int build_path_safe(char *out, size_t cap, const char *dir, const char *file) {
    if (!out || cap == 0 || !dir || !file) return -1;

    int written = snprintf(out, cap, "%s/%s", dir, file);
    if (written < 0 || (size_t)written >= cap) {
        // Output was truncated or format error occurred; clear buffer and return error
        out[0] = '\0';
        return -1;
    }

    return 0;
}
```

---

## String Views (Fat Pointer String Slices)

Standard C strings require null terminators (`\0`), forcing heap allocations or mutating original buffers when extracting substrings. The `str_view_t` idiom represents an immutable string slice without allocation.

### String View Implementation (`str_view.h`)

```c
#include <stdbool.h>
#include <stddef.h>
#include <string.h>

typedef struct str_view {
    const char *data;
    size_t len;
} str_view_t;

// Create string view from null-terminated C string
static inline str_view_t str_view_from_cstr(const char *s) {
    if (!s) return (str_view_t){ .data = NULL, .len = 0 };
    return (str_view_t){ .data = s, .len = strlen(s) };
}

// Create string view from explicit data and length
static inline str_view_t str_view_from_parts(const char *data, size_t len) {
    return (str_view_t){ .data = data, .len = len };
}

// Slice string view without memory allocation
static inline str_view_t str_view_slice(str_view_t sv, size_t start, size_t end) {
    if (start >= sv.len) return (str_view_t){ .data = NULL, .len = 0 };
    if (end > sv.len) end = sv.len;
    if (end <= start) return (str_view_t){ .data = NULL, .len = 0 };
    return (str_view_t){ .data = sv.data + start, .len = end - start };
}

// Compare two string views
static inline bool str_view_eq(str_view_t a, str_view_t b) {
    if (a.len != b.len) return false;
    if (a.len == 0) return true;
    return memcmp(a.data, b.data, a.len) == 0;
}

// Check prefix match
static inline bool str_view_starts_with(str_view_t sv, str_view_t prefix) {
    if (sv.len < prefix.len) return false;
    return memcmp(sv.data, prefix.data, prefix.len) == 0;
}
```

---

## Checked Integer Arithmetic

Integer overflow in size calculations (e.g. `count * sizeof(item)`) wraps around to a small number, causing undersized allocations followed by catastrophic heap buffer overflows.

Use C23 `<stdckdint.h>` or compiler builtins (`__builtin_mul_overflow`, `__builtin_add_overflow`).

### ❌ ANTI-PATTERN: Unchecked Allocation Size Calculation
```c
// Anti-pattern: If count is large (e.g. 2^30 on 32-bit or huge on 64-bit), multiplication wraps
void *allocate_records_bad(size_t count) {
    size_t total_bytes = count * sizeof(record_t); // ❌ Overflows silently!
    return malloc(total_bytes); // Allocates small buffer, subsequent loop writes past end
}
```

### ✅ PRAGMATIC: Checked Multiplication via C23 or Compiler Builtins
```c
#include <stddef.h>
#include <stdlib.h>

#if defined(__STDC_VERSION__) && __STDC_VERSION__ >= 202311L
#include <stdckdint.h>
#define CHECKED_MUL(res, a, b) ckd_mul(res, a, b)
#define CHECKED_ADD(res, a, b) ckd_add(res, a, b)
#elif defined(__GNUC__) || defined(__clang__)
#define CHECKED_MUL(res, a, b) __builtin_mul_overflow(a, b, res)
#define CHECKED_ADD(res, a, b) __builtin_add_overflow(a, b, res)
#else
// Portable fallback for size_t multiplication check
static inline int checked_mul_size(size_t *res, size_t a, size_t b) {
    if (a != 0 && b > (size_t)-1 / a) return 1;
    *res = a * b;
    return 0;
}
#define CHECKED_MUL(res, a, b) checked_mul_size(res, a, b)
#endif

void *allocate_records_safe(size_t count, size_t elem_size) {
    if (count == 0 || elem_size == 0) return NULL;

    size_t total_bytes = 0;
    if (CHECKED_MUL(&total_bytes, count, elem_size)) {
        return NULL; // Overflow detected; reject allocation safely
    }

    return malloc(total_bytes);
}
```

---

## Format String Injection Prevention

Never pass a dynamic or user-controlled string directly as the format string argument to `printf`, `sprintf`, `snprintf`, or `syslog`. Attackers can use `%n` or `%x` specifiers to read and write arbitrary stack and memory addresses.

### ❌ ANTI-PATTERN: Dynamic Format String
```c
// Anti-pattern: Format string vulnerability
void log_message_bad(const char *user_input) {
    printf(user_input); // ❌ Vulnerable to arbitrary memory read/write
}
```

### ✅ PRAGMATIC: Fixed Constant Format Specifier
```c
// Pragmatic: Constant format specifier with user input passed as data argument
void log_message_safe(const char *user_input) {
    if (!user_input) return;
    printf("%s\n", user_input); // ✅ Secure: format string is constant literal
}
```

---

## Anti-Pattern Summary

| Anti-Pattern | Vulnerability | Pragmatic Replacement |
|---|---|---|
| `strcpy(dst, src)` | Stack/Heap buffer overflow | `snprintf(dst, sizeof(dst), "%s", src)` |
| `sprintf(dst, ...)` | Unchecked buffer overrun | `snprintf(dst, cap, ...)` with return code verification |
| Unchecked `count * size` | Integer overflow -> heap buffer overflow | C23 `ckd_mul` or `__builtin_mul_overflow` |
| Substring via `strdup` + mutation | Memory churn and memory leaks | Use fat pointer `str_view_t` slices |
| `printf(dynamic_var)` | Arbitrary memory execution/leak | `printf("%s", dynamic_var)` |
| Unbounded `scanf("%s", ...)` | Stack buffer overflow | `scanf("%63s", buf)` with explicit width limit |

---

## Fast-Path Verification Recipes

Verify buffer and integer safety with AddressSanitizer and UndefinedBehaviorSanitizer:

```bash
# Compile with ASan, UBSan, and strict format warnings
clang -std=c11 -fsanitize=address,undefined -g -Wall -Wextra -Werror -pedantic -Wformat=2 \
  -Iinclude src/buffer.c tests/test_buffer.c -o /tmp/test_buffer && /tmp/test_buffer
```
