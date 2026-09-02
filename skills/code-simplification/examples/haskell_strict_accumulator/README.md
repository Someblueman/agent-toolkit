# Example: Haskell Lazy Accumulator to Strict Worker-Wrapper

## Problem Overview
Haskell's default lazy evaluation builds closures (thunks) in memory when updating accumulator values in loops (`acc + x`). For long lists, this leads to $O(N)$ heap allocation, excessive garbage collection overhead, and stack overflows.

## Refactoring Strategy
1. **BangPatterns (`!`)**: Annotate worker parameters with `!` to force evaluation to Weak Head Normal Form (WHNF) eagerly.
2. **Worker-Wrapper Pattern**: Isolate the recursive core into a local worker function with unboxed accumulator arguments.
3. **Constant Space**: Achieve true $O(1)$ memory consumption and fast unboxed register arithmetic.

## Files
- `BaselineLazy.hs`: Naive lazy fold accumulating thunk chains.
- `SimplifiedStrict.hs`: Strict worker-wrapper with `BangPatterns`.
- `TestParity.hs`: Parity test suite and benchmark over 1,000,000 elements.

## Verification
```bash
runghc TestParity.hs
# or with compiler optimization:
ghc -O2 -rtsopts TestParity.hs -o test_parity && ./test_parity
```
