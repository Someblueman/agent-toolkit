"""Claude Code's native structured result and ephemeral print-mode worker."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from structured_worker import (
    receipt_schema,
    run_structured_worker,
    validate_receipt,
    write_worker_prompt,
)


def parse_claude_output(
    stdout: bytes, worker_id: str, direct_payload: bool = False
) -> tuple[dict[str, Any] | None, Any, str | None]:
    try:
        envelope = json.loads(stdout)
        if not isinstance(envelope, dict) or envelope.get("type") != "result":
            raise ValueError("Claude Code did not emit a result envelope")
        if (
            envelope.get("subtype") != "success"
            or envelope.get("is_error") is not False
        ):
            raise ValueError(
                f"Claude Code did not complete: {envelope.get('errors') or envelope.get('subtype')}"
            )
        result, error = validate_receipt(
            envelope.get("structured_output"), worker_id, direct_payload
        )
        native_usage = envelope.get("usage")
        usage = {"total_cost_usd": envelope.get("total_cost_usd")}
        if isinstance(native_usage, dict):
            tokens = [
                native_usage.get(key, 0)
                for key in (
                    "input_tokens",
                    "output_tokens",
                    "cache_creation_input_tokens",
                    "cache_read_input_tokens",
                )
            ]
            if all(type(value) is int and value >= 0 for value in tokens):
                usage["total_tokens"] = sum(tokens)
        return result, usage, error
    except (ValueError, TypeError) as error:
        return None, None, str(error)


async def run_claude_worker(
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
    payload_schema: dict | None = None,
    effort: str | None = None,
) -> dict[str, Any]:
    worker_id = f"worker-{index:04d}"
    prompt_path = write_worker_prompt(output, worker_id, base_prompt, payload_schema)
    schema = receipt_schema(worker_id, payload_schema)
    command = [
        executable_path,
        "--print",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--json-schema",
        json.dumps(schema),
    ]
    if model is not None:
        command.extend(["--model", model])
    environment = None
    if effort is not None:
        environment = {**os.environ, "CLAUDE_CODE_EFFORT_LEVEL": effort}
    return await run_structured_worker(
        worker_id=worker_id,
        command=command,
        parse_output=lambda stdout, worker: parse_claude_output(
            stdout, worker, payload_schema is not None
        ),
        semaphore=semaphore,
        working_directory=working_directory,
        output=output,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        stdin_path=prompt_path,
        environment=environment,
    )
