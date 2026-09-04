# Behavioral comparison

Define the observable contract before simplifying: outputs, exceptions, mutations, ordering, serialized representation, resource lifecycle and numeric semantics. Existing domain tests are usually the best starting point. Select boundaries and randomized cases from the risk, not a fixed count.

The bundled invariant checker supports:

- Python functions with an explicit nonempty `TEST_CASES` list of `(args, kwargs)` pairs. Each function gets independent deep copies; return values and mutated inputs are snapshotted and compared. Values that cannot be copied need a domain-specific case factory in the repository test harness.
- Command strings with `--cases` containing a nonempty JSON array of literal single arguments. Commands are parsed into argv without a shell and have a 30-second timeout. Exit code, stdout and stderr are compared exactly. Expected failures may match; establish that the supplied corpus actually exercises the intended behavior.
- Golden JSON with nonempty `test_cases`, each containing `id`, `input`, and `expected`. Candidate exceptions fail rather than being confused with expected strings.

Types and integers remain exact. Float tolerance is opt-in through the Python API; NaN does not establish equality. No UUIDs, timestamps, addresses or process IDs are automatically removed: a normalization can hide a real regression and needs a domain-specific justification and test.

This helper does not isolate module globals, external resources or process-wide state, and does not prove alias identity, termination or all possible behavior. Use isolated processes or the native test harness for those contracts. Its elapsed times are diagnostics, not a statistically supported speedup measurement. State the tested corpus and remaining limits instead of claiming universal invariance.
