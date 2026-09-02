---
name: fanout
description: Delegate tasks to bounded concurrent workers via Agy (Gemini) or OpenCode (Minimax) and collect structured results. Load when delegating independent analysis, multi-model reviews, parallel investigations, or consensus checks across non-Codex models.
---

# Fanout Task Delegation

Delegate bounded subtasks, architectural reviews, or exploratory investigations to parallel one-shot workers running in separate harnesses (Agy / Gemini and OpenCode / Minimax). Workers execute in isolated process groups under strict supervisor deadlines, emit structured results conforming to JSON schemas, and record full attempt provenance in a deterministic `packet.json`.

## When to load

Load this skill whenever:
- You need independent, non-Codex model reviews (e.g. Gemini 3.7 Flash via Agy, Minimax M3 via OpenCode).
- You want to gather multiple parallel perspectives or consensus checks on code, architecture, or plan proposals.
- You need to run exploratory code investigations without polluting your current agent context window.
- You want fault-tolerant multi-worker delegation with explicit K-of-N quorum guarantees.

## Command syntax

Invoke the standalone tool entry point `tools/fanout/bin/fanout` from the workspace root:

```sh
tools/fanout/bin/fanout <prompt_file> \
  --output <output_dir> \
  [--harness {agy,opencode}] \
  [--workers <count>] \
  [--concurrency <count>] \
  [--min-results <count>] \
  [--timeout-seconds <seconds>] \
  [--model <model_name>] \
  [--agent <agent_name>] \
  [--working-directory <path>] \
  [--agy-retries {0,1}] \
  [--max-output-bytes <bytes>]
```

### CLI Options Reference

| Option | Type | Default | Description |
|---|---|---|---|
| `<prompt_file>` | Positional Path | *Required* | Path to the markdown or text prompt file describing the task. |
| `--output` | Path | *Required* | Destination directory for results and `packet.json` (must not exist or be empty). |
| `--harness` | `agy` \| `opencode` | `agy` | Execution harness to use. |
| `--workers` | Integer (1..50) | `4` | Total number of worker instances to launch. |
| `--concurrency` | Integer (1..workers) | `min(4, workers)` | Maximum concurrent worker processes in flight. |
| `--min-results` | Integer (1..workers) | `workers` | Minimum valid results needed for exit code 0 (K-of-N threshold). |
| `--timeout-seconds` | Float (> 1.0) | `300.0` | Per-attempt execution timeout in seconds. |
| `--model` | String | Harness default | Model route override (`gemini-3.7-flash-low` for Agy, `opencode-go/minimax-m3` for OpenCode). |
| `--agent` | String | `plan` | OpenCode agent profile (only applicable when `--harness opencode`). |
| `--working-directory`| Path | Current directory | Working directory context for worker processes. |
| `--agy-retries` | `0` \| `1` | `1` | Max transient retries (timeout/nonzero) for Agy workers. |
| `--max-output-bytes` | Integer (>= 1024) | `1000000` | Max stdout/stderr capture limit in bytes per attempt. |

### Exit Codes

- `0`: **Success** — Quorum threshold met (`valid_results >= min_results`).
- `1`: **Threshold Unmet** — Execution finished, but fewer than `min_results` succeeded.
- `2`: **Error** — Argument validation failed, missing files/executables, or unhandled OS error.

## Worker selection & harnesses

Choose the harness matching the task characteristics and isolation requirements:

### 1. Agy Harness (`--harness agy`)
- **Default Model**: `gemini-3.7-flash-low`
- **Execution Mode**: Runs `agy --mode plan --sandbox --output-format json --json-schema schemas/worker-result.schema.json`.
- **Isolation**: Read-only plan sandbox mode. Cannot mutate disk.
- **Retry Policy**: Includes 1 automatic retry (`--agy-retries 1`) for transient timeouts or nonzero exits. Schema violations and oversized output are never retried.
- **Output Schema**:
  ```json
  {
    "worker_id": "worker-0001",
    "summary": "High-level summary of analysis",
    "findings": ["Specific finding item 1", "Specific finding item 2"],
    "uncertainties": ["Question or area requiring human/caller verification"]
  }
  ```
- **Best For**: Fast second opinions, architectural review, risk analysis, code sanity checks, multi-agent advisory councils.

### 2. OpenCode Harness (`--harness opencode`)
- **Default Model**: `opencode-go/minimax-m3`
- **Execution Mode**: Spawns an ephemeral OpenCode SDK v2 server per worker via `lib/opencode_worker.mjs` on an isolated TCP port.
- **Isolation & Tools**: Uses the specified `--agent` profile (default: `plan`, or `build`, etc.) with that agent's configured tools (such as `read`, `grep`, `glob`, `bash`).
- **Retry Policy**: Single attempt per worker (no automatic retry).
- **Universal Receipt**:
  ```json
  {
    "worker_id": "worker-0001",
    "outcome": "completed",
    "summary": "Concise outcome explanation",
    "result_json": "{\"task_key\": \"task_value\"}"
  }
  ```
  The supervisor validates the outer receipt and parses `result_json` into `result.payload`. Only `outcome: "completed"` counts toward `valid_results`.
- **Best For**: Deep codebase exploration, execution planning, repository search, or tasks requiring multi-turn tool interaction.

## Result interpretation (`packet.json`)

All execution results are compiled into `<output_dir>/packet.json` (permissions `0600`). The JSON schema version 3 structure is:

```json
{
  "schema_version": 3,
  "harness": "agy",
  "model": "gemini-3.7-flash-low",
  "agent": null,
  "prompt_path": "/path/to/prompt.md",
  "prompt_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "requested_workers": 4,
  "concurrency": 4,
  "timeout_seconds": 90.0,
  "agy_retries": 1,
  "total_retries": 0,
  "min_results": 3,
  "valid_results": 4,
  "total_tokens": 128450,
  "total_cost_usd": 0.01425,
  "elapsed_seconds": 24.18,
  "workers": [
    {
      "worker_id": "worker-0001",
      "status": "ok",
      "attempt_count": 1,
      "attempts": [
        {
          "attempt": 1,
          "returncode": 0,
          "elapsed_seconds": 18.2,
          "stdout_path": "worker-0001/attempt-1/stdout.json",
          "stderr_path": "worker-0001/attempt-1/stderr.log",
          "log_path": "worker-0001/attempt-1/agy.log",
          "status": "ok",
          "result": {
            "worker_id": "worker-0001",
            "summary": "Identified 2 race conditions in cache manager",
            "findings": [
              "Cache eviction does not acquire lock before modifying linked list",
              "TTL expiry check uses non-monotonic clock"
            ],
            "uncertainties": [
              "Whether background cleaner thread runs in test environments"
            ]
          },
          "usage": { "total_tokens": 32100 }
        }
      ],
      "result": {
        "worker_id": "worker-0001",
        "summary": "Identified 2 race conditions in cache manager",
        "findings": [
          "Cache eviction does not acquire lock before modifying linked list",
          "TTL expiry check uses non-monotonic clock"
        ],
        "uncertainties": [
          "Whether background cleaner thread runs in test environments"
        ]
      }
    }
  ]
}
```

### Worker Status Codes

- `ok`: Worker completed successfully with schema-valid output (or OpenCode `outcome: "completed"`).
- `nonzero_exit`: Harness subprocess exited with a non-zero exit code.
- `timeout`: Subprocess exceeded `--timeout-seconds` and its process group was terminated.
- `oversized_output`: Worker stdout or stderr exceeded `--max-output-bytes`.
- `malformed_output`: Worker stdout could not be parsed as valid JSON.
- `invalid_result`: Output JSON violated the schema constraints, had missing/extra keys, or mismatched `worker_id`.
- `blocked` / `failed`: OpenCode worker completed with an explicit `blocked` or `failed` receipt outcome (preserved in packet, but not counted toward `valid_results`).

### Synthesis & Grounding Workflow

1. **Check Quorum**: Verify `valid_results >= min_results`. If exit code is 1, inspect failed workers in `packet.json` to understand why.
2. **Aggregate Findings**: Extract `findings` (Agy) or `payload` (OpenCode) across all valid workers.
3. **Cluster & Compare**: Identify consensus findings (flagged by multiple workers) versus unique outliers.
4. **Ground Truth Verification**: Always verify findings against actual codebase files (using `view_file` or `grep_search`). Do not take worker claims as ground truth without verification.
5. **Formulate Final Answer**: Synthesize verified findings into your response, noting any remaining uncertainties.

## Practical examples

### Example 1: Multi-Perspective Code Architecture Review (Agy / Gemini)

```sh
# 1. Create prompt
cat << 'EOF' > /tmp/arch-review-prompt.md
Review the proposed async database connection pool in src/db/pool.py.
Identify potential concurrency bottlenecks, resource leaks, or lifecycle issues.
EOF

# 2. Run 4 workers with quorum threshold of 3
tools/fanout/bin/fanout /tmp/arch-review-prompt.md \
  --harness agy \
  --workers 4 \
  --concurrency 4 \
  --min-results 3 \
  --timeout-seconds 90 \
  --output runs/arch-review-01
```

### Example 2: Investigation with OpenCode Tools

```sh
# 1. Create prompt
cat << 'EOF' > /tmp/test-failure-prompt.md
Investigate why tests in tests/integration/test_sync.py are flaking on macOS.
Examine socket timeouts and thread locking in src/sync/worker.py.
Return your diagnosis in structured JSON payload with keys "root_cause" and "recommended_fix".
EOF

# 2. Run 3 OpenCode workers using the plan agent
tools/fanout/bin/fanout /tmp/test-failure-prompt.md \
  --harness opencode \
  --agent plan \
  --workers 3 \
  --concurrency 3 \
  --min-results 2 \
  --timeout-seconds 120 \
  --output runs/flaky-test-investigation
```

### Example 3: Advisory Consensus Check with Custom Model & Timeout

```sh
tools/fanout/bin/fanout /tmp/rfc-proposal.md \
  --harness agy \
  --model gemini-3.7-flash-low \
  --workers 5 \
  --concurrency 5 \
  --min-results 4 \
  --timeout-seconds 60 \
  --agy-retries 1 \
  --output runs/rfc-consensus
```
