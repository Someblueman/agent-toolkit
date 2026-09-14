"""Shared receipt validation and single-attempt worker process lifecycle."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import time
from collections.abc import Callable, Coroutine
from contextlib import nullcontext
from pathlib import Path
from typing import Any

RECEIPT_KEYS = {"worker_id", "outcome", "summary", "result_json"}
OUTCOMES = {"completed", "blocked", "failed"}


async def capture_worker_errors(
    worker_id: str, worker: Coroutine[Any, Any, dict[str, Any]]
) -> dict[str, Any]:
    """Preserve one worker's execution failure without discarding its siblings."""
    try:
        return await worker
    except (OSError, ValueError, TypeError) as error:
        attempt = {
            "attempt": 1,
            "status": "runner_error",
            "error": f"{type(error).__name__}: {error}",
        }
        return {
            "worker_id": worker_id,
            "status": "runner_error",
            "attempt_count": 1,
            "attempts": [attempt],
        }


def write_private(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    path.chmod(0o600)


def write_worker_prompt(
    output: Path, worker_id: str, base_prompt: str, payload_schema: dict | None = None
) -> Path:
    worker_dir = output / worker_id
    worker_dir.mkdir(mode=0o700, exist_ok=True)
    worker_dir.chmod(0o700)
    prompt_path = worker_dir / "prompt.txt"
    prompt = (
        base_prompt.strip()
        + "\n\nFan-out response contract: return only one JSON object, without Markdown "
        "fences, with exactly these fields: worker_id, outcome, summary, result_json. "
        f"Your worker_id is {worker_id}. outcome must be completed, blocked, or failed. "
        "summary must be a non-empty string of at most 2000 characters. result_json "
        "must be a JSON-encoded object containing your task-specific answer. "
        "Use your normal tools and permissions; report blocked if required tools "
        "or permissions are unavailable. result_json is a STRING, not a nested object. "
        "Use this exact outer shape, replacing the example answer:\n"
        + json.dumps(
            {
                "worker_id": worker_id,
                "outcome": "completed",
                "summary": "Completed the task",
                "result_json": json.dumps(
                    {"answer": "replace with task-specific fields"}
                ),
            }
        )
        + "\n"
    )
    if payload_schema is not None:
        prompt = base_prompt.strip() + (
            "\n\nFan-out response contract: return only one JSON object without Markdown fences. "
            f"Your worker_id is {worker_id}. Fields must be exactly worker_id, outcome, summary, payload. "
            "outcome is completed, blocked, or failed; summary is a nonempty string of at most 2000 characters. "
            "payload is a JSON OBJECT, not an encoded string. For completed use the supplied payload schema; "
            "for blocked/failed use {} and explain why in summary. Use normal permissions. "
            "Use this outer structure, filling in your task-specific evidence: "
            + json.dumps(
                {
                    "worker_id": worker_id,
                    "outcome": "completed",
                    "summary": "Completed task",
                    "payload": {k: [] for k in payload_schema["required"]},
                }
            )
            + "\n"
        )
    write_private(prompt_path, prompt.encode("utf-8"))
    return prompt_path


def validate_receipt(
    value: Any, worker_id: str, direct_payload: bool = False
) -> tuple[dict[str, Any] | None, str | None]:
    keys = (
        (RECEIPT_KEYS - {"result_json"}) | {"payload"}
        if direct_payload
        else RECEIPT_KEYS
    )
    if not isinstance(value, dict) or set(value) != keys:
        missing = keys - set(value) if isinstance(value, dict) else keys
        extra = set(value) - keys if isinstance(value, dict) else set()
        if missing or extra:
            return (
                None,
                f"structured_output has unexpected fields (missing: {sorted(missing)}, extra: {sorted(extra)})",
            )
        return None, "structured_output must be a JSON object"
    if value.get("worker_id") != worker_id:
        return (
            None,
            f"structured_output worker_id '{value.get('worker_id')}' does not match assigned worker '{worker_id}'",
        )
    if not isinstance(value.get("outcome"), str) or value["outcome"] not in OUTCOMES:
        return None, "outcome must be completed, blocked, or failed"

    summary = value.get("summary")
    if not isinstance(summary, str) or not 1 <= len(summary) <= 2000:
        return None, "summary must be a non-empty string of at most 2000 characters"
    if direct_payload:
        payload = value["payload"]
    else:
        result_json = value.get("result_json")
        if not isinstance(result_json, str):
            return None, "result_json must be a string"
        try:
            payload = json.loads(result_json)
        except json.JSONDecodeError:
            return None, "result_json must contain valid JSON"
    if not isinstance(payload, dict):
        return (
            None,
            "payload must be a JSON object"
            if direct_payload
            else "result_json must encode a JSON object",
        )

    return {
        "worker_id": worker_id,
        "outcome": value["outcome"],
        "summary": summary,
        "payload": payload,
    }, None


async def terminate_process_group(process: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        if process.returncode is None:
            await process.wait()
        return
    if process.returncode is None:
        try:
            await asyncio.wait_for(process.wait(), timeout=3.0)
        except TimeoutError:
            pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if process.returncode is None:
        await process.wait()


async def run_structured_worker(
    *,
    worker_id: str,
    command: list[str],
    parse_output: Callable[[bytes, str], tuple[dict[str, Any] | None, Any, str | None]],
    semaphore: asyncio.Semaphore,
    working_directory: Path,
    output: Path,
    timeout_seconds: float,
    max_output_bytes: int,
    environment: dict[str, str] | None = None,
    stdout_name: str = "stdout.json",
    stdin_path: Path | None = None,
) -> dict[str, Any]:
    worker_dir = output / worker_id
    worker_dir.mkdir(mode=0o700, exist_ok=True)
    worker_dir.chmod(0o700)
    stdout_path = worker_dir / stdout_name
    stderr_path = worker_dir / "stderr.log"
    started = time.monotonic()
    async with semaphore:
        with (
            stdin_path.open("rb")
            if stdin_path is not None
            else nullcontext(asyncio.subprocess.DEVNULL)
        ) as stdin:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=working_directory,
                stdin=stdin,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=environment,
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
            attempt = {
                "attempt": 1,
                "status": "timeout",
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "stdout_path": str(stdout_path.relative_to(output)),
                "stderr_path": str(stderr_path.relative_to(output)),
            }
            return {
                "worker_id": worker_id,
                "status": "timeout",
                "attempt_count": 1,
                "attempts": [attempt],
            }
        except asyncio.CancelledError:
            await terminate_process_group(process)
            await communicate
            raise

    write_private(stdout_path, stdout)
    write_private(stderr_path, stderr)
    attempt = {
        "attempt": 1,
        "returncode": process.returncode,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "stdout_path": str(stdout_path.relative_to(output)),
        "stderr_path": str(stderr_path.relative_to(output)),
    }
    if process.returncode != 0:
        attempt["status"] = "nonzero_exit"
    elif len(stdout) > max_output_bytes or len(stderr) > max_output_bytes:
        attempt["status"] = "oversized_output"
    else:
        result, usage, error = parse_output(stdout, worker_id)
        if error is not None:
            attempt["status"] = "invalid_result"
            attempt["error"] = error
        else:
            attempt["status"] = (
                "ok" if result["outcome"] == "completed" else result["outcome"]
            )
            attempt["result"] = result
            attempt["usage"] = usage

    worker = {
        "worker_id": worker_id,
        "status": attempt["status"],
        "attempt_count": 1,
        "attempts": [attempt],
    }
    if "result" in attempt:
        worker["result"] = attempt["result"]
    return worker


def extract_tokens(usage: Any) -> int | None:
    if not isinstance(usage, dict):
        return None
    if "total_tokens" in usage and isinstance(usage["total_tokens"], (int, float)):
        return int(usage["total_tokens"])
    if "tokens" in usage:
        t = usage["tokens"]
        if isinstance(t, (int, float)):
            return int(t)
        if (
            isinstance(t, dict)
            and "total" in t
            and isinstance(t["total"], (int, float))
        ):
            return int(t["total"])
    return None


def extract_cost(usage: Any) -> float | None:
    if not isinstance(usage, dict):
        return None
    if "cost" in usage and isinstance(usage["cost"], (int, float)):
        return float(usage["cost"])
    if "total_cost_usd" in usage and isinstance(usage["total_cost_usd"], (int, float)):
        return float(usage["total_cost_usd"])
    return None


def receipt_schema(worker_id, payload_schema=None):
    key = "payload" if payload_schema is not None else "result_json"
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["worker_id", "outcome", "summary", key],
        "properties": {
            "worker_id": {"type": "string", "const": worker_id},
            "outcome": {"type": "string", "enum": ["completed", "blocked", "failed"]},
            "summary": {"type": "string", "minLength": 1, "maxLength": 2000},
            key: {"anyOf": [payload_schema, {"type": "object", "maxProperties": 0}]}
            if payload_schema is not None
            else {"type": "string"},
        },
    }
