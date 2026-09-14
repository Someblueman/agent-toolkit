"""Pi's native JSON event stream and ephemeral headless worker."""

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


def parse_pi_output(
    stdout: bytes, worker_id: str, direct_payload: bool = False
) -> tuple[dict[str, Any] | None, Any, str | None]:
    try:
        terminal = None
        for line in stdout.splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict):
                raise TypeError("Invalid Pi event")
            if event.get("type") == "agent_end":
                if event.get("willRetry") is True:
                    continue
                if terminal is not None:
                    raise ValueError("Multiple Pi terminal events")
                terminal = event
        if terminal is None:
            raise ValueError("Pi did not emit agent_end")
        messages = terminal.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("Pi terminal messages are missing")
        final = messages[-1]
        if not isinstance(final, dict) or final.get("role") != "assistant":
            raise ValueError("Pi did not finish with an assistant message")
        if final.get("stopReason") != "stop":
            raise ValueError(
                f"Pi did not complete: {final.get('errorMessage') or final.get('stopReason')}"
            )
        content = final.get("content")
        if not isinstance(content, list) or any(
            not isinstance(part, dict) for part in content
        ):
            raise TypeError("Invalid Pi message content")
        text = "".join(part["text"] for part in content if part.get("type") == "text")
        result, error = validate_receipt(json.loads(text), worker_id, direct_payload)
        usage = {"total_tokens": 0, "cost": 0.0}
        for message in messages:
            if isinstance(message, dict) and message.get("role") == "assistant":
                used = message.get("usage", {})
                usage["total_tokens"] += used.get("totalTokens", 0)
                usage["cost"] += used.get("cost", {}).get("total", 0)
        return result, usage, error
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        return None, None, str(error)


async def run_pi_worker(
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
    command = [executable_path, "--mode", "json", "--print", "--no-session"]
    if model is not None:
        command.extend(["--model", model])
    if effort is not None:
        command.extend(["--thinking", effort])
    command.extend(["--", f"@{prompt_path}"])
    return await run_structured_worker(
        worker_id=worker_id,
        command=command,
        parse_output=lambda stdout, worker: parse_pi_output(
            stdout, worker, payload_schema is not None
        ),
        semaphore=semaphore,
        working_directory=working_directory,
        output=output,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        stdout_name="stdout.jsonl",
    )
