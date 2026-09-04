# Native Skill Effectiveness Evals

This is the clean native-v2 evaluation harness. Pre-v2 suites, tasks, runs,
baselines, archives, and compatibility decoders are not retained. The current
tree contains one frozen suite and its three fresh task assets.

The harness compares native skill availability across Codex and OMP. It keeps
correctness, task-specific quality, efficiency, patch footprint, and reliability
as separate dimensions.

## Contract

- The `without` arm uses an isolated native profile with the target skill
  absent. The `with` arm differs only by installing the complete skill package.
- Prompts state outcomes without naming the skill's preferred design decision.
- Correctness controls `pass`. A deterministic `quality_score` and named
  `quality_checks` describe code quality separately.
- Baseline screening uses only the `without` arm and labels every task/runtime
  `informative`, `saturated`, `unstable`, `insufficient`, or `blocked`.
- Efficiency is compared only within complete pairs sharing exact task and
  runtime fingerprints. There is no pooled cross-runner or universal score.

## Workflow

Every operation requires an explicit suite path:

```bash
python3 scripts/skill_eval.py validate \
  --suite evals/suites/pragmatic-frozen-v2.toml
```

The completed fresh proof screened six candidates, froze three that were
informative on both harnesses, and ran two randomized pairs per task and
harness. To run a new confirmatory batch against the unchanged frozen contract:

```bash
python3 scripts/skill_eval.py run \
  --suite evals/suites/pragmatic-frozen-v2.toml \
  --purpose confirmatory --batch NEW-PROOF
```

Raw traces are created under gitignored `evals/results/`; sanitized numeric
records are created under `evals/history/`. `evals/REPORT.md` is generated only
from explicitly named batches. There is no archive or legacy input path.

For calibration, `scaffold/`, `flawed/`, and `reference/` are complete
workspaces. Variants are never overlaid, so clean replacement can be measured.
