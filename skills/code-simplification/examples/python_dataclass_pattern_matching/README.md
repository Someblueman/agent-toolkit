# Example: Python Dataclass & Pattern Matching Modernization

## Problem Overview
Legacy Python OOP architectures often employ the Gang of Four Visitor pattern with Abstract Base Classes (`abc.ABC`), double-dispatch (`accept(visitor)`), and manual dunder method implementations. This introduces excessive boilerplate and slow method dispatch.

## Refactoring Strategy
1. **Immutable Slots Dataclasses**: Define tree nodes using `@dataclass(slots=True, frozen=True)` to eliminate `__dict__` overhead and automatic `__repr__`/`__eq__` generation.
2. **Structural Pattern Matching**: Replace multi-class double dispatch with a single pure recursive function using Python 3.10+ `match / case`.

## Files
- `baseline_oop_hierarchy.py`: OOP Visitor pattern with ABCs and double dispatch.
- `simplified_dataclass_match.py`: Concise dataclasses with `match/case`.
- `test_parity.py`: Differential property fuzzing suite (5,000+ random expression trees).

## Verification
```bash
python3 test_parity.py
python3 ../../scripts/complexity_budget_analyzer.py .
```
