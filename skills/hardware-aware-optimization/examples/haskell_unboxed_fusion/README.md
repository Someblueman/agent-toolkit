# Haskell Optimization: Unboxed Primitives & Stream Fusion

This benchmark demonstrates how low-level unboxed primitives (`MagicHash`, `Double#`, `Int#`) and stream fusion eliminate lazy thunk allocations and garbage collection overhead in Haskell, achieving near-C performance across 10 million pipeline elements.

## Key Techniques
1. **Unboxed Primitives (`MagicHash`)**: Operating directly on machine registers (`Double#`, `Int#`) with zero heap closures.
2. **Stream Fusion**: Inlining and fusing multi-pass combinators (`filter`, `map`, `fold`) into a single non-allocating loop.
3. **Differential Parity Verification**: Mathematically verifying that unboxed and fused streams yield the exact same floating-point result as the standard boxed list baseline.

## Building and Running
```bash
make
./HaskellBench +RTS -s
```
