# API Design, Header Architecture, Opaque Pointers, and Refactoring

Read this for opaque pointer encapsulation (PIMPL in C), header include hygiene, translation unit boundaries, the Rule of Three for API contracts, and single-path refactoring. Memory arenas belong in `memory-arenas.md`; concurrency primitives in `concurrency-atomics.md`; compiler warnings in `tooling-sanitizers-ci.md`.

---

## Opaque Pointers (Encapsulation and ABI Stability)

Exposing struct field definitions in public headers binds callers directly to struct memory layout and private dependencies. When struct fields change, binary compatibility breaks, requiring full re-compilation of all consumer modules.

Use the **opaque pointer** pattern (PIMPL in C):

### Public Header (`include/network_engine.h`)
```c
#ifndef NETWORK_ENGINE_H
#define NETWORK_ENGINE_H

#include <stddef.h>
#include <stdint.h>

// Opaque type declaration: callers know the type exists as a pointer, but cannot see its fields
typedef struct network_engine network_engine_t;

// Lifecycle management
network_engine_t *network_engine_create(uint16_t port, size_t max_conns);
void network_engine_destroy(network_engine_t *engine);

// Concrete API operations
int network_engine_start(network_engine_t *engine);
int network_engine_stop(network_engine_t *engine);
int network_engine_broadcast(network_engine_t *engine, const uint8_t *data, size_t len);

#endif /* NETWORK_ENGINE_H */
```

### Private Source Implementation (`src/network_engine.c`)
```c
#include "network_engine.h"
#include <stdlib.h>
#include <unistd.h>
#include <sys/socket.h>

// Full struct definition is strictly internal to this translation unit
struct network_engine {
    int listen_fd;
    uint16_t port;
    size_t max_conns;
    size_t active_conns;
    int *conn_fds;
};

network_engine_t *network_engine_create(uint16_t port, size_t max_conns) {
    if (max_conns == 0) return NULL;

    network_engine_t *engine = malloc(sizeof(*engine));
    if (!engine) return NULL;

    engine->listen_fd = -1;
    engine->port = port;
    engine->max_conns = max_conns;
    engine->active_conns = 0;
    engine->conn_fds = calloc(max_conns, sizeof(int));
    if (!engine->conn_fds) {
        free(engine);
        return NULL;
    }

    return engine;
}

void network_engine_destroy(network_engine_t *engine) {
    if (!engine) return;
    if (engine->listen_fd >= 0) close(engine->listen_fd);
    free(engine->conn_fds);
    free(engine);
}

int network_engine_start(network_engine_t *engine) {
    if (!engine) return -1;
    // Implementation details...
    return 0;
}
```

---

## Header Include Minimalism & Forward Declarations

Headers should include only what is required to parse their type definitions. If a header only uses a pointer to a struct, forward-declare the struct instead of including its entire header file.

### ❌ ANTI-PATTERN: Header Include Sprawl
```c
// Anti-pattern in header: Pulls in dozens of transitive headers, slowing build times
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include "internal_database.h" // Leaks internal implementation header to callers

typedef struct session {
    internal_db_conn_t *db;
    struct sockaddr_in client_addr;
} session_t;
```

### ✅ PRAGMATIC: Minimal Header with Forward Declarations
```c
#ifndef SESSION_H
#define SESSION_H

#include <stddef.h>

// Forward declarations avoid pulling in heavy third-party or internal headers
struct internal_db_conn;
typedef struct internal_db_conn internal_db_conn_t;

typedef struct session session_t;

session_t *session_create(internal_db_conn_t *db);
void session_destroy(session_t *s);

#endif /* SESSION_H */
```

---

## Linkage, Scope, and Visibility

- **`static` Functions**: Every function not part of the public API must be declared `static` in its `.c` file. This limits visibility to the translation unit, enables aggressive compiler inlining, and prevents symbol collision.
- **`static inline` in Headers**: Small, hot accessor functions (e.g. `str_view_len`) placed in headers must be declared `static inline`.
- **Global Variables**: Forbid non-`static` global variables. If shared state is mandatory, keep it `static` within a `.c` file behind accessor functions.

---

## Rule of Three in C Architecture (Anti-Abstraction)

Do NOT extract function pointer vtables (`struct ops`) or abstract driver interfaces when there is only 1 concrete implementation. Direct function calls are faster, inlinable, easily searchable (`grep`), and drastically simpler to debug.

### ❌ ANTI-PATTERN: Speculative Function Pointer Table
```c
// Anti-pattern: 1 concrete storage engine wrapped in speculative vtable abstraction
typedef struct storage_driver_ops {
    int (*init)(void *ctx, const char *path);
    int (*read)(void *ctx, uint64_t id, void *buf, size_t *len);
    int (*write)(void *ctx, uint64_t id, const void *data, size_t len);
    void (*close)(void *ctx);
} storage_driver_ops_t;

typedef struct storage_engine {
    storage_driver_ops_t *ops;
    void *ctx;
} storage_engine_t;

// Invocation requires indirect function pointer call (cannot be inlined, hard to debug)
int res = engine->ops->write(engine->ctx, 42, buf, len);
```

### ✅ PRAGMATIC: Direct Concrete API
```c
// Pragmatic: Direct concrete functions until 3 distinct storage backends exist
typedef struct disk_storage disk_storage_t;

disk_storage_t *disk_storage_open(const char *path);
int disk_storage_read(disk_storage_t *ds, uint64_t id, void *buf, size_t *len);
int disk_storage_write(disk_storage_t *ds, uint64_t id, const void *data, size_t len);
void disk_storage_close(disk_storage_t *ds);

// Direct call: inlinable by compiler, fast, explicit call graph
int res = disk_storage_write(storage, 42, buf, len);
```

---

## Forbid Small Struct Builders (< 5 Fields)

Do not create builder pattern objects or multi-step setters for simple data structures with fewer than 5 fields.

### ❌ ANTI-PATTERN: Builder Pattern for 3-Field Struct
```c
// Anti-pattern: 50 lines of boilerplate to construct a 3-field struct
typedef struct point { float x; float y; float z; } point_t;
typedef struct point_builder point_builder_t;

point_builder_t *point_builder_create(void);
void point_builder_set_x(point_builder_t *b, float x);
void point_builder_set_y(point_builder_t *b, float y);
void point_builder_set_z(point_builder_t *b, float z);
point_t point_builder_build(point_builder_t *b);
```

### ✅ PRAGMATIC: Direct Struct Initialization / Constructor
```c
typedef struct point {
    float x;
    float y;
    float z;
} point_t;

// Constructor helper or direct compound literal
static inline point_t point_create(float x, float y, float z) {
    return (point_t){ .x = x, .y = y, .z = z };
}

// Usage:
point_t pt1 = point_create(1.0f, 2.0f, 3.0f);
point_t pt2 = (point_t){ .x = 1.0f, .y = 2.0f, .z = 3.0f };
```

---

## Single-Path Execution & Atomic In-Place Refactoring

When refactoring a function signature, struct layout, or module contract, perform a clean in-place replacement and atomically update all call sites across the codebase in the same commit.

- **Ban Forwarding Shims**: Do not retain deprecated wrappers like `int old_fn(int x) { return new_fn(x, 0); }`.
- **Ban Zombie Struct Aliases**: Do not retain `typedef struct new_foo old_foo_t;` unless part of a versioned public ABI boundary.
- **Ban Commented-Out Ghost Code**: Delete obsolete functions completely; rely on Git history for recovery.

---

## Anti-Pattern Summary

| Anti-Pattern | Drawback | Pragmatic Replacement |
|---|---|---|
| Struct fields exposed in public `.h` | Breaks ABI on field edits, exposes private state | Opaque pointer `typedef struct foo foo_t;` |
| Deep nested header `#include`s | Slow compilation, circular dependencies | Forward-declare structs; `#include` only in `.c` |
| Speculative `struct ops` vtables for single backend | Indirect branch overhead, prevents inlining, obscures debug stack | Direct concrete functions (`disk_storage_read`) |
| Builder pattern for structs < 5 fields | Boilerplate sprawl, dynamic memory overhead | Compound literals or simple constructors |
| Forwarding wrapper shims for old APIs | Dead code bloat, confusing API surface | Clean in-place atomic update across all call sites |

---

## Fast-Path Verification Recipes

Verify translation unit compilation and symbol visibility:

```bash
# Verify compilation unit cleanly builds with strict warning flags
clang -std=c11 -Wall -Wextra -Werror -pedantic -Iinclude -c src/network_engine.c -o /tmp/network_engine.o

# Inspect exported symbols to ensure non-public functions are not exported
nm -g /tmp/network_engine.o
```
