---
name: code-simplification
description: >-
  Systematically diagnoses accidental complexity, strips bloated design patterns,
  flattens control flow, collapses deep type hierarchies, and enforces quantitative
  complexity budgets across Rust, Go, Python, C++, and Haskell while ensuring 100%
  behavioral invariance through differential testing. Trigger when the user asks to
  simplify code, eliminate nested conditionals/arrow anti-pattern, remove over-engineering,
  reduce cognitive complexity, refactor design patterns, or streamline data pipelines.
---

# Code Simplification Playbook

A production-grade methodology for systematically diagnosing and removing accidental complexity, flattening architectures, and enforcing complexity budgets without introducing behavioral regressions.

---

## 1. Quick Start Workflow: The 5-Step Simplification Cycle

```
[ Step 1: Characterize & Snapshot ]
  ├── Freeze baseline behavior with tests or golden snapshots
  └── Tool: [scripts/invariant_regression_checker.py](scripts/invariant_regression_checker.py)
          │
[ Step 2: Diagnose Accidental Complexity ]
  ├── Audit AST nesting depth, cyclomatic, cognitive complexity, and signal ratio
  └── Tool: [scripts/complexity_budget_analyzer.py](scripts/complexity_budget_analyzer.py)
          │
[ Step 3: Apply Simplification Transformations ]
  ├── Invert nested checks into flat guard clauses (depth <= 2)
  ├── Strip over-engineered GoF patterns (Factories, Visitors, Strategies)
  └── Collapse deep inheritance & trait trees into flat data structs
          │
[ Step 4: Streamline Memory & Data Pipelines ]
  ├── Fuse multi-pass iterations into single-pass loops
  └── Convert copying signatures to zero-copy views (&str, &[T], std::span, memoryview)
          │
[ Step 5: Assert Behavioral Parity & Enforce Budget ]
  ├── Run differential fuzzing harness (assert baseline == simplified)
  └── Enforce complexity budget scorecard (Pass/Fail)
```

---

## 2. Refactoring Decision Tree

```
                              [Code Under Review]
                                       │
                    Is nesting depth > 3 or arrow pattern present?
                           ┌───────────┴───────────┐
                          YES                      NO
                           │                       │
               [Apply Guard Clauses]    Are there 1-to-1 interfaces,
               Invert conditions &      deep inheritance, or GoF visitors?
               early return top-of-fn      ┌───────────┴───────────┐
                                          YES                      NO
                                           │                       │
                               [Strip Over-Engineering]   Are multi-pass collections
                               Collapse to flat structs,  allocated in loops?
                               pure functions & enums        ┌───────────┴───────────┐
                                                            YES                      NO
                                                             │                       │
                                                 [Fuse Stream & Views]    [Check Budget]
                                                 Single-pass loop &       Verify max CC <= 10,
                                                 zero-copy slices         max nesting <= 3
```

---

## 3. Core Transformation Catalog

### 3.1 Control Flow Flattening (Arrow Anti-Pattern $\to$ Guard Clauses)
- **Problem**: 6-level nested `if/else` ladders (Pyramid of Doom) requiring high cognitive tracking.
- **Solution**: Invert checks into top-of-function guard clauses and early returns. Keep happy path at 0 indentation.
- **Reference**: [references/control-flow-and-data-pipelines.md](references/control-flow-and-data-pipelines.md)
- **Runnable Example**: [examples/control_flow_guard_refactoring/](examples/control_flow_guard_refactoring/)

### 3.2 Stripping Over-Engineered Design Patterns
- **Problem**: GoF Abstract Factories, Visitors, and Strategies written for static business logic.
- **Solution**: Replace with pure functions, lambdas, algebraic data types (tagged unions), and pattern matching.
- **Reference**: [references/pattern-stripping-and-flattening.md](references/pattern-stripping-and-flattening.md)
- **Runnable Example**: [examples/python_dataclass_pattern_matching/](examples/python_dataclass_pattern_matching/)

### 3.3 Data Pipeline Streamlining & Allocation Fusing
- **Problem**: Multi-pass transformations (`map().filter().collect()`) allocating intermediate heap vectors.
- **Solution**: Fuse transformations into a single-pass loop using non-owning zero-copy views.
- **Reference**: [references/control-flow-and-data-pipelines.md](references/control-flow-and-data-pipelines.md)
- **Runnable Example**: [examples/data_pipeline_zero_copy/](examples/data_pipeline_zero_copy/)

### 3.4 Language-Specific Modern Simplifications
- **Rust**: Unwind cyclic `Rc<RefCell<Node>>` to contiguous Arena index graphs (`Vec<Node>` + `NodeId`) and unify errors with `thiserror`.
  - Example: [examples/rust_error_and_arena_simplification/](examples/rust_error_and_arena_simplification/)
- **Go**: Return concrete structs, accept 1-method interfaces, prefer mutexes over channel multiplexing for local state.
- **Python**: Replace OOP hierarchies with `@dataclass(slots=True)` and `match/case`.
  - Example: [examples/python_dataclass_pattern_matching/](examples/python_dataclass_pattern_matching/)
- **C++**: Modernize SFINAE templates with C++20 concepts and `std::span`; replace virtual inheritance with `std::variant`.
- **Haskell**: Eliminate lazy accumulator space leaks via strict worker-wrapper transformations and `BangPatterns`.
  - Example: [examples/haskell_strict_accumulator/](examples/haskell_strict_accumulator/)
- **Reference**: [references/language-simplification-patterns.md](references/language-simplification-patterns.md)

---

## 4. Complexity Budgeting Framework

Evaluate all architectural changes against the 3-tier complexity decision matrix:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        3-TIER COMPLEXITY DECISION MATRIX                               │
├─────────┬──────────────────────────────────┬─────────────────┬─────────────────────────┤
│ Tier    │ Characteristics                  │ Action Rule     │ Example                 │
├─────────┼──────────────────────────────────┼─────────────────┼─────────────────────────┤
│ Tier 1  │ Code is simpler, shorter, AND    │ **Mandatory**   │ Guard clauses, fused    │
│         │ runs faster (Negative Cost).     │ Apply always.   │ single-pass loops,      │
│         │                                  │                 │ `std::string_view`.     │
├─────────┼──────────────────────────────────┼─────────────────┼─────────────────────────┤
│ Tier 2  │ Adds moderate structural         │ **Encapsulate** │ AVX2/NEON SIMD dot      │
│         │ complexity but yields proven     │ Confine behind  │ product engine, custom  │
│         │ massive speedup ($\ge 2\times$). │ clean boundary. │ Arena bump allocator.   │
├─────────┼──────────────────────────────────┼─────────────────┼─────────────────────────┤
│ Tier 3  │ High cognitive complexity or     │ **Reject / Strip│ Complex template meta-  │
│         │ esoteric tricks with negligible  │ Refactor to     │ programming for a 2%    │
│         │ speedup ($< 10\%$).              │ standard idioms.│ speedup in non-hot path.│
└─────────┴──────────────────────────────────┴─────────────────┴─────────────────────────┘
```

- **Quantitative Limits**: Max Cyclomatic $\le 10$ (target $\le 5$), Max Nesting $\le 3$, Max Function LOC $\le 50$.
- **Reference**: [references/complexity-budgeting-framework.md](references/complexity-budgeting-framework.md)

---

## 5. Behavioral Invariance Verification Protocol

Refactoring must never introduce semantic drift:
1. **Differential Fuzzing**: Run 5,000+ randomized input permutations across baseline and simplified candidates.
2. **Golden Snapshot Testing**: Validate serialized candidate outputs against frozen golden files, masking non-deterministic tokens (`<UUID>`, `<TIMESTAMP>`).
3. **Reference**: [references/behavioral-invariance-testing.md](references/behavioral-invariance-testing.md)

---

## 6. Automation Scripts & Tooling

- **Analyze Complexity Budget Compliance**:
  ```bash
  python3 scripts/complexity_budget_analyzer.py path/to/source/ --max-cyclomatic 10 --max-nesting 3
  ```
- **Execute Differential Invariance Check**:
  ```bash
  python3 scripts/invariant_regression_checker.py --baseline baseline.py --candidate simplified.py
  ```

---

## 7. Reference Index

| Topic | Reference Document |
|---|---|
| Accidental Complexity Diagnosis | [references/accidental-complexity-rubric.md](references/accidental-complexity-rubric.md) |
| Pattern Stripping & Hierarchy Flattening | [references/pattern-stripping-and-flattening.md](references/pattern-stripping-and-flattening.md) |
| Control Flow & Data Pipelines | [references/control-flow-and-data-pipelines.md](references/control-flow-and-data-pipelines.md) |
| Complexity Budgeting Framework | [references/complexity-budgeting-framework.md](references/complexity-budgeting-framework.md) |
| Language-Specific Simplification | [references/language-simplification-patterns.md](references/language-simplification-patterns.md) |
| Behavioral Invariance Testing | [references/behavioral-invariance-testing.md](references/behavioral-invariance-testing.md) |
