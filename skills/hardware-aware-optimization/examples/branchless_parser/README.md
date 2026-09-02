# Branchless Record Filtering & Parser Benchmark

This benchmark demonstrates how eliminating branch mispredictions in data filtering and parsing loops across 10 million randomized records accelerates throughput by replacing jumps with arithmetic bitmasks and predicated index advancement.

## Key Techniques
1. **Arithmetic Bitmasks**: Replacing nested `if` statements with non-branching boolean bitwise operations (`&`).
2. **Predicated Write Pointer Updates**: Storing candidate records unconditionally and incrementing the output index by `0` or `1` using conditional move (`CMOV` / `csel`).
3. **Differential Parity Verification**: Comparing all filtered outputs byte-for-byte against the baseline branching filter.

## Building and Running
```bash
make
./branchless_bench
```
