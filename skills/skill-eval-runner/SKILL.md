---
name: skill-eval-runner
description: Run deterministic skill-effectiveness evals (with/without A/B across codex, opencode, omp) in agent-toolkit, calibrate sample sizes, and produce batch-scoped reports. Use when measuring whether a skill changes agent output, after editing a skill, or when adding an eval task.
---

# Skill Eval Runner

Measure whether a skill in this repo changes agent output, deterministically.
Never hand-judge model outputs; only `verify.py` metrics count.

## When to use

- Re-measuring skill effectiveness after skill edits (hill-climbing).
- Adding an eval task for a new skill.
- Comparing runners (codex, opencode, omp) or sample sizes.

## Layout

- `scripts/skill_eval.py` — the only entry point. `run`, `probe`, `report`.
- `evals/tasks/<task-id>/` — `task.md` (agent prompt), `scaffold/` (copied to
  a fresh workspace per run), `verify.py` (hidden mechanical scorer; never
  copied into the agent workspace).
- `evals/results/<batch>/` — one batch per `run` invocation: `manifest.json`
  plus raw per-run JSON.
- `evals/REPORT.md` — committed report, built from exactly one batch.

## Workflow

1. **Isolation probe first** (cheap, catches contamination):
   `python3 scripts/skill_eval.py probe`
   Each runner must show no target-repo skills. Expected residual context:
   codex shows only its built-in product skills; omp shows only its built-in
   system prompt; opencode replies NONE. If a probe lists a repo skill,
   STOP — the without-arm is contaminated.
2. **Run a batch**:
   `python3 scripts/skill_eval.py run --samples N --concurrency 6`
   - Arms: `with` = SKILL.md prepended to the prompt; `without` = prompt only.
   - Every run uses an isolated config home (CODEX_HOME / XDG dirs / fake
     HOME), so shared installed skills cannot leak into the baseline.
   - Runs failing for infrastructure reasons (auth, timeout, isolation leak,
     missing verifier output) are marked invalid and excluded automatically.
3. **Report**: generated automatically after `run`; rebuild with
   `python3 scripts/skill_eval.py report [--batch ID]`.
   Batches pool per task only when runner config AND the task's content
   fingerprint (SKILL.md + task.md + verify.py + scaffold) match — any edit
   to a skill or an eval resets pooling for that task, so pre/post-edit
   results can never be mixed. Never pool across fingerprints; compare one
   batch (or fingerprint-equal batches) against each other. Pooling also
   requires an identical `harness` fingerprint in the manifest — adapter or
   CLI-protocol changes start a new measurement series even when recorded
   models and versions are unchanged.

## Sample-size calibration

Wilson 95% CIs are in the report. To separate a true pass-rate gap `g`, you
need roughly `n ≈ 3/g²` valid runs per arm (g=0.3 → ~33, g=0.5 → ~12). Start
at N=5; only scale up when the arms' CIs overlap and the gap matters. Increase
in small steps — each +5 per arm costs real plan quota.

## Adding a task for a new skill

1. `evals/tasks/<task-id>/scaffold/` — small, stdlib-only, runnable offline.
2. `task.md` — describe the *problem*, not the solution. Hints that reveal
   the fix (or acceptance criteria) produce ceiling effects: both arms score
   the same and the delta measures noise. A temptation to do the wrong thing
   is fine; an explicit *requirement* to do the wrong thing is not (that
   scores disobedience, not engineering).
3. `verify.py` — prints `METRICS {...}` (JSON) as its last line, exit 0 = pass.
   Validate both directions: must FAIL on the pristine scaffold and PASS on a
   reference solution. Metrics should be threshold-anchored to the honest
   best fix (e.g. CPU-bound work cannot be parallelized past the GIL — do
   not set wall-time targets below the serial floor).
4. Register it in `TASKS` in `scripts/skill_eval.py` with its skill mapping
   and headline metric.

## Rules

- Never modify `skills/` content as part of an eval run — measure, don't fix.
- Never let the agent see `verify.py` or the acceptance thresholds in the
  prompt.
- Credentials: runners authenticate via copied auth files inside temp dirs;
  never print those files' contents.
