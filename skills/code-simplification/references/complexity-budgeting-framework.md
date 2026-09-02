# Complexity Budgeting Framework

## 1. The Cost of Code: Cognitive Load vs. Performance Speedup

In software engineering, every line of code incurs an ongoing maintenance tax: compilation time, cognitive overhead for reviewers, testing surface area, and potential bug surface.

However, high-performance computing sometimes requires low-level constructs (e.g., explicit SIMD intrinsics, custom bump allocators, cache-aligned data layouts) that inherently increase structural complexity.

The **Complexity Budgeting Framework** establishes an objective decision model for balancing code simplicity against performance gains.

---

## 2. The Three-Tier Optimization & Simplification Decision Matrix

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

```
                       [Proposed Code Change]
                                 │
                 Is it both simpler AND faster?
                     ┌───────────┴───────────┐
                    YES                      NO
                     │                       │
             [TIER 1: MANDATORY]    Is speedup $\ge 2\times$ in proven bottleneck?
             Apply immediately               ┌───────────┴───────────┐
                                            YES                      NO
                                             │                       │
                                    [TIER 2: ENCAPSULATE]   [TIER 3: REJECT]
                                    Isolate behind clean    Strip accidental
                                    high-level API boundary complexity
```

---

## 3. Hardware Synergy: Why Simpler Code is Often Faster

Reducing code size and eliminating indirection has profound hardware-level performance benefits:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          HARDWARE-LEVEL SIMPLIFICATION SYNERGIES                       │
├──────────────────────────┬─────────────────────────────────────────────────────────────┤
│ Hardware Subsystem       │ Impact of Simpler, Compact Code                             │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ L1 Instruction Cache     │ Smaller function footprint fits entirely in the 32–64 KB    │
│ (L1i Cache)              │ L1i cache, eliminating instruction fetch stalls.            │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Branch Target Buffer     │ Linear, flat control flow without deep nested branching     │
│ (BTB) & Branch Predictor │ prevents BTB pollution and minimizes branch mispredictions. │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Compiler Inliner         │ Small functions ($<50$ LOC) are easily inlined by LLVM/GCC, │
│                          │ unlocking constant propagation and autovectorization.       │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Register Allocator       │ Flat expressions reduce live-variable spans, preventing     │
│                          │ register spilling to the stack frame.                       │
└──────────────────────────┴─────────────────────────────────────────────────────────────┘
```

### 3.1 The I-Cache Footprint Effect
When a critical loop invokes polymorphic virtual methods or calls through multiple wrapper forwarding layers, the machine code spans across multiple disjoint memory pages. This causes:
- Frequent L1i cache line evictions.
- Instruction Translation Lookaside Buffer (iTLB) misses.
- Micro-operation ($\mu\text{op}$) cache thrashing.

By stripping unnecessary wrapper layers and flattening function calls, the hot path becomes a contiguous block of machine instructions, maximizing CPU throughput.

---

## 4. Quantitative Complexity Budget Scorecards

Teams should enforce strict quantitative limits in automated CI/CD checks (using `scripts/complexity_budget_analyzer.py`):

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     QUANTITATIVE COMPLEXITY BUDGET THRESHOLDS                          │
├──────────────────────────────┬───────────────────┬───────────────────┬─────────────────┤
│ Metric                       │ Strict Budget     │ Warning Limit     │ Rejection Limit │
├──────────────────────────────┼───────────────────┼───────────────────┼─────────────────┤
│ Max Cyclomatic Complexity    │ $\le 5$           │ $6 - 10$          │ $> 10$          │
│ Max Cognitive Complexity     │ $\le 8$           │ $9 - 15$          │ $> 15$          │
│ Max AST Nesting Depth        │ $\le 2$           │ $3$               │ $> 3$           │
│ Max Function LOC             │ $\le 30$          │ $31 - 50$         │ $> 50$          │
│ Max Function Parameters      │ $\le 3$           │ $4$               │ $> 4$           │
│ Max Generic Type Parameters  │ $\le 1$           │ $2$               │ $> 2$           │
│ Max Class Inheritance Depth  │ $\le 1$           │ $2$               │ $> 2$           │
└──────────────────────────────┴───────────────────┴───────────────────┴─────────────────┘
```

### 4.1 Documented Budget Exemptions

In rare cases where Tier 2 high-performance algorithms require exceeding a budget threshold (e.g. an unrolled SIMD vector kernel or an optimized state machine transition switch with 25 states), exemptions must be:
1. **Explicitly Documented**: Include a benchmark link proving $\ge 2\times$ speedup.
2. **Encapsulated**: Confined within a private module file behind an opaque, simple public interface.
3. **Differential Tested**: Covered by automated differential tests against a simple reference implementation.
