# Lock-Free SPSC Ring Buffer Benchmark

This benchmark demonstrates high-throughput Single-Producer Single-Consumer (SPSC) inter-thread message passing without mutexes or kernel context switches.

## Key Techniques
1. **64-byte Cache Line Separation (`alignas(64)`)**: Placing atomic `head` and `tail` on separate cache lines eliminates false sharing.
2. **Atomic Acquire / Release Memory Orderings**: Zero global lock barriers.
3. **Producer & Consumer Cached Indices**: Bypasses expensive cross-core atomic synchronization when the buffer is not full/empty.
4. **Differential Parity & Checksum Verification**: Proves 100% in-order message delivery without dropped or duplicated messages.

## Building and Running
```bash
make
./spsc_bench
```
