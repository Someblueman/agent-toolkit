"""Native harness dispatch, validation, and executable discovery."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import time
from pathlib import Path
from typing import Any

from claude_worker import run_claude_worker
from muse_worker import run_muse_worker
from pi_worker import run_pi_worker
from structured_worker import (
    receipt_schema,
    run_structured_worker,
    terminate_process_group,
    validate_receipt,
    write_private,
    write_worker_prompt,
)

TOOL_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = TOOL_ROOT / "schemas" / "worker-result.schema.json"
OPENCODE_HELPER_PATH = TOOL_ROOT / "lib" / "opencode_worker.mjs"
AGY_RESULT_KEYS = {"worker_id", "summary", "findings", "uncertainties"}


def resolve_executable(name: str, label: str) -> str:
    executable_path = shutil.which(name)
    if executable_path is not None:
        return executable_path
    candidate = Path(name).expanduser().resolve()
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    raise ValueError(f"{label} executable not found: {name}")


def resolve_opencode_sdk(explicit_path: Path | None) -> Path:
    if explicit_path is not None:
        candidates = [explicit_path.expanduser().resolve()]
    else:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        candidates = [
            config_home
            / "opencode"
            / "node_modules"
            / "@opencode-ai"
            / "sdk"
            / "dist"
            / "v2"
            / "index.js"
        ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ValueError(
        "OpenCode SDK v2 not found; install @opencode-ai/sdk in the OpenCode config directory"
    )


def validate_agy_result(value: Any, worker_id: str) -> str | None:
    if not isinstance(value, dict) or set(value) != AGY_RESULT_KEYS:
        missing = (
            AGY_RESULT_KEYS - set(value) if isinstance(value, dict) else AGY_RESULT_KEYS
        )
        extra = set(value) - AGY_RESULT_KEYS if isinstance(value, dict) else set()
        if missing or extra:
            return f"structured_output has unexpected fields (missing: {sorted(missing)}, extra: {sorted(extra)})"
        return "structured_output must be a JSON object"
    if value.get("worker_id") != worker_id:
        return f"structured_output worker_id '{value.get('worker_id')}' does not match assigned worker '{worker_id}'"

    summary = value.get("summary")
    if not isinstance(summary, str) or not 1 <= len(summary) <= 2000:
        return "summary must be a non-empty string of at most 2000 characters"

    for field in ("findings", "uncertainties"):
        items = value.get(field)
        if not isinstance(items, list) or len(items) > 10:
            return f"{field} must be an array of at most 10 strings"
        if any(
            not isinstance(item, str) or not 1 <= len(item) <= 500 for item in items
        ):
            return (
                f"{field} entries must be non-empty strings of at most 500 characters"
            )
    return None


def available_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


async def run_agy_attempt(
    *,
    worker_id: str,
    attempt: int,
    semaphore: asyncio.Semaphore,
    agy_path: str,
    model: str,
    base_prompt: str,
    working_directory: Path,
    output: Path,
    timeout_seconds: float,
    max_output_bytes: int,
    payload_schema: dict | None = None,
    effort: str | None = None,
) -> dict[str, Any]:
    worker_dir = output / worker_id
    worker_dir.mkdir(mode=0o700, exist_ok=True)
    worker_dir.chmod(0o700)
    attempt_dir = worker_dir / f"attempt-{attempt}"
    attempt_dir.mkdir(mode=0o700, exist_ok=True)
    attempt_dir.chmod(0o700)
    stdout_path = attempt_dir / "stdout.json"
    stderr_path = attempt_dir / "stderr.log"
    log_path = attempt_dir / "agy.log"
    prompt = (
        f"{base_prompt.rstrip()}\n\n"
        "Fan-out response contract: return only the requested structured result. "
        f"Your assigned worker_id is {worker_id}. Keep the summary concise; "
        "put bounded conclusions in findings and material unknowns in uncertainties."
    )
    if payload_schema is not None:
        prompt = write_worker_prompt(
            output, worker_id, base_prompt, payload_schema
        ).read_text()
    workflow_schema = (
        worker_dir / "receipt.schema.json" if payload_schema is not None else None
    )
    if workflow_schema:
        write_private(
            workflow_schema,
            json.dumps(receipt_schema(worker_id, payload_schema)).encode(),
        )
    agy_timeout = max(1, int(timeout_seconds) - 1)
    command = [
        agy_path,
        "--model",
        model,
        "--mode",
        "plan",
        "--sandbox",
        "--output-format",
        "json",
        "--json-schema",
        str(workflow_schema or SCHEMA_PATH),
        "--print-timeout",
        f"{agy_timeout}s",
        "--log-file",
        str(log_path),
        f"--print={prompt}",
    ]

    if effort is not None:
        command.extend(["--effort", effort])
    started = time.monotonic()
    async with semaphore:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=working_directory,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        communicate = asyncio.create_task(process.communicate())
        try:
            stdout, stderr = await asyncio.wait_for(
                asyncio.shield(communicate), timeout=timeout_seconds
            )
        except TimeoutError:
            await terminate_process_group(process)
            stdout, stderr = await communicate
            write_private(stdout_path, stdout)
            write_private(stderr_path, stderr)
            if log_path.exists():
                log_path.chmod(0o600)
            return {
                "attempt": attempt,
                "status": "timeout",
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "stdout_path": str(stdout_path.relative_to(output)),
                "stderr_path": str(stderr_path.relative_to(output)),
                "log_path": str(log_path.relative_to(output)),
            }
        except asyncio.CancelledError:
            await terminate_process_group(process)
            await communicate
            raise

    write_private(stdout_path, stdout)
    write_private(stderr_path, stderr)
    if log_path.exists():
        log_path.chmod(0o600)
    record: dict[str, Any] = {
        "attempt": attempt,
        "returncode": process.returncode,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "stdout_path": str(stdout_path.relative_to(output)),
        "stderr_path": str(stderr_path.relative_to(output)),
        "log_path": str(log_path.relative_to(output)),
    }
    if process.returncode != 0:
        record["status"] = "nonzero_exit"
        return record
    if len(stdout) > max_output_bytes or len(stderr) > max_output_bytes:
        record["status"] = "oversized_output"
        return record

    try:
        envelope = json.loads(stdout)
    except (UnicodeDecodeError, json.JSONDecodeError):
        record["status"] = "malformed_output"
        return record
    if not isinstance(envelope, dict) or envelope.get("status") != "SUCCESS":
        record["status"] = "invalid_result"
        return record

    result = envelope.get("structured_output")
    if payload_schema is not None:
        result, error = validate_receipt(result, worker_id, True)
    else:
        error = validate_agy_result(result, worker_id)
    if error is not None:
        record["status"] = "invalid_result"
        record["error"] = error
        return record

    record.update(
        {
            "status": "ok"
            if payload_schema is None or result["outcome"] == "completed"
            else result["outcome"],
            "result": result,
            "agy_duration_seconds": envelope.get("duration_seconds"),
            "agy_num_turns": envelope.get("num_turns"),
            "usage": envelope.get("usage"),
        }
    )
    return record


async def run_agy_worker(
    *,
    index: int,
    semaphore: asyncio.Semaphore,
    agy_path: str,
    model: str,
    base_prompt: str,
    working_directory: Path,
    output: Path,
    timeout_seconds: float,
    max_output_bytes: int,
    retries: int,
    payload_schema: dict | None = None,
    effort: str | None = None,
) -> dict[str, Any]:
    worker_id = f"worker-{index:04d}"
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, retries + 2):
        record = await run_agy_attempt(
            worker_id=worker_id,
            attempt=attempt,
            semaphore=semaphore,
            agy_path=agy_path,
            model=model,
            base_prompt=base_prompt,
            working_directory=working_directory,
            output=output,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            payload_schema=payload_schema,
            effort=effort,
        )
        attempts.append(record)
        if record["status"] not in {"timeout", "nonzero_exit"}:
            break

    final = attempts[-1]
    return {
        "worker_id": worker_id,
        "status": final["status"],
        "attempt_count": len(attempts),
        "attempts": attempts,
        **({"result": final["result"]} if "result" in final else {}),
    }


def parse_opencode_output(
    stdout: bytes, worker_id: str, direct_payload: bool = False
) -> tuple[dict[str, Any] | None, Any, str | None]:
    try:
        envelope = json.loads(stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, None, str(error)
    if not isinstance(envelope, dict) or envelope.get("status") != "SUCCESS":
        detail = envelope.get("error") if isinstance(envelope, dict) else None
        if detail is None:
            return None, None, "OpenCode helper did not return a successful envelope"
        return None, None, f"OpenCode structured output failed: {json.dumps(detail)}"
    result, validation_error = validate_receipt(
        envelope.get("structured_output"), worker_id, direct_payload
    )
    if validation_error is not None:
        return None, None, validation_error
    return result, envelope.get("usage"), None


async def run_opencode_worker(
    *,
    index: int,
    semaphore: asyncio.Semaphore,
    opencode_path: str,
    node_path: str,
    sdk_path: Path,
    model: str,
    agent: str,
    base_prompt: str,
    working_directory: Path,
    output: Path,
    timeout_seconds: float,
    max_output_bytes: int,
    payload_schema: dict | None = None,
) -> dict[str, Any]:
    worker_id = f"worker-{index:04d}"
    command = [
        node_path,
        str(OPENCODE_HELPER_PATH),
        "--sdk",
        str(sdk_path),
        "--directory",
        str(working_directory),
        "--port",
        str(available_tcp_port()),
        "--model",
        model,
        "--agent",
        agent,
        "--worker-id",
        worker_id,
        "--prompt",
        base_prompt,
    ]
    if payload_schema is not None:
        command.extend(["--receipt-key", "payload"])
        prompt_path = write_worker_prompt(
            output, worker_id, base_prompt, payload_schema
        )
        command[command.index("--prompt") + 1] = prompt_path.read_text()
    environment = os.environ.copy()
    environment["OPENCODE_DB"] = str(output / worker_id / "opencode.db")
    environment["OPENCODE_GOAL_STATE_PATH"] = str(
        output / worker_id / "goal-state.json"
    )
    opencode_directory = str(Path(opencode_path).resolve().parent)
    environment["PATH"] = opencode_directory + os.pathsep + environment.get("PATH", "")
    return await run_structured_worker(
        worker_id=worker_id,
        command=command,
        parse_output=lambda stdout, worker: parse_opencode_output(
            stdout, worker, payload_schema is not None
        ),
        semaphore=semaphore,
        working_directory=working_directory,
        output=output,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        environment=environment,
    )


def resolve_dependencies(args, members):
    dependencies = {}
    for harness in sorted({m["harness"] for m in members}):
        executable = resolve_executable(getattr(args, harness), harness)
        dependencies[harness] = (
            executable,
            resolve_executable(args.node, "node") if harness == "opencode" else None,
            resolve_opencode_sdk(args.opencode_sdk) if harness == "opencode" else None,
        )
    return dependencies


async def dispatch_worker(
    member, common, dependencies, *, retries=0, payload_schema=None
):
    harness = member["harness"]
    executable, node, sdk = dependencies[harness]
    settings = member.get("settings", {})
    if harness == "agy":
        return await run_agy_worker(
            **common,
            agy_path=executable,
            model=member["model"],
            retries=retries,
            payload_schema=payload_schema,
            effort=settings.get("effort"),
        )
    if harness == "opencode":
        return await run_opencode_worker(
            **common,
            opencode_path=executable,
            node_path=node,
            sdk_path=sdk,
            model=member["model"],
            agent=settings.get("agent", "plan"),
            payload_schema=payload_schema,
        )
    runner = {
        "muse": run_muse_worker,
        "pi": run_pi_worker,
        "claude": run_claude_worker,
    }[harness]
    options = {"effort": settings.get("effort")} if harness in {"pi", "claude"} else {}
    return await runner(
        **common,
        executable_path=executable,
        model=member["model"],
        payload_schema=payload_schema,
        **options,
    )
