# Example: Data Pipeline Zero-Copy & Allocation Fusing

## Problem Overview
Multi-pass data pipelines (splitting, filtering, transforming, mapping, filtering again, aggregating) often allocate new intermediate heap collections at every stage. For large datasets, this creates severe memory allocation churn and cache pressure.

## Refactoring Strategy
1. **Fuse Intermediate Iterations**: Merge map/filter/parse operations into a single continuous loop.
2. **Stream Processing**: Process line-by-line / record-by-record directly without creating intermediate list representations.
3. **In-Place Aggregation**: Maintain rolling state aggregates instead of collecting records into a list before reducing.

## Files
- `baseline_multi_pass.py`: Multi-stage pipeline allocating 6 intermediate lists/dicts.
- `simplified_zero_copy.py`: Single-pass streaming pipeline with zero intermediate collections.
- `test_parity.py`: Parity test and memory allocation benchmark (`tracemalloc`).

## Verification
```bash
python3 test_parity.py
python3 ../../scripts/complexity_budget_analyzer.py .
```
