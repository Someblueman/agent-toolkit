"""Shared receipt validation and single-attempt worker process lifecycle."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

RECEIPT_KEYS = {"worker_id", "outcome", "summary", "result_json"}
OUTCOMES = {"completed", "blocked", "failed"}


def write_private(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    path.chmod(0o600)


def validate_receipt(
    value: Any, worker_id: str
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(value, dict) or set(value) != RECEIPT_KEYS:
        missing = RECEIPT_KEYS - set(value) if isinstance(value, dict) else RECEIPT_KEYS
        extra = set(value) - RECEIPT_KEYS if isinstance(value, dict) else set()
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
    if value.get("outcome") not in OUTCOMES:
        return None, "outcome must be completed, blocked, or failed"

    summary = value.get("summary")
    if not isinstance(summary, str) or not 1 <= len(summary) <= 2000:
        return None, "summary must be a non-empty string of at most 2000 characters"
    result_json = value.get("result_json")
    if not isinstance(result_json, str):
        return None, "result_json must be a string"
    try:
        payload = json.loads(result_json)
    except json.JSONDecodeError:
        return None, "result_json must contain valid JSON"
    if not isinstance(payload, dict):
        return None, "result_json must encode a JSON object"

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
) -> dict[str, Any]:
    worker_dir = output / worker_id
    worker_dir.mkdir(mode=0o700, exist_ok=True)
    worker_dir.chmod(0o700)
    stdout_path = worker_dir / stdout_name
    stderr_path = worker_dir / "stderr.log"
    started = time.monotonic()
    async with semaphore:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=working_directory,
            stdin=asyncio.subprocess.DEVNULL,
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
