# Evaluation, Strictness, and Performance

Use this page when correctness depends on when a value is evaluated, when preventing space leaks, or when optimizing measured code.

## Name the Evaluation Contract

Haskell values may contain unevaluated computations or bottoms. Say what an API promises to evaluate:

| Mechanism | Typical demand |
| --- | --- |
| ordinary `case` or constructor pattern | enough to select a constructor, usually weak head normal form (WHNF) |
| `seq`, a bang pattern, strict field, or `$!` | WHNF, subject to pattern/newtype details |
| `evaluate x` | evaluates `x` to WHNF inside `IO`, making exception timing composable |
| `deepseq`, `force`, or `evaluate (force x)` | normal form (NF) as defined by the `NFData` instance |

WHNF does not force constructor fields. NF is only as strong and correct as the `NFData` instance. Lazy patterns and `newtype` can behave differently from ordinary data-constructor intuition.

- Force a pure computation inside the resource or exception scope that is supposed to contain its failure.
- Test the depth the caller will observe. Evaluating only an outer constructor can hide a bottom in a field.
- Remember that adding `seq` or strict fields can change termination and exception behavior, so strictness is semantic as well as operational.
- Do not describe a value as fully evaluated without establishing an appropriate `NFData` contract.

## Strictness Choices

- Use strict fields for values that should never retain producers and whose early evaluation does not change the intended failure behavior.
- Use bang patterns for local state that must be evaluated each iteration. Confirm what the pattern actually forces.
- `Strict` and `StrictData` are broad semantic switches. Adopt them only under an explicit package/module policy and review lazy exceptions deliberately.
- Choose folds by behavior, not slogans. `foldl'` is often appropriate for strict accumulators, but a lazy or right fold can be essential for short-circuiting, productivity, or structure.
- For long-running state, check whether strictness reaches fields inside the accumulator; WHNF of a record may still retain thunks.
- Prefer strict and lazy `ByteString`/`Text` variants according to streaming and lifetime requirements, not merely input size.

## Measurement Workflow

1. Define the representative workload, output, compiler flags, input sizes, and required evaluation depth.
2. Establish an optimized baseline and force the demanded result outside setup timing.
3. Measure multiple samples and report variability, not only the best run.
4. Use allocation and residency evidence to distinguish CPU work, retained memory, and garbage-collection pressure.
5. Profile the relevant dimension: cost centres, heap profiles, eventlogs/thread activity, or inspected Core.
6. Change one hypothesis at a time, re-run correctness tests, and remeasure.

RTS totals such as allocation and maximum residency answer different questions from a live heap profile. A faster benchmark that evaluates less work is not an optimization of the same program.

## Optimizer-Sensitive Code

- Treat `INLINE`, `INLINABLE`, `SPECIALIZE`, rewrite `RULES`, worker/wrapper assumptions, and manual unboxing as version- and phase-sensitive.
- For each rewrite rule, document the semantic preconditions, test both sides over boundary values, and confirm whether it fires under the supported optimization levels.
- Inspect simplified Core only after compiling through the repository's actual component and flags.
- Compare `-O0` and optimized behavior when unsound FFI, unsafe code, or rewrite rules are suspected.
- Avoid performance claims from microbenchmarks alone when end-to-end allocation, contention, I/O, or residency dominates.

Do not add strictness, fusion machinery, or representation tricks pre-emptively. Measured evidence must justify the maintenance and semantic cost.
