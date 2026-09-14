"""Run Muse's native headless CLI and validate its root terminal receipt."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from structured_worker import (
    run_structured_worker,
    validate_receipt,
    write_worker_prompt,
)


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
    executable_path: str,
    model: str | None,
    base_prompt: str,
    working_directory: Path,
    output: Path,
    timeout_seconds: float,
    max_output_bytes: int,
) -> dict[str, Any]:
    worker_id = f"worker-{index:04d}"
    prompt_path = write_worker_prompt(output, worker_id, base_prompt)
    command = [
        executable_path,
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
