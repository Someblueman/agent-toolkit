# Complexity review

Use size and repetition to locate review candidates, then inspect cohesion and the current task. The default 500-line file and 150-line inline-test thresholds are advisory. Do not split a file mechanically or add modules merely to satisfy a counter. The checker supports `--strict` for projects that explicitly require hard limits.

Prefer concrete domain operations over speculative layers. Introduce traits, protocols or interfaces when they express a useful current contract; there is no minimum implementation count. Choose direct construction, constructors or builders according to invariants and call-site clarity, not field count.

Tests should reproduce the changed behavior and cover consequential failure boundaries. Keep fixtures small and use the existing harness. Real CLI, browser, filesystem and subprocess tests are appropriate for features at those boundaries. A filename cannot establish whether a test is useful. Avoid redundant tests and custom runners that add no evidence.

When a module needs decomposition, move a cohesive responsibility and its tests together, update imports/callers, and verify the affected path. Do not combine an unrelated architecture rewrite with a localized repair.
