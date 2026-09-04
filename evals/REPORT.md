# Native Skill Value Report

Correctness is the gate. Skill-specific quality, operational efficiency,
patch footprint, and reliability remain separate dimensions. Every verdict
is limited to the named tasks and exact runtime fingerprint.

## Run manifests

| batch | purpose | skill | tasks | samples/arm | runners | invalid |
|---|---|---|---:|---:|---|---:|
| `pragmatic-v2-screen-20260904` | screen | `pragmatic-engineering` | 3 | 2 | codex, omp | 0 |
| `pragmatic-v2-screen-20260904-b` | screen | `pragmatic-engineering` | 3 | 2 | codex, omp | 0 |
| `pragmatic-v2-health-codex-20260904` | validation | `pragmatic-engineering` | 1 | 1 | codex | 0 |
| `pragmatic-v2-health-omp-20260904` | validation | `pragmatic-engineering` | 1 | 1 | omp | 0 |
| `pragmatic-v2-proof-20260904` | confirmatory | `pragmatic-engineering` | 3 | 2 | codex, omp | 0 |

## Frozen identities

- `pragmatic-v2-screen-20260904` skill: `50423de0ad46fabdaf874fd907ec2749d85f19bf5d9249e0822fdacfb3671e87`
  - task `notification-cutover`: `7ec137a06c92463841e9c3781a6dc0cc9b1aa520ac040de032ffab28cf76c6dd`
  - task `receipt-tags`: `55e9de15caaeed91026bd15e05c9be46fc61e9fdfb779e64a72d99b0be4df0c3`
  - task `retry-schema`: `997b0f761e9aa4ddab3df48bac76125defac8a56b2f1457da5b765c082bff401`
  - runtime `codex`: `b33a20ab069cdd6758b55466d63065f3ec7f14e9eca9af5d0288f9400bb041f1`
  - runtime `omp`: `e9fa4b104a0f479c78c207df80e4031a5a2f81b5d1e41dd085bc24e028f9183b`
- `pragmatic-v2-screen-20260904-b` skill: `50423de0ad46fabdaf874fd907ec2749d85f19bf5d9249e0822fdacfb3671e87`
  - task `profile-field-cutover`: `c65ebf5cb92d1ed9d36ed96c3c0f76e11ca59fde1e4f3def3e9e71de344ca6c1`
  - task `single-memory-store`: `053d2433aff5eabb30373cf36ac08265d500c4a82226109d701cc458508363d2`
  - task `upload-options`: `ecacf27844b1de9e12a958fea40a11b4ce31b70f045dfca7c79e8888a13afae9`
  - runtime `codex`: `b33a20ab069cdd6758b55466d63065f3ec7f14e9eca9af5d0288f9400bb041f1`
  - runtime `omp`: `e9fa4b104a0f479c78c207df80e4031a5a2f81b5d1e41dd085bc24e028f9183b`
- `pragmatic-v2-health-codex-20260904` skill: `50423de0ad46fabdaf874fd907ec2749d85f19bf5d9249e0822fdacfb3671e87`
  - task `receipt-tags`: `55e9de15caaeed91026bd15e05c9be46fc61e9fdfb779e64a72d99b0be4df0c3`
  - runtime `codex`: `dea8f9fd770a15d335ccf0112264bacf3a1fc131ab96ce52ab7bdffbc7ec7689`
- `pragmatic-v2-health-omp-20260904` skill: `50423de0ad46fabdaf874fd907ec2749d85f19bf5d9249e0822fdacfb3671e87`
  - task `receipt-tags`: `55e9de15caaeed91026bd15e05c9be46fc61e9fdfb779e64a72d99b0be4df0c3`
  - runtime `omp`: `7e98cf0ff39d5d5346ded2d435d8b1e24985bef29bd8d08ecf35ee17cd67f0f3`
- `pragmatic-v2-proof-20260904` skill: `50423de0ad46fabdaf874fd907ec2749d85f19bf5d9249e0822fdacfb3671e87`
  - task `receipt-tags`: `55e9de15caaeed91026bd15e05c9be46fc61e9fdfb779e64a72d99b0be4df0c3`
  - task `single-memory-store`: `053d2433aff5eabb30373cf36ac08265d500c4a82226109d701cc458508363d2`
  - task `upload-options`: `ecacf27844b1de9e12a958fea40a11b4ce31b70f045dfca7c79e8888a13afae9`
  - runtime `codex`: `b33a20ab069cdd6758b55466d63065f3ec7f14e9eca9af5d0288f9400bb041f1`
  - runtime `omp`: `e9fa4b104a0f479c78c207df80e4031a5a2f81b5d1e41dd085bc24e028f9183b`

## Task-specific quality measures

- `notification-cutover`: `flows_use_typed_notifications`, `retired_module_removed`, `retired_symbol_removed`
- `profile-field-cutover`: `direct_update`, `legacy_field_removed`, `single_write_path`
- `receipt-tags`: `flows_construct_receipts_directly`, `fluent_builder_calls_removed`, `small_builder_removed`
- `retry-schema`: `legacy_decoder_removed`, `legacy_keys_removed`, `single_schema_path`
- `single-memory-store`: `concrete_store_used_directly`, `factory_removed`, `single_use_protocol_removed`
- `upload-options`: `fluent_builder_calls_removed`, `paths_construct_uploads_directly`, `small_builder_removed`

## Baseline screening

Only the without-skill arm is used. Saturated and unstable tasks must
not be promoted into a frozen comparison for that runtime.

| runner | task | correctness | quality | spread | pass | status |
|---|---|---:|---:|---:|---:|---|
| codex | notification-cutover | 1.00 | 0.33 | 0.00 | 1.00 | **informative** |
| codex | profile-field-cutover | 1.00 | 1.00 | 0.00 | 1.00 | **saturated** |
| codex | receipt-tags | 1.00 | 0.00 | 0.00 | 1.00 | **informative** |
| codex | retry-schema | 1.00 | 1.00 | 0.00 | 1.00 | **saturated** |
| codex | single-memory-store | 1.00 | 0.00 | 0.00 | 1.00 | **informative** |
| codex | upload-options | 1.00 | 0.00 | 0.00 | 1.00 | **informative** |
| omp | notification-cutover | 1.00 | 1.00 | 0.00 | 1.00 | **saturated** |
| omp | profile-field-cutover | 1.00 | 1.00 | 0.00 | 1.00 | **saturated** |
| omp | receipt-tags | 1.00 | 0.00 | 0.00 | 1.00 | **informative** |
| omp | retry-schema | 1.00 | 1.00 | 0.00 | 1.00 | **saturated** |
| omp | single-memory-store | 1.00 | 0.00 | 0.00 | 1.00 | **informative** |
| omp | upload-options | 1.00 | 0.00 | 0.00 | 1.00 | **informative** |

### Confirmatory freeze gate

- Screened 6 candidate tasks; eligible on every screened harness: receipt-tags, single-memory-store, upload-options.
- Gate status: **passed**.

## pragmatic-engineering — codex

Model: `gpt-5.6-sol`  
Runtime fingerprint: `b33a20ab069cdd6758b55466d63065f3ec7f14e9eca9af5d0288f9400bb041f1`  
Proven skill reads: 6/6 treatment runs; trace-unknown: 0  
Suite-bounded verdict: **unstable**

### Outcome and skill-specific quality

| task | correctness without→with | quality without→with | pass without→with | value |
|---|---:|---:|---:|---|
| receipt-tags | 1.00→1.00 (+0.00) | 0.00→0.00 (+0.00) | 1.00→1.00 | **no-observed-benefit** |
| single-memory-store | 1.00→1.00 (+0.00) | 1.00→1.00 (+0.00) | 1.00→1.00 | **unstable** |
| upload-options | 1.00→1.00 (+0.00) | 0.00→0.00 (+0.00) | 1.00→1.00 | **no-observed-benefit** |
- `single-memory-store` baseline quality shifted from 0.00 in screening to 1.00 in confirmation; combined spread 1.00 is **unstable**.

### Operational efficiency

Negative changes use fewer resources. Tool calls and agent steps are
native-runner counts and are comparable only within this runtime.

| task | seconds | tokens | cached | cost | tools | steps | interpretation |
|---|---:|---:|---:|---:|---:|---:|---|
| receipt-tags | 30.0→41.6 (+38%) | 95378→104414 (+9%) | 84800→85632 (+1%) | n/a | 5.0→5.5 (+10%) | 3.0→3.0 (+0%) | **more-expensive** |
| single-memory-store | 35.0→30.7 (-12%) | 93261→84158 (-10%) | 85632→72768 (-15%) | n/a | 5.0→4.0 (-20%) | 3.0→3.0 (+0%) | **more-efficient** |
| upload-options | 51.1→40.0 (-22%) | 123968→105653 (-15%) | 112192→91072 (-19%) | n/a | 6.0→6.0 (+0%) | 3.0→3.0 (+0%) | **more-efficient** |

### Patch footprint and reliability

| task | files without→with | diff +added/-deleted | final LOC without→with | timeouts without→with |
|---|---:|---:|---:|---:|
| receipt-tags | 1.00→1.50 | +1.00/-1.00→+3.00/-5.50 | 56.00→53.50 | 0.00→0.00 |
| single-memory-store | 2.00→2.00 | +4.00/-17.00→+4.00/-17.00 | 26.00→26.00 | 0.00→0.00 |
| upload-options | 2.00→2.00 | +6.00/-12.00→+6.00/-12.00 | 54.00→54.00 | 0.00→0.00 |

## pragmatic-engineering — omp

Model: `opencode-go/glm-5.3-flash`  
Runtime fingerprint: `e9fa4b104a0f479c78c207df80e4031a5a2f81b5d1e41dd085bc24e028f9183b`  
Proven skill reads: 0/6 treatment runs; trace-unknown: 6  
Suite-bounded verdict: **no-observed-benefit**

### Outcome and skill-specific quality

| task | correctness without→with | quality without→with | pass without→with | value |
|---|---:|---:|---:|---|
| receipt-tags | 1.00→1.00 (+0.00) | 0.00→0.00 (+0.00) | 1.00→1.00 | **no-observed-benefit** |
| single-memory-store | 1.00→1.00 (+0.00) | 0.00→0.00 (+0.00) | 1.00→1.00 | **no-observed-benefit** |
| upload-options | 1.00→1.00 (+0.00) | 0.00→0.00 (+0.00) | 1.00→1.00 | **no-observed-benefit** |

### Operational efficiency

Negative changes use fewer resources. Tool calls and agent steps are
native-runner counts and are comparable only within this runtime.

| task | seconds | tokens | cached | cost | tools | steps | interpretation |
|---|---:|---:|---:|---:|---:|---:|---|
| receipt-tags | 24.4→22.1 (-10%) | 97944→89233 (-9%) | 86976→79168 (-9%) | 0.0022→0.0020 (-9%) | 6.5→5.5 (-15%) | 5.5→5.0 (-9%) | **more-efficient** |
| single-memory-store | 18.1→16.5 (-9%) | 88010→97553 (+11%) | 86912→87680 (+1%) | 0.0014→0.0021 (+48%) | 4.5→5.5 (+22%) | 5.0→5.5 (+10%) | **more-expensive** |
| upload-options | 17.7→24.6 (+39%) | 71527→98730 (+38%) | 61472→97088 (+58%) | 0.0017→0.0016 (-5%) | 4.0→7.0 (+75%) | 4.0→5.5 (+38%) | **more-expensive** |

### Patch footprint and reliability

| task | files without→with | diff +added/-deleted | final LOC without→with | timeouts without→with |
|---|---:|---:|---:|---:|
| receipt-tags | 1.00→1.00 | +1.00/-1.00→+1.00/-1.00 | 56.00→56.00 | 0.00→0.00 |
| single-memory-store | 1.00→1.00 | +1.00/-1.00→+1.00/-1.00 | 39.00→39.00 | 0.00→0.00 |
| upload-options | 1.00→1.00 | +1.00/-2.00→+1.00/-1.00 | 59.00→60.00 | 0.00→0.00 |

## Across tested harnesses

- `codex` / `gpt-5.6-sol`: **unstable**
- `omp` / `opencode-go/glm-5.3-flash`: **no-observed-benefit**
- These are parallel task-bounded verdicts, not a pooled portability claim.

Activation is `unknown` unless the native trace proves a successful
skill read. Availability alone is not treated as invocation.
