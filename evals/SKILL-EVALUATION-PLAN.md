# Native-v2 Skill Evaluation Plan and Result

Status: implemented and proved from a fresh start

Date: 2026-09-04

## Goal

Measure whether native access to `pragmatic-engineering` changes correctness,
task-specific code quality, efficiency, footprint, or reliability on Codex and
OMP without carrying forward any pre-v2 evidence or compatibility path.

## Implemented replacement

- One strict native-v2 schema and CLI with explicit suite paths.
- Native package isolation; prompts never contain skill instructions.
- Complete calibration workspaces, allowing obsolete files to be removed.
- Correctness as the pass gate, with named deterministic quality checks.
- Per-pair duration, tokens/cache/cost, tool calls, agent steps, patch size,
  timeout, and invalid-run evidence.
- Exact task, skill, runner, model, version, threshold, and runtime fingerprints.
- Baseline screening plus saturated, unstable, insufficient, and blocked labels.
- Separate quality and efficiency verdicts; no universal composite.

Pre-v2 tasks, suites, baselines, results, reports, archives, and fallback
decoders were deleted. Rejected fresh candidate task assets were deleted after
screening rather than archived.

## Executed proof

1. Six fresh candidates were calibrated twice offline.
2. Two without-skill samples per task and harness selected `receipt-tags`,
   `single-memory-store`, and `upload-options` as cross-harness informative.
3. Health pairs verified isolation and runtime health on Codex `gpt-5.6-sol`
   and OMP `opencode-go/glm-5.3-flash`.
4. The frozen suite ran two randomized with/without pairs per task and harness:
   24 valid records, 24 correctness passes, and zero timeouts.

## Result

- Codex proved a native skill read in all six treatment runs. Neither stable
  task improved in quality. The store task's baseline shifted from 0.00 quality
  during screening to 1.00 during confirmation, so its result is unstable.
- OMP used the exact requested provider/model with fallback disabled. Its trace
  cannot prove file reads; none of the three tasks improved in quality.
- Efficiency was mixed rather than absent: Codex treatment was cheaper on two
  tasks and costlier on one; OMP treatment was cheaper on one and costlier on
  two. Footprint and reliability remain visible separately in `REPORT.md`.
- The defensible conclusion is task-bounded: this fresh suite found no code-
  quality benefit from the current skill, and no consistent efficiency benefit.

The harness now distinguishes a negative result from saturation, instability,
infrastructure failure, or missing telemetry. Improving the skill itself should
be a separate change wave, evaluated against a new frozen task set.

## Deliberately absent

No legacy decoder, archive, database, dashboard, compatibility shim, forced
prompt-exposure arm, cross-harness pooling, universal composite score, or
arbitrary five-task gate.
