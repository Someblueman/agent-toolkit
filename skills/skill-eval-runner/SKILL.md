---
name: skill-eval-runner
description: Run native v2 with/without skill evaluations in agent-toolkit, including baseline screening, deterministic correctness and quality calibration, paired efficiency telemetry, and task-bounded reporting across Codex and OMP.
---

# Skill Eval Runner

Use `scripts/skill_eval.py` as the only CLI entry point and read
`evals/README.md` before changing or running an experiment.

## Invariants

- Install or omit the complete target skill through each harness's native skill
  path. Never prepend the skill instructions to the task prompt.
- Keep prompts outcome-focused. Do not name the skill's preferred implementation
  choice in a candidate task.
- Treat correctness as the pass gate. Report deterministic task-specific quality,
  efficiency, footprint, and reliability separately; never create one skill score.
- Compare only complete pairs with identical task and runtime fingerprints.
- Never modify the measured skill, task, grader, fixture, or threshold after a
  confirmatory batch begins.

## Protocol

1. Validate candidate graders offline:

   ```bash
   python3 scripts/skill_eval.py validate --suite SUITE.toml
   ```

   Each pristine, flawed, and reference fixture is graded twice. The flawed
   fixture must pass correctness while scoring below the reference on quality.

2. Screen at most six candidates without the skill:

   ```bash
   python3 scripts/skill_eval.py run --suite SUITE.toml \
     --purpose screen --batch BATCH
   ```

   Require at least three tasks labeled `informative` on every intended harness.
   Reject `saturated`, `unstable`, `insufficient`, and `blocked` strata. Do not
   inspect a with-skill result before freezing the final tasks.

3. Create a frozen suite containing exactly three eligible tasks. Run one
   non-evidentiary pair per harness and inspect raw traces for package isolation,
   requested-model identity, and provider health.

4. Run two randomized adjacent pairs per task and harness:

   ```bash
   python3 scripts/skill_eval.py run --suite FROZEN.toml \
     --purpose confirmatory --batch BATCH
   ```

5. Generate a report from explicit v2 batches. Report task-level value and
   efficiency separately. Do not pool runners or claim general usefulness from
   a three-task proof.

## Failure boundaries

- Provider/authentication/model/fallback/pre-start failures are infrastructure-
  invalid. Package leakage or omission is isolation-invalid. A malformed grader
  result is evaluator-invalid.
- Fixed-budget exhaustion after work begins is a valid outcome and retains its
  measured cost and graded workspace.
- Any invalid confirmatory record blocks that exact runtime verdict.
- If the six-candidate screen cannot produce three cross-harness tasks, stop
  with that task-design blocker. Do not weaken thresholds or broaden the batch.

Raw traces live under gitignored `evals/results/`; sanitized numeric history
lives under `evals/history/`. Activation is `unknown` unless a native trace
proves a successful skill read.
