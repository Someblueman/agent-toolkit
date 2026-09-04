# Complexity review

Use metrics to locate code worth reading, not as mechanical rewrite targets. The bundled Python analyzer reports configurable cyclomatic/cognitive complexity, nesting, parameter count and function size. It does not analyze Rust, Go, C++ or Haskell and fails when no Python files are analyzed.

Ask whether a transformation reduces the effort needed to understand the current behavior. Preserve useful domain distinctions and invariants. Prefer a guard clause when it clarifies exceptional flow; keep a straightforward loop when a fused pipeline would obscure state or ordering.

Extra complexity can be justified by a measured benefit that matters to the workload, even below an arbitrary percentage. Conversely, a large microbenchmark gain may not improve the actual application. Record the relevant tradeoff and use existing project budgets where they are contractual.

Do not create exemption ledgers or mandatory architecture tiers for ordinary simplifications. Validate the actual behavior contract using the existing tests and appropriate boundaries.
