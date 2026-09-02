# Branchless Programming & Hardware Bit Manipulation

Modern out-of-order CPU cores employ deep execution pipelines (14–20+ stages). When a conditional branch (`if / else`, `switch`, loop condition) cannot be predicted accurately by the CPU Branch History Table (BHT), the entire instruction pipeline must be flushed and refilled. This incurs a penalty of **15 to 20 clock cycles per misprediction**.

Branchless programming and hardware bit manipulation eliminate pipeline flushes by replacing conditional jumps with arithmetic expressions, conditional moves (`CMOV` / `csel`), and single-cycle bitwise instructions.

---

## 1. The Cost of Branch Mispredictions

Consider iterating through an array of randomized numbers and summing only values greater than 128:

```c
// BRANCHY: High misprediction rate (~50% on uniform random input)
uint64_t sum_branchy(const uint8_t* data, size_t count) {
    uint64_t sum = 0;
    for (size_t i = 0; i < count; ++i) {
        if (data[i] >= 128) { // Unpredictable branch!
            sum += data[i];
        }
    }
    return sum;
}
```

```c
// BRANCHLESS: Zero branches, constant throughput
uint64_t sum_branchless(const uint8_t* data, size_t count) {
    uint64_t sum = 0;
    for (size_t i = 0; i < count; ++i) {
        // Boolean comparison generates 0 or 1 without branching
        uint8_t condition = (data[i] >= 128);
        sum += data[i] * condition;
    }
    return sum;
}
```

On randomized data, `sum_branchless` is typically **3x–6x faster** than `sum_branchy` because it completely removes pipeline stalls.

---

## 2. Core Branchless Idioms

### 1. Conditional Selection via Arithmetic Bitmask
For types of width $W$, `-(int)(cond)` generates a bitmask of all 1s (`0xFFFFFFFF`) when true, or all 0s (`0x00000000`) when false:

```c
// Select 'a' if cond is true, else 'b'
int32_t branchless_select(int32_t cond, int32_t a, int32_t b) {
    int32_t mask = -((int32_t)(cond != 0)); // 0xFFFFFFFF if true, 0x0 if false
    return (a & mask) | (b & ~mask);
}
```

### 2. Branchless Min, Max, and Absolute Value
```c
#include <stdint.h>

// Branchless Minimum
int32_t branchless_min(int32_t a, int32_t b) {
    return b ^ ((a ^ b) & -(a < b));
}

// Branchless Maximum
int32_t branchless_max(int32_t a, int32_t b) {
    return a ^ ((a ^ b) & -(a < b));
}

// Branchless Absolute Value (for 32-bit signed integers)
int32_t branchless_abs(int32_t v) {
    int32_t mask = v >> 31; // 0 if v >= 0, -1 (0xFFFFFFFF) if v < 0
    return (v ^ mask) - mask;
}
```

### 3. Branchless Clamping
```c
// Clamp value between min_val and max_val without branching
int32_t branchless_clamp(int32_t val, int32_t min_val, int32_t max_val) {
    val = branchless_max(val, min_val);
    val = branchless_min(val, max_val);
    return val;
}
```

---

## 3. Branchless Array Filtering / Compaction

Filtering matching elements from an array into an output buffer usually involves `if (predicate(x)) out[out_idx++] = x;`. The branchy index increment causes heavy mispredictions on random data.

```c
// Branchless array filtering: unconditional store with predicated increment
size_t filter_positive_branchless(const int32_t* in, size_t n, int32_t* out) {
    size_t out_idx = 0;
    for (size_t i = 0; i < n; ++i) {
        int32_t val = in[i];
        uint32_t keep = (val > 0); // 1 if kept, 0 if dropped
        
        out[out_idx] = val;        // Store unconditionally
        out_idx += keep;           // Advance write pointer only if kept
    }
    return out_idx;
}
```

---

## 4. Hardware Bit Manipulation Intrinsics

Modern CPUs feature dedicated single-cycle silicon instructions for complex bitwise calculations:

| Operation | GCC / Clang Builtin | x86 Instruction | ARM64 Instruction | Rust Method |
|---|---|---|---|---|
| **Population Count** (count set 1s) | `__builtin_popcountll(x)` | `POPCNT` | `cnt` + `addv` | `x.count_ones()` |
| **Count Leading Zeros** | `__builtin_clzll(x)` | `LZCNT` / `BSR` | `clz` | `x.leading_zeros()` |
| **Count Trailing Zeros** | `__builtin_ctzll(x)` | `TZCNT` / `BSF` | `rbit` + `clz` | `x.trailing_zeros()` |
| **Bit Reverse** | `__builtin_bitreverse64(x)` | Custom shifts / BSWAP | `rbit` | `x.reverse_bits()` |
| **Byte Swap (Endianness)** | `__builtin_bswap64(x)` | `BSWAP` | `rev` | `x.swap_bytes()` |

### Bit Twiddling Algorithms

#### 1. Check if Integer is Power of Two:
```c
static inline bool is_power_of_two(uint64_t x) {
    return x != 0 && (x & (x - 1)) == 0;
}
```

#### 2. Isolate Least Significant Set Bit (LSB):
```c
static inline uint64_t isolate_lowest_set_bit(uint64_t x) {
    return x & (-x);
}
```

#### 3. Clear Least Significant Set Bit:
```c
static inline uint64_t clear_lowest_set_bit(uint64_t x) {
    return x & (x - 1);
}
```

#### 4. Fast Round Up to Next Power of Two:
```c
static inline uint64_t next_power_of_two(uint64_t x) {
    if (x <= 1) return 1;
    return 1ULL << (64 - __builtin_clzll(x - 1));
}
```

#### 5. Fast Bitset Iteration (Iterate set bit indices):
```c
void iterate_active_indices(uint64_t bitmask, void (*callback)(uint32_t)) {
    while (bitmask != 0) {
        uint32_t idx = __builtin_ctzll(bitmask); // Index of lowest set bit
        callback(idx);
        bitmask &= (bitmask - 1);                // Clear lowest set bit
    }
}
```

---

## 5. Parallel Bit Extraction and Deposit (BMI2)

On x86_64 processors supporting BMI2, `_pext_u64` (Parallel Bit Extract) and `_pdep_u64` (Parallel Bit Deposit) extract or deposit non-contiguous bits defined by a mask in a single clock cycle:

```c
#ifdef __BMI2__
#include <immintrin.h>

// Extract bits defined by mask to contiguous low-order bits
uint64_t extract_chess_rank(uint64_t board, uint64_t rank_mask) {
    return _pext_u64(board, rank_mask);
}
#endif
```

---

## 6. Traps & Edge Cases

1. **Undefined Behavior for `clz(0)` and `ctz(0)`**:
   On x86 without the `LZCNT` / `TZCNT` extension, calling `__builtin_clz(0)` or `__builtin_ctz(0)` produces **undefined behavior**. Always guard zero inputs or provide an explicit zero check:
   ```c
   static inline uint32_t safe_clz32(uint32_t x) {
       return (x == 0) ? 32 : __builtin_clz(x);
   }
   ```
2. **Speculative Execution Side Effects**:
   Branchless selection (`a & mask | b & ~mask`) evaluates both `a` and `b`. If evaluating `a` or `b` triggers a division by zero (`x / y`), a null pointer dereference (`*ptr`), or a function call with side effects, branchless selection is **invalid** and dangerous.
3. **When to Keep Branches**:
   If a branch is predicted correctly >99% of the time (such as rare error checks: `if (__builtin_expect(err != 0, 0)) return ERR;`), the CPU branch predictor handles it with **0 cycle overhead**, while branchless arithmetic would add unnecessary instructions.
