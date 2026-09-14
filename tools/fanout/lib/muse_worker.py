"""Run Muse's native headless CLI and validate its root terminal receipt."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from structured_worker import run_structured_worker, validate_receipt, write_private


def parse_muse_output(
    stdout: bytes, worker_id: str
) -> tuple[dict[str, Any] | None, Any, str | None]:
    try:
        records = [json.loads(line) for line in stdout.splitlines() if line.strip()]
        root_id = None
        terminal = None
        for record in records:
            if not isinstance(record, dict) or record.get("schema_version") != 1:
                raise ValueError("Unsupported Muse event envelope")
            payload = record.get("payload")
            if not isinstance(payload, dict):
                raise TypeError("Invalid Muse event payload")
            if (
                record.get("payload_type") == "runtime.command.accepted"
                and payload.get("command_kind") == "turn.submit"
            ):
                if root_id is not None:
                    raise ValueError("Multiple Muse root commands")
                root_id = payload.get("command_id")
                if not isinstance(root_id, str) or not root_id:
                    raise ValueError("Missing Muse command id")
            if str(record.get("payload_type", "")).startswith("run.terminal."):
                if root_id is None or payload.get("command_id") != root_id:
                    continue
                if terminal is not None:
                    raise ValueError("Multiple Muse root terminal events")
                terminal = payload
        if terminal is None:
            raise ValueError("Muse did not emit a root terminal event")
        if terminal.get("terminal") != "completed":
            raise ValueError(f"Muse run did not complete: {terminal.get('reason')}")
        text = terminal.get("text")
        if not isinstance(text, str):
            raise TypeError("Muse terminal text is missing")
        result, error = validate_receipt(json.loads(text), worker_id)
        return result, None, error
    except (UnicodeDecodeError, ValueError, TypeError) as error:
        return None, None, str(error)


async def run_muse_worker(
    *,
    index: int,
    semaphore: asyncio.Semaphore,
    muse_path: str,
    model: str | None,
    base_prompt: str,
    working_directory: Path,
    output: Path,
    timeout_seconds: float,
    max_output_bytes: int,
) -> dict[str, Any]:
    worker_id = f"worker-{index:04d}"
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
        "or permissions are unavailable.\n"
    )
    write_private(prompt_path, prompt.encode("utf-8"))
    command = [
        muse_path,
        "exec",
        "--json",
        "--no-session-log",
        "--workspace",
        str(working_directory),
        "--prompt-file",
        str(prompt_path),
    ]
    if model is not None:
        command.extend(["--model", model])
    return await run_structured_worker(
        worker_id=worker_id,
        command=command,
        parse_output=parse_muse_output,
        semaphore=semaphore,
        working_directory=working_directory,
        output=output,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        stdout_name="stdout.jsonl",
    )
