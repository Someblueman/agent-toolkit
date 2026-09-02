# Monotonic Bump Arena Allocator Benchmark

This benchmark demonstrates the performance advantages of custom monotonic bump allocation over general-purpose system heap allocators (`malloc`/`free`, `new`/`delete`) during tree/AST construction and bulk destruction workloads (1,048,575 nodes).

## Key Techniques
1. **64-byte cache alignment** via `std::aligned_alloc`.
2. **Instantaneous $O(1)$ bulk deallocation** via `arena.reset()`.
3. **Sequential memory layout** maximizing L1/L2 cache locality during node traversals.
4. **Differential parity verification** ensuring recursive tree structures and data checksums match 100%.

## Building and Running
```bash
make
./arena_bench
```
