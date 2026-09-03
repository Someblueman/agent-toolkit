# Skill Effectiveness Report

Batches: `20260903T094508_323e`, `20260903T143535_3094`, `ext-sh-1`, `msgclean-fix1`  |  Generated: 2026-09-03T15:13:08+00:00
- `20260903T094508_323e`: samples/arm=2, models={'codex': 'gpt-5.6-sol', 'opencode': 'opencode/big-pickle', 'omp': 'openai-codex/gpt-5.6-sol'}, versions={'opencode': '1.18.27', 'omp': 'omp/18.1.4'}
- `20260903T143535_3094`: samples/arm=2, models={'codex': 'gpt-5.6-sol', 'opencode': 'opencode/big-pickle', 'omp': 'openai-codex/gpt-5.6-sol'}, versions={'codex': 'codex-cli 0.149.1', 'opencode': '1.18.27', 'omp': 'omp/18.1.4'}
- `ext-sh-1`: samples/arm=2, models={'codex': 'gpt-5.6-sol', 'opencode': 'opencode/big-pickle', 'omp': 'openai-codex/gpt-5.6-sol'}, versions={'opencode': '1.18.27', 'omp': 'omp/18.1.4'}
- `msgclean-fix1`: samples/arm=2, models={'codex': 'gpt-5.6-sol', 'opencode': 'opencode/big-pickle', 'omp': 'openai-codex/gpt-5.6-sol'}, versions={'codex': 'codex-cli 0.149.1', 'opencode': '1.18.27', 'omp': 'omp/18.1.4'}

Each cell: pass rate [95% Wilson CI] over scored (valid) runs.
`metric` is the task's mechanical metric (mean over runs with a
value). `delta` = with-skill minus without-skill; for
lower-is-better metrics a negative delta is an improvement.

**21 run(s) excluded from scoring** (infra failures, isolation leaks, or post-run invalidation):
See raw JSON under `evals/results/`.

## event-sink-concrete

Skill: `pragmatic-engineering`

| runner | without | with | delta (pass rate) | metric w/o | metric with |
|---|---|---|---|---|---|
| codex | 1.0 [0.342,1.0] (n=2) | 1.0 [0.342,1.0] (n=2) | +0.000 | 0.0 | 0.0 |
| omp | 1.0 [0.342,1.0] (n=2) | 1.0 [0.342,1.0] (n=2) | +0.000 | 0.0 | 0.0 |
| opencode | 1.0 [0.342,1.0] (n=2) | 1.0 [0.342,1.0] (n=2) | +0.000 | 0.0 | 0.0 |

## fanout-cancel-batch

Skill: `python-engineering`

| runner | without | with | delta (pass rate) | metric w/o | metric with |
|---|---|---|---|---|---|
| codex | 1.0 [0.342,1.0] (n=2) | 1.0 [0.342,1.0] (n=2) | +0.000 | 0.1 | 0.1 |
| omp | 1.0 [0.342,1.0] (n=2) | 1.0 [0.342,1.0] (n=2) | +0.000 | 0.1 | 0.1 |
| opencode | 1.0 [0.342,1.0] (n=2) | 1.0 [0.207,1.0] (n=1) | +0.000 | 0.1 | 0.1 |

## go-error-chain

Skill: `go-engineering`

| runner | without | with | delta (pass rate) | metric w/o | metric with |
|---|---|---|---|---|---|
| omp | 1.0 [0.342,1.0] (n=2) | 1.0 [0.342,1.0] (n=2) | +0.000 | - | - |
| opencode | 1.0 [0.342,1.0] (n=2) | 1.0 [0.342,1.0] (n=2) | +0.000 | - | - |

## msg-clean-cutover

Skill: `pragmatic-engineering`

| runner | without | with | delta (pass rate) | metric w/o | metric with |
|---|---|---|---|---|---|
| omp | 1.0 [0.342,1.0] (n=2) | 0.0 [0.0,0.658] (n=2) | -1.000 | - | - |
| opencode | 1.0 [0.342,1.0] (n=2) | 0.5 [0.095,0.905] (n=2) | -0.500 | - | - |

## regex-recompile-per-row

Skill: `profiling-software-performance`

| runner | without | with | delta (pass rate) | metric w/o | metric with |
|---|---|---|---|---|---|
| omp | - | 1.0 [0.207,1.0] (n=1) |  | - | 5.96 |
| opencode | 0.5 [0.095,0.905] (n=2) | 0.0 [0.0,0.658] (n=2) | -0.500 | 5.85 | - |

## sh-rollup-probe

Skill: `shell-engineering`

| runner | without | with | delta (pass rate) | metric w/o | metric with |
|---|---|---|---|---|---|
| omp | 1.0 [0.51,1.0] (n=4) | 1.0 [0.51,1.0] (n=4) | +0.000 | - | - |
| opencode | 0.75 [0.301,0.954] (n=4) | 0.5 [0.15,0.85] (n=4) | -0.250 | - | - |

## soa-layout-rewrite

Skill: `hardware-aware-optimization`

| runner | without | with | delta (pass rate) | metric w/o | metric with |
|---|---|---|---|---|---|
| omp | 1.0 [0.207,1.0] (n=1) | 0.5 [0.095,0.905] (n=2) | -0.500 | 7.76 | 7.49 |
| opencode | 1.0 [0.342,1.0] (n=2) | 1.0 [0.342,1.0] (n=2) | +0.000 | 8.415 | 8.65 |

`*` = non-overlapping 95% CIs (distinguishable at this N).

## Sample-size calibration

Wilson CI half-width ~1.96*sqrt(p(1-p)/n); separating two arms at a
true pass-rate gap g needs roughly n ~ 3/g^2 samples per arm
(g=0.3 -> ~33; g=0.5 -> ~12). Current N per arm and verdicts:

| task | runner | N per arm | verdict |
|---|---|---|---|
| event-sink-concrete | codex | 2 | saturated: both arms at ceiling; add a harder task, more N won't help |
| event-sink-concrete | omp | 2 | saturated: both arms at ceiling; add a harder task, more N won't help |
| event-sink-concrete | opencode | 2 | saturated: both arms at ceiling; add a harder task, more N won't help |
| fanout-cancel-batch | codex | 2 | saturated: both arms at ceiling; add a harder task, more N won't help |
| fanout-cancel-batch | omp | 2 | saturated: both arms at ceiling; add a harder task, more N won't help |
| fanout-cancel-batch | opencode | 2 | saturated: both arms at ceiling; add a harder task, more N won't help |
| go-error-chain | omp | 2 | saturated: both arms at ceiling; add a harder task, more N won't help |
| go-error-chain | opencode | 2 | saturated: both arms at ceiling; add a harder task, more N won't help |
| msg-clean-cutover | omp | 2 | overlapping; est. n~3/arm to resolve gap 1.00 |
| msg-clean-cutover | opencode | 2 | overlapping; est. n~12/arm to resolve gap 0.50 |
| regex-recompile-per-row | omp | 0 | no valid runs in one arm (infra failures) - not scorable |
| regex-recompile-per-row | opencode | 2 | overlapping; est. n~12/arm to resolve gap 0.50 |
| sh-rollup-probe | omp | 4 | saturated: both arms at ceiling; add a harder task, more N won't help |
| sh-rollup-probe | opencode | 4 | overlapping; est. n~48/arm to resolve gap 0.25 |
| soa-layout-rewrite | omp | 1 | overlapping; est. n~12/arm to resolve gap 0.50 |
| soa-layout-rewrite | opencode | 2 | saturated: both arms at ceiling; add a harder task, more N won't help |

Increase `--samples`, rerun `run` then `report`, until the arms' CIs
reliably separate (or reliably don't) for the conclusion you need.
