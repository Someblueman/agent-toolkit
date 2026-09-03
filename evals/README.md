# Skill Effectiveness Evals

Deterministic measurement of whether loading a skill changes agent output.

- `tasks/<task-id>/` — one eval task per directory:
  - `task.md` — the prompt given to the agent.
  - `scaffold/` — files copied into a fresh run workspace.
  - `verify.py` — mechanical scorer. Prints one line `METRICS {...}` (JSON) and
    exits 0 on pass, non-zero on fail. No judgment, no model output parsing.
- `REPORT.md` — committed baseline/current scores with with/without deltas.

- `archive/` — retired series-v0 material: calibration report, reconstructed
  batch manifests (raw v0 run records were destroyed by an over-broad
  cleanup on 2026-09-03; nothing was fabricated to replace them).
- `results/` — raw per-run JSON (gitignored; includes model stdout/stderr
  tails, so it must never be committed). Batch metadata (samples, models,
  runner versions, task fingerprints, harness revision, series) lives in
  each batch's `manifest.json`, mirrored in the committed `REPORT.md`.

Provenance: series-v1 tasks were designed against the specific rules of the
skill they measure (each `task.md` states only the observable business
contract; the mechanism the skill teaches is never named). Series-v0 tasks
derived from the skills' own evaluation references; they are retired.

Per-task provenance and the series-v0 calibration ladder (N=5 saturated on
all runners) are recorded in `archive/REPORT-v0-calibration.md`.

## Series v1 pilot results (n=2/arm, 3 runners; sh-rollup n=4)

- **Saturated (no discrimination):** event-sink-concrete, fanout-cancel-batch,
  go-error-chain (all runners 100% both arms); sh-rollup-probe on omp; soa on
  opencode (agents reach ~8x SoA unaided - the World API invites the fix);
  regex on its passing runs (5.8-5.9x unaided).
- **Initially universal fail, then negative after fix:** msg-clean-cutover
  first went 0/10 both arms (every agent retained the legacy function).
  After restoring the one-send-path requirement to the prompt:
  agents clean-cut 4/4 (deleted the legacy function outright); with-skill
  agents kept a forwarding shim 3/4 times (`single_path` gate). Reading the
  skill's compatibility guidance appears to make agents MORE conservative
  about deleting code, not less. Codex rows are 404s from the chatgpt
  backend endpoint (server-side, not quota); opencode had 420s timeouts on
  3 runs in the main batch (run caps since raised to 900s/840s).

**Headline finding after 7 redesigned tasks and ~90 scored runs:** none of
the five evaluated skills produced a measurable with/without pass-rate delta
on current frontier models via mechanical metrics. Frontier models either
solve these tasks unaided (ceiling) or fail for reasons the skill text does
not address (floor). Making skills measurably effective - or detecting their
effect - likely requires harder/multi-step tasks, quality-graded metrics
rather than pass/fail, or models below frontier capability.

## Series v0 (retired calibration, archived)

The original tasks (py-async-endpoint, tax-refactor, hot-path-optimize) are
retired: saturated at N=5 on all runners (see
`archive/REPORT-v0-calibration.md`). Raw v0 run records were destroyed by an
over-broad cleanup on 2026-09-03; aggregate report and reconstructed
manifests survive under `archive/`.
