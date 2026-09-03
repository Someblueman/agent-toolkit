# Skill Effectiveness Report

Batches: `20260903T013927_841c`, `20260903T020643_3aa5`, `20260903T022838_2ee6`  |  Generated: 2026-09-03T09:29:17+00:00
- `20260903T013927_841c`: samples/arm=5, models={'codex': 'gpt-5.6-sol', 'opencode': 'opencode/big-pickle', 'omp': 'openai-codex/gpt-5.6-sol'}, versions={'codex': 'codex-cli 0.149.1', 'opencode': '1.18.27', 'omp': 'omp/18.1.4'}
- `20260903T020643_3aa5`: samples/arm=5, models={'codex': 'gpt-5.6-sol', 'opencode': 'opencode/big-pickle', 'omp': 'openai-codex/gpt-5.6-sol'}, versions={'codex': 'codex-cli 0.149.1', 'opencode': '1.18.27', 'omp': 'omp/18.1.4'}
- `20260903T022838_2ee6`: samples/arm=5, models={'codex': 'gpt-5.6-sol', 'opencode': 'opencode/big-pickle', 'omp': 'openai-codex/gpt-5.6-sol'}, versions={'codex': 'codex-cli 0.149.1', 'opencode': '1.18.27', 'omp': 'omp/18.1.4'}

Each cell: pass rate [95% Wilson CI] over scored (valid) runs.
`metric` is the task's mechanical metric (mean over runs with a
value). `delta` = with-skill minus without-skill; for
lower-is-better metrics a negative delta is an improvement.

## hot-path-optimize

Skill: `profiling-software-performance`

| runner | without | with | delta (pass rate) | metric w/o | metric with |
|---|---|---|---|---|---|
| codex | 1.0 [0.566,1.0] (n=5) | 1.0 [0.566,1.0] (n=5) | +0.000 | 861.04 | 856.8 |
| omp | 1.0 [0.566,1.0] (n=5) | 1.0 [0.566,1.0] (n=5) | +0.000 | 908.98 | 876.2 |
| opencode | 1.0 [0.566,1.0] (n=5) | 1.0 [0.566,1.0] (n=5) | +0.000 | 762.64 | 785.44 |

## py-async-endpoint

Skill: `python-engineering`

| runner | without | with | delta (pass rate) | metric w/o | metric with |
|---|---|---|---|---|---|
| codex | 1.0 [0.566,1.0] (n=5) | 1.0 [0.566,1.0] (n=5) | +0.000 | 0.58 | 0.556 |
| omp | 1.0 [0.566,1.0] (n=5) | 1.0 [0.566,1.0] (n=5) | +0.000 | 0.902 | 0.556 |
| opencode | 1.0 [0.566,1.0] (n=5) | 1.0 [0.566,1.0] (n=5) | +0.000 | 0.521 | 0.474 |

## tax-refactor

Skill: `pragmatic-engineering`

| runner | without | with | delta (pass rate) | metric w/o | metric with |
|---|---|---|---|---|---|
| codex | 1.0 [0.566,1.0] (n=5) | 1.0 [0.566,1.0] (n=5) | +0.000 | - | - |
| omp | 1.0 [0.566,1.0] (n=5) | 1.0 [0.566,1.0] (n=5) | +0.000 | - | - |
| opencode | 0.8 [0.376,0.964] (n=5) | 1.0 [0.566,1.0] (n=5) | +0.200 | - | - |

`*` = non-overlapping 95% CIs (distinguishable at this N).

## Sample-size calibration

Wilson CI half-width ~1.96*sqrt(p(1-p)/n); separating two arms at a
true pass-rate gap g needs roughly n ~ 3/g^2 samples per arm
(g=0.3 -> ~33; g=0.5 -> ~12). Current N per arm and verdicts:

| task | runner | N per arm | verdict |
|---|---|---|---|
| hot-path-optimize | codex | 5 | saturated: both arms at ceiling; add a harder task, more N won't help |
| hot-path-optimize | omp | 5 | saturated: both arms at ceiling; add a harder task, more N won't help |
| hot-path-optimize | opencode | 5 | saturated: both arms at ceiling; add a harder task, more N won't help |
| py-async-endpoint | codex | 5 | saturated: both arms at ceiling; add a harder task, more N won't help |
| py-async-endpoint | omp | 5 | saturated: both arms at ceiling; add a harder task, more N won't help |
| py-async-endpoint | opencode | 5 | saturated: both arms at ceiling; add a harder task, more N won't help |
| tax-refactor | codex | 5 | saturated: both arms at ceiling; add a harder task, more N won't help |
| tax-refactor | omp | 5 | saturated: both arms at ceiling; add a harder task, more N won't help |
| tax-refactor | opencode | 5 | overlapping; est. n~75/arm to resolve gap 0.20 |

Increase `--samples`, rerun `run` then `report`, until the arms' CIs
reliably separate (or reliably don't) for the conclusion you need.
