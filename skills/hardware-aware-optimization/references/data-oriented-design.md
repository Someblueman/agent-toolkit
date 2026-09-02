# Data-Oriented Design & Hardware-Aware Memory Layout

Data-Oriented Design (DoD) shifts the programming mental model from abstract object hierarchies to the physical reality of how modern CPUs access memory. Modern CPU execution speed is predominantly constrained by memory access latency—the "memory wall." Optimizing data layouts for cache line utilization, spatial locality, and alignment frequently yields an order-of-magnitude greater speedup than algorithmic tweaks alone.

---

## 1. Hardware Cache Architecture & Latency Realities

Modern multi-core processors (such as x86_64 Intel/AMD and ARM64 Apple M-series) organize memory into a hierarchical caching topology:

| Hierarchy Level | Typical Size (per core/shared) | Typical Latency (cycles) | Access Time (approx. ns) |
|---|---|---|---|
| **CPU Registers** | ~1–2 KB total | 0–1 cycle | < 0.3 ns |
| **L1 Data Cache (L1D)** | 32 KB – 128 KB per core | 4–5 cycles | ~1.0 ns |
| **L2 Unified / Data** | 512 KB – 4 MB per core | 12–14 cycles | ~3.0 – 4.0 ns |
| **L3 Shared Cache (LLC)** | 16 MB – 64+ MB shared | 40–75 cycles | ~10 – 20 ns |
| **Main Memory (DRAM)** | 16 GB – 128+ GB | 150–300 cycles | ~60 – 100 ns |

### The 64-Byte Cache Line
Memory is transferred between DRAM and CPU caches in fixed chunks of **64 bytes** (a cache line). When a single 4-byte float is loaded from DRAM, the CPU automatically fetches the entire 64-byte block containing that float.

- **Spatial Locality**: If adjacent data elements in the 64-byte line are needed by subsequent instructions, those accesses hit L1D with 0 penalty.
- **Cache Pollution**: If a struct contains 64 bytes of fields but an algorithm only reads 4 bytes per struct across 1,000,000 instances, **93.75% of memory bandwidth and cache capacity is completely wasted**.

---

## 2. AoS vs. SoA vs. AoSoA Layouts

### Array of Structures (AoS) — Object-Oriented Default
In AoS, all attributes of a single entity are stored contiguously in memory:

```cpp
// AoS: 32 bytes per entity
struct Particle {
    float x, y, z;       // 12 bytes (Hot in physics step)
    float vx, vy, vz;    // 12 bytes (Hot in physics step)
    uint32_t color;      // 4 bytes  (Cold during physics)
    uint32_t id;         // 4 bytes  (Cold during physics)
};

Particle particles[1000000]; // Array of structures
```

**Memory Layout**:
`[x0, y0, z0, vx0, vy0, vz0, c0, id0] [x1, y1, z1, vx1, vy1, vz1, c1, id1] ...`

*Flaw*: In a physics loop updating positions `x += vx * dt`, each particle requires reading 24 bytes of hot data, but loading the 32-byte struct pulls cold `color` and `id` into L1D cache, evicting other active lines.

---

### Structure of Arrays (SoA) — Data-Oriented Streaming
In SoA, each field is stored in its own separate, contiguous array:

```cpp
// SoA: Contiguous parallel arrays
struct ParticleSystemSoA {
    float* x;   // Contiguous float stream
    float* y;
    float* z;
    float* vx;
    float* vy;
    float* vz;
    uint32_t* color; // Cold data untouched during physics update
    uint32_t* id;
    size_t count;
};
```

**Memory Layout for X**:
`[x0, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12, x13, x14, x15, ...]`

*Advantages*:
1. **100% Cache Line Utilization**: Loading `x[0]` fetches `x[0]` through `x[15]` (16 floats per 64B cache line). Zero wasted bytes.
2. **SIMD Load Friendliness**: Contiguous floats can be loaded directly into 128-bit NEON (`vld1q_f32`) or 256-bit AVX2 (`_mm256_load_ps`) registers without gather/scatter instructions.
3. **Hardware Prefetcher Optimization**: Modern stride prefetchers identify the linear memory access and stream upcoming cache lines into L1D ahead of time.

---

### Array of Structures of Arrays (AoSoA / Tiled SoA)
When datasets are vast or random lookups occur by chunk, AoSoA combines the cache friendliness of SoA with the encapsulation of AoS by grouping data into tiles matching the vector register width:

```cpp
// AoSoA / Tiled SoA for 8-wide AVX2 or 4-wide NEON
constexpr size_t SIMD_WIDTH = 8; // 8 floats = 32 bytes (1 AVX2 register)

struct ParticleTile {
    float x[SIMD_WIDTH];
    float y[SIMD_WIDTH];
    float z[SIMD_WIDTH];
    float vx[SIMD_WIDTH];
    float vy[SIMD_WIDTH];
    float vz[SIMD_WIDTH];
};

struct ParticleSystemAoSoA {
    std::vector<ParticleTile> tiles;
};
```

**Memory Layout**:
`[Tile 0: x0..7, y0..7, z0..7, vx0..7, vy0..7, vz0..7] [Tile 1: x8..15, ...]`

---

## 3. Cache Line Alignment & False Sharing Elimination

### What is False Sharing?
When two threads running on different CPU cores modify independent variables that happen to reside within the **same 64-byte cache line**, the CPU cache coherence protocol (MESI/MOESI) forces the cache line to bounce back and forth between cores:

1. Core 0 writes `counter[0]` -> Core 0 marks cache line as **Modified (M)**.
2. Core 1's copy of the entire 64-byte line is invalidated (**Invalid - I**).
3. Core 1 writes `counter[1]` -> Core 1 must reload the line from L3/RAM, marking it Modified.
4. Core 0's copy is invalidated.
5. Result: **10x–50x performance degradation** due to continuous cache line bouncing, despite zero logical race condition.

```
Thread 0 (Core 0)                      Thread 1 (Core 1)
writes counter[0]                     writes counter[1]
      │                                     │
      ▼                                     ▼
┌───────────────────────────────────────────────────────────┐
│              Same 64-Byte Cache Line                      │
│  [ counter[0] (8B) | counter[1] (8B) | ... (48B unused) ] │
└───────────────────────────────────────────────────────────┘
               ▲                           ▲
               └────── Cache Invalidation ─┘
```

### Elimination via 64-Byte Alignment and Padding

#### In C++ (C++11 and C++17):
```cpp
#include <new>

// Hardware destructive interference size (typically 64 bytes)
#ifdef __cpp_lib_hardware_interference_size
    using std::hardware_destructive_interference_size;
#else
    constexpr size_t hardware_destructive_interference_size = 64;
#endif

// Align structure to distinct 64-byte cache lines
struct alignas(hardware_destructive_interference_size) ThreadCounter {
    uint64_t count{0};
    // Compiler automatically pads struct to 64 bytes
};

struct MultiThreadedEngine {
    // Each thread counter is guaranteed to reside on a distinct cache line
    ThreadCounter counters[MAX_THREADS];
};
```

#### In Rust:
```rust
#[repr(align(64))]
pub struct ThreadWorkerState {
    pub processed_items: u64,
    pub last_latency_ns: u64,
}

pub struct ConcurrentEngine {
    pub workers: [ThreadWorkerState; 16],
}
```

#### In Go:
```go
type WorkerStats struct {
    count uint64
    _pad  [56]byte // Explicit 56-byte pad: 8B + 56B = 64B cache line
}
```

---

## 4. Struct Member Packing & Padding Reduction

Compilers align struct members to multiples of their natural size (e.g., an 8-byte pointer must align to an 8-byte boundary). Suboptimal field ordering introduces wasted padding bytes.

### Poor Layout (Wasted Padding):
```cpp
struct BadEntity {
    bool active;        // 1 byte  (+ 7 bytes padding)
    double health;      // 8 bytes (aligned at offset 8)
    uint16_t id;        // 2 bytes  (+ 6 bytes padding)
    void* ptr;          // 8 bytes (aligned at offset 24)
}; // Total sizeof = 32 bytes (11 bytes data + 21 bytes padding = 65.6% waste)
```

### Optimized Layout (Ordered by Alignment Descending):
```cpp
struct OptimizedEntity {
    void* ptr;          // 8 bytes (offset 0)
    double health;      // 8 bytes (offset 8)
    uint16_t id;        // 2 bytes (offset 16)
    bool active;        // 1 byte  (offset 18)
    char _pad[5];       // 5 bytes tail padding to multiple of 8
}; // Total sizeof = 24 bytes (8 fewer bytes per instance!)
```

### Struct Optimization Rules:
1. **Sort fields descending by alignment requirement**: `8-byte (pointers, int64_t, double)` -> `4-byte (int32_t, float)` -> `2-byte (int16_t)` -> `1-byte (bool, char)`.
2. **Diagnostic compiler flags**:
   - Clang/GCC: `-Wpadded` warns whenever padding is inserted inside a struct.
   - Rust: `cargo-pahole` or `structlayout` tool analyzes memory layout.
3. **Hot/Cold field splitting**: Separate fields modified in hot loops from metadata fields (like names, debug UUIDs) into separate structs.

---

## 5. Software Prefetching

Hardware stride prefetchers automatically detect linear forward or backward accesses. However, for non-linear or multi-pointer chasing algorithms (e.g., hash table probes or B-tree lookups), software prefetching instructs the memory controller to start fetching lines cycles before use:

```cpp
// C/C++ Software Prefetching
// __builtin_prefetch(addr, rw, locality)
// rw: 0 = read, 1 = write
// locality: 0 (no temporal locality) to 3 (extremely high temporal locality)

void batch_hash_lookup(const uint64_t* keys, size_t count, HashTable& table) {
    constexpr size_t PREFETCH_DISTANCE = 8;
    
    for (size_t i = 0; i < count; ++i) {
        // Prefetch bucket for item (i + PREFETCH_DISTANCE) while processing item i
        if (i + PREFETCH_DISTANCE < count) {
            size_t prefetch_idx = table.hash(keys[i + PREFETCH_DISTANCE]);
            __builtin_prefetch(&table.buckets[prefetch_idx], 0, 1);
        }
        
        // Process current key
        table.lookup(keys[i]);
    }
}
```

---

## 6. Implementation Checklist & Verification

- [ ] Has the data structure been evaluated for AoS vs SoA in hot iteration loops?
- [ ] Are per-thread write targets aligned to 64 bytes (`alignas(64)`) to eliminate false sharing?
- [ ] Are struct fields ordered by descending size to eliminate internal padding holes?
- [ ] Has `-Wpadded` been checked during compilation to identify unintended alignment overhead?
- [ ] Are hot arrays allocated with 64-byte alignment (`posix_memalign`, `std::aligned_alloc`, or `_aligned_malloc`) to support aligned SIMD vector loads?
