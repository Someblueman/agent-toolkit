# Zero-Copy Memory Management & Custom Allocators

General-purpose heap allocators (`malloc`, `free`, `new`, `delete`) are engineered for arbitrary allocation lifetimes and variable block sizes. This generality imposes steep costs: lock contention, metadata bookkeeping (16+ bytes per allocation), heap fragmentation, and non-contiguous memory layouts that destroy CPU cache locality.

High-performance systems bypass general allocators using specialized allocation strategies and zero-copy data views.

---

## 1. Allocator Performance Comparison

| Allocator Strategy | Allocation Time ($O$) | Free Time ($O$) | Metadata Overhead | Fragmentation | Thread Safety | Ideal Use Case |
|---|---|---|---|---|---|---|
| **System `malloc`** | $O(1)$ – $O(N)$ (bins) | $O(1)$ | 8–16B per chunk | High (external) | Global/Per-arena locks | General arbitrary lifetimes |
| **Bump / Arena** | $O(1)$ (1 pointer add) | $O(1)$ (bulk reset) | 0 bytes per alloc | Zero | Thread-local / lock-free | Request lifecycles, ASTs, per-frame data |
| **Fixed-Size Slab/Pool** | $O(1)$ (pop freelist) | $O(1)$ (push freelist)| 0 bytes (intrusive) | Zero | Lock-free via CAS | Network packets, game entities, tasks |
| **Small Buffer (SSO/SVO)**| $O(0)$ (stack) | $O(0)$ | Inline buffer | Zero | Thread-local | Strings/vectors $\le$ 24–64 bytes |

---

## 2. Monotonic Bump / Arena Allocator

An Arena allocates memory linearly from a pre-reserved contiguous buffer by incrementing an offset pointer. Individual deallocations are no-ops; the entire arena is reclaimed instantaneously by resetting the offset to 0.

### C++ Monotonic Arena Implementation
```cpp
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <new>

class LinearArena {
public:
    explicit LinearArena(size_t capacity) 
        : capacity_(capacity), offset_(0) {
        buffer_ = static_cast<uint8_t*>(std::aligned_alloc(64, capacity));
    }

    ~LinearArena() {
        std::free(buffer_);
    }

    // Allocate memory with strict alignment guarantees
    void* allocate(size_t size, size_t alignment = 8) {
        size_t current_addr = reinterpret_cast<size_t>(buffer_ + offset_);
        size_t aligned_addr = (current_addr + (alignment - 1)) & ~(alignment - 1);
        size_t new_offset = (aligned_addr - reinterpret_cast<size_t>(buffer_)) + size;

        if (new_offset > capacity_) {
            return nullptr; // Out of memory
        }

        offset_ = new_offset;
        return reinterpret_cast<void*>(aligned_addr);
    }

    template <typename T, typename... Args>
    T* create(Args&&... args) {
        void* mem = allocate(sizeof(T), alignof(T));
        if (!mem) return nullptr;
        return new (mem) T(std::forward<Args>(args)...);
    }

    // Instantaneous O(1) bulk reclamation
    void reset() noexcept {
        offset_ = 0;
    }

    size_t bytes_allocated() const noexcept { return offset_; }
    size_t capacity() const noexcept { return capacity_; }

private:
    uint8_t* buffer_;
    size_t capacity_;
    size_t offset_;
};
```

---

## 3. Fixed-Size Object Pool (Slab Allocator)

When allocating uniform objects (e.g. 128-byte connection contexts), a slab allocator uses an **intrusive freelist** where freed objects store the pointer to the next free node directly inside their own unallocated memory:

```cpp
#include <vector>
#include <cstddef>

template <typename T, size_t BlockSize = 4096>
class ObjectPool {
private:
    union Node {
        Node* next;
        alignas(alignof(T)) char storage[sizeof(T)];
    };

    Node* free_list_{nullptr};
    std::vector<void*> chunks_;

    void allocate_new_chunk() {
        size_t num_nodes = BlockSize / sizeof(Node);
        Node* block = static_cast<Node*>(std::aligned_alloc(alignof(T), num_nodes * sizeof(Node)));
        chunks_.push_back(block);

        for (size_t i = 0; i < num_nodes - 1; ++i) {
            block[i].next = &block[i + 1];
        }
        block[num_nodes - 1].next = free_list_;
        free_list_ = block;
    }

public:
    ObjectPool() = default;
    ~ObjectPool() {
        for (void* chunk : chunks_) std::free(chunk);
    }

    T* allocate() {
        if (!free_list_) allocate_new_chunk();
        Node* node = free_list_;
        free_list_ = free_list_->next;
        return reinterpret_cast<T*>(node->storage);
    }

    void deallocate(T* ptr) noexcept {
        if (!ptr) return;
        Node* node = reinterpret_cast<Node*>(ptr);
        node->next = free_list_;
        free_list_ = node;
    }
};
```

---

## 4. Zero-Copy Architectures & Non-Owning Views

Zero-copy eliminates copying memory buffers across processing stages by passing pointer/length view references:

### Language Implementations:
- **C++**: `std::string_view`, `std::span<T>` (C++20)
- **Rust**: `&str`, `&[T]`
- **Go**: `[]byte` slice slicing (`buf[start:end]`)
- **Python**: `memoryview(buf)` (bypasses byte string cloning)

### Zero-Copy Parsing Example (HTTP Header Parser):
```cpp
#include <string_view>
#include <vector>

struct HeaderView {
    std::string_view name;
    std::string_view value;
};

// Zero allocations: parses directly from input raw network buffer
std::vector<HeaderView> parse_headers_zerocopy(std::string_view raw_http, LinearArena& arena) {
    std::vector<HeaderView> headers;
    size_t pos = 0;
    
    while (pos < raw_http.size()) {
        size_t line_end = raw_http.find("\r\n", pos);
        if (line_end == std::string_view::npos || line_end == pos) break;
        
        std::string_view line = raw_http.substr(pos, line_end - pos);
        size_t colon = line.find(':');
        if (colon != std::string_view::npos) {
            std::string_view name = line.substr(0, colon);
            std::string_view val = line.substr(colon + 1);
            // Trim leading whitespace
            while (!val.empty() && val.front() == ' ') val.remove_prefix(1);
            headers.push_back({name, val});
        }
        pos = line_end + 2;
    }
    return headers;
}
```

---

## 5. High-Throughput Memory-Mapped I/O (`mmap`)

For massive sequential or random data processing (e.g. multi-gigabyte log analysis or database tables), `mmap` maps disk files directly into the virtual address space, eliminating user-space copy buffers.

```c
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>

void process_large_file_mmap(const char* filepath) {
    int fd = open(filepath, O_RDONLY);
    if (fd < 0) return;

    struct stat sb;
    fstat(fd, &sb);
    size_t file_size = sb.st_size;

    // Direct virtual memory mapping
    char* data = (char*)mmap(NULL, file_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (data == MAP_FAILED) {
        close(fd);
        return;
    }

    // Kernel advice: stream sequential pages & enable aggressive read-ahead
    madvise(data, file_size, MADV_SEQUENTIAL | MADV_WILLNEED);

    // Process file directly in place without read() syscall buffers
    // ... computation ...

    munmap(data, file_size);
    close(fd);
}
```

---

## 6. Traps & Safety Guidelines

1. **Dangling Pointers after Arena Reset**: Resetting an arena invalidates every pointer handed out during that cycle. Never store arena-allocated pointers in long-lived global or cross-thread data structures.
2. **Alignment Violations**: When writing custom bump allocators, never return unaligned raw offsets. Always round up the offset to the required alignment (`alignof(T)`); failing to align pointers triggers severe bus penalties or hardware fault crashes on strict architectures.
3. **`mmap` and `SIGBUS`**: If another process truncates a file while your application has it mapped via `mmap`, accessing the truncated memory region triggers an immediate `SIGBUS` signal. Always handle or guard file length mutations.
