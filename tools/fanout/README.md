# tools/fanout: Standalone Multi-Worker Delegation Engine

`tools/fanout` is a standalone, bounded execution engine and CLI tool that delegates tasks to concurrent one-shot workers running in separate harnesses (Agy / Gemini and OpenCode / Minimax) with strict process-group lifecycle isolation, bounded timeouts, single transient retry, atomic result packets, and K-of-N quorum verification.

---

## Architecture

```text
                               ┌────────────────────────────────────────────────────────┐
                               │               tools/fanout/bin/fanout                  │
                               │  (Asyncio Supervisor, Bounded Semaphore, Signal Trap)   │
                               └───────────┬────────────────────────────────┬───────────┘
                                           │                                │
                     ┌─────────────────────┴──────────────┐   ┌─────────────┴──────────────────────┐
                     │         --harness agy              │   │        --harness opencode          │
                     │  (Antigravity Plan Sandbox)        │   │  (Ephemeral SDK v2 Node Helper)    │
                     └─────────────┬──────────────────────┘   └─────────────┬──────────────────────┘
                                   │                                        │
                    ┌──────────────▼──────────────┐          ┌──────────────▼──────────────┐
                    │ Worker 1..N (Process Group) │          │ Worker 1..N (Process Group) │
                    │ - setsid (new session)      │          │ - setsid (new session)      │
                    │ - agy --mode plan --sandbox │          │ - node opencode_worker.mjs  │
                    │ - worker-result.schema.json │          │ - private TCP port server   │
                    │ - 1x retry on timeout/error │          │ - receipt + result_json     │
                    │ - attempt-N/ private logs   │          │ - stdout.json / stderr.log  │
                    └──────────────┬──────────────┘          └──────────────┬──────────────┘
                                   │                                        │
                                   └───────────────────┬────────────────────┘
                                                       │
                                           ┌───────────▼────────────┐
                                           │  Atomic os.replace     │
                                           │  <output>/packet.json  │
                                           │  (Schema Version 3)    │
                                           └────────────────────────┘
```

The tool is structured into three primary subdirectories:
- `bin/fanout`: Executable CLI entry point (`chmod +x`). Handles option parsing, semaphore-bounded scheduling, signal traps, subprocess execution, and atomic packet writing.
- `lib/opencode_worker.mjs`: Node.js worker helper managing ephemeral OpenCode SDK v2 instances on isolated TCP ports, extracting universal structured receipts.
- `schemas/worker-result.schema.json`: JSON Schema (Draft 2020-12) defining the structured output format for Agy workers.

---

## Process Safety & Reliability Guarantees

1. **Process-Group Isolation (`setsid`)**:
   Every worker process is spawned with `start_new_session=True` (POSIX `setsid`), placing the worker and any child processes it spawns (such as language servers or sub-commands) into an isolated process group where `pgid = pid`.

2. **Cascaded Process-Group Termination (`killpg`)**:
   When a worker exceeds `--timeout-seconds` or when the supervisor is cancelled, `terminate_process_group` sends `SIGTERM` to `os.killpg(process.pid)`. It allows up to a 3.0-second grace period for orderly cleanup before escalating to `SIGKILL` (`os.killpg(process.pid, signal.SIGKILL)`), ensuring zero orphaned background processes.

3. **Parent Signal Trapping (`SIGTERM`)**:
   The parent supervisor registers a `SIGTERM` signal handler on the running event loop. Receiving `SIGTERM` initiates a graceful cancellation of all active worker tasks, triggering the `terminate_process_group` cleanup cascade across all in-flight process groups before exiting.

4. **Atomic Packet Writing (`os.replace`)**:
   `packet.json` is first written to a temporary sibling file (`packet.json.tmp.<pid>`) with permissions `0600` and then moved into place using `os.replace`. This POSIX atomic rename prevents external readers from reading partial or corrupted JSON.

5. **Filesystem Permission Hardening**:
   The output directory and worker subdirectories are created with `0700` (`rwx------`) permissions. Log files (`stdout.json`, `stderr.log`, `agy.log`) and `packet.json` are strictly set to `0600` (`rw-------`).

6. **Bounded Resource Consumption**:
   An `asyncio.Semaphore` strictly caps concurrent worker processes. Subprocess output is capped at `--max-output-bytes` (default: 1MB) to prevent buffer overflows from runaway worker stdout/stderr.

7. **Deterministic Agy Retries**:
   Agy workers automatically execute one fresh retry attempt (`--agy-retries 1`) if the first attempt fails due to a `timeout` or `nonzero_exit`. Attempt artifacts are preserved under `attempt-1/` and `attempt-2/` so debugging evidence is never overwritten. Schema violations and oversized output are considered non-transient and are not retried.

---

## CLI Options Reference

```sh
tools/fanout/bin/fanout <prompt_file> \
  --output <output_dir> \
  [options]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `<prompt_file>` | Positional Path | *Required* | Path to the markdown or text prompt file. |
| `--output` | Path | *Required* | Destination directory for results and `packet.json` (must not exist or be empty). |
| `--harness` | `agy` \| `opencode` | `agy` | Worker harness to execute. |
| `--workers` | Integer (1..50) | `4` | Number of workers to spawn. |
| `--concurrency` | Integer (1..workers) | `min(4, workers)` | Max concurrent worker processes in flight. |
| `--min-results` | Integer (1..workers) | `workers` | Minimum required valid results for exit code 0 (K-of-N threshold). |
| `--timeout-seconds` | Float (> 1.0) | `300.0` | Per-attempt execution timeout in seconds. |
| `--model` | String | Harness default | Model route override (`gemini-3.7-flash-low` for Agy, `opencode-go/minimax-m3` for OpenCode). |
| `--agent` | String | `plan` | OpenCode agent profile (only with `--harness opencode`). |
| `--working-directory`| Path | Current directory | Working directory context for worker processes. |
| `--agy-retries` | `0` \| `1` | `1` | Max transient retries for Agy workers. |
| `--max-output-bytes` | Integer (>= 1024) | `1000000` | Max stdout/stderr capture buffer in bytes per attempt. |

---

## Exit Codes

| Exit Code | Classification | Condition | Description |
|---|---|---|---|
| `0` | **Success** | `valid_results >= min_results` | Quorum threshold met; structured results available in `packet.json`. |
| `1` | **Threshold Unmet** | `valid_results < min_results` | Execution completed, but insufficient workers passed schema validation. |
| `2` | **Error** | CLI / OS Validation Error | Missing arguments, nonexistent paths, non-empty output directory, or missing binaries. |

---

## Output Packet Contract (`packet.json` Schema v3)

The aggregated execution packet is written to `<output_dir>/packet.json`:

```json
{
  "schema_version": 3,
  "harness": "agy",
  "model": "gemini-3.7-flash-low",
  "agent": null,
  "prompt_path": "/Users/sws/Code/agent-toolkit/prompt.md",
  "prompt_sha256": "8f481a5c68ff0e32f416c19a9307d0663459c558b3f23a542b8e8f6e80b2ec4c",
  "requested_workers": 4,
  "concurrency": 4,
  "timeout_seconds": 90.0,
  "agy_retries": 1,
  "total_retries": 0,
  "min_results": 3,
  "valid_results": 4,
  "total_tokens": 142050,
  "total_cost_usd": 0.0152,
  "elapsed_seconds": 26.16,
  "workers": [
    {
      "worker_id": "worker-0001",
      "status": "ok",
      "attempt_count": 1,
      "attempts": [
        {
          "attempt": 1,
          "returncode": 0,
          "elapsed_seconds": 18.25,
          "stdout_path": "worker-0001/attempt-1/stdout.json",
          "stderr_path": "worker-0001/attempt-1/stderr.log",
          "log_path": "worker-0001/attempt-1/agy.log",
          "status": "ok",
          "result": {
            "worker_id": "worker-0001",
            "summary": "Verified process group cleanup logic",
            "findings": [
              "terminate_process_group correctly handles ProcessLookupError",
              "SIGTERM handler prevents orphaned child sessions"
            ],
            "uncertainties": []
          },
          "usage": {
            "total_tokens": 35500
          }
        }
      ],
      "result": {
        "worker_id": "worker-0001",
        "summary": "Verified process group cleanup logic",
        "findings": [
          "terminate_process_group correctly handles ProcessLookupError",
          "SIGTERM handler prevents orphaned child sessions"
        ],
        "uncertainties": []
      }
    }
  ]
}
```

### Worker Status Codes

- `ok`: Worker completed with schema-valid output (or OpenCode `outcome: "completed"`).
- `nonzero_exit`: Harness subprocess exited with non-zero exit code.
- `timeout`: Subprocess exceeded timeout and was terminated via process-group kill.
- `oversized_output`: Worker stdout or stderr exceeded `--max-output-bytes`.
- `malformed_output`: Output could not be decoded as JSON.
- `invalid_result`: JSON violated schema constraints, had missing/extra fields, or wrong `worker_id`.
- `blocked` / `failed`: OpenCode receipt returned explicit `blocked` or `failed` outcome.

---

## Result Schemas

### 1. Agy Structured Result (`schemas/worker-result.schema.json`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["worker_id", "summary", "findings", "uncertainties"],
  "additionalProperties": false,
  "properties": {
    "worker_id": { "type": "string" },
    "summary": { "type": "string", "minLength": 1, "maxLength": 2000 },
    "findings": {
      "type": "array",
      "maxItems": 10,
      "items": { "type": "string", "minLength": 1, "maxLength": 500 }
    },
    "uncertainties": {
      "type": "array",
      "maxItems": 10,
      "items": { "type": "string", "minLength": 1, "maxLength": 500 }
    }
  }
}
```

### 2. OpenCode Universal Receipt

```json
{
  "worker_id": "worker-0001",
  "outcome": "completed",
  "summary": "Completed search and identified 3 key call sites",
  "result_json": "{\"call_sites\": [\"src/main.rs:42\", \"src/lib.rs:18\"]}"
}
```

---

## Examples

### 1. Fast Agy Review with Quorum Threshold

```sh
tools/fanout/bin/fanout prompt.md \
  --harness agy \
  --workers 4 \
  --concurrency 4 \
  --min-results 3 \
  --timeout-seconds 90 \
  --output runs/agy-review-01
```

### 2. OpenCode Investigation with Custom Agent Profile

```sh
tools/fanout/bin/fanout prompt.md \
  --harness opencode \
  --agent plan \
  --workers 3 \
  --concurrency 3 \
  --min-results 2 \
  --timeout-seconds 120 \
  --output runs/opencode-plan-01
```
