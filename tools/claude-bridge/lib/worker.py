"""Detached, single-turn Claude process with bounded execution."""

from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from state import (
    exchange_lock,
    exchange_path,
    read_json,
    read_status,
    turn_path,
    write_private,
    write_status,
)

SYSTEM_PROMPT = (
    "You are an independent technical collaborator responding to Codex. "
    "Assess only the supplied exchange and evidence. Challenge unsupported claims, "
    "state uncertainty plainly, and suggest decisive checks when useful. "
    "Do not claim to have inspected files or run commands."
)


def command(meta: dict[str, Any]) -> list[str]:
    return [
        meta["claude"],
        "--restricted",
        "--safe-mode",
        "--print",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--tools",
        "",
        "--disallowedTools",
        "mcp__*",
        "--model",
        meta["model"],
        "--effort",
        meta["effort"],
        "--max-turns",
        "1",
        "--system-prompt",
        SYSTEM_PROMPT,
    ]


def parse_result(output: bytes) -> tuple[str, list[str], float | None]:
    try:
        envelope = json.loads(output)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Claude did not return a JSON result") from error
    if not isinstance(envelope, dict) or envelope.get("type") != "result":
        raise ValueError("Claude did not return a result envelope")
    if envelope.get("subtype") != "success" or envelope.get("is_error") is not False:
        raise ValueError(f"Claude did not complete: {envelope.get('subtype')}")
    answer = envelope.get("result")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("Claude returned an empty response")
    usage = envelope.get("modelUsage")
    models = sorted(usage) if isinstance(usage, dict) else []
    cost = envelope.get("total_cost_usd")
    return answer, models, cost if isinstance(cost, (int, float)) else None


def stop_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def finish(exchange: Path, turn: int, state: str, **fields: Any) -> None:
    with exchange_lock(exchange):
        status = read_status(exchange, turn)
        status.update(fields)
        status["state"] = state
        status["finished_at"] = time.time()
        write_status(exchange, turn, status)


def record_completion(
    exchange: Path,
    turn: int,
    current: Path,
    meta: dict[str, Any],
    child: subprocess.Popen[bytes],
    stdout: bytes,
    stderr: bytes,
    cancelled: bool,
) -> None:
    write_private(current / "stdout.json", stdout.decode("utf-8", errors="replace"))
    write_private(current / "stderr.log", stderr.decode("utf-8", errors="replace"))
    if cancelled:
        finish(exchange, turn, "cancelled")
    elif (
        len(stdout) > meta["max_output_bytes"] or len(stderr) > meta["max_output_bytes"]
    ):
        finish(
            exchange,
            turn,
            "failed",
            error="Claude output exceeded the configured limit",
        )
    elif child.returncode != 0:
        finish(
            exchange,
            turn,
            "failed",
            error=f"Claude exited with code {child.returncode}",
        )
    else:
        answer, models, cost = parse_result(stdout)
        write_private(current / "response.txt", answer)
        finish(exchange, turn, "succeeded", observed_models=models, cost_usd=cost)


def run(root: Path, exchange_id: str, turn: int) -> None:
    exchange = exchange_path(root, exchange_id)
    current = turn_path(exchange, turn)
    descriptor = os.open(current / "worker.lock", os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX)
    child: subprocess.Popen[bytes] | None = None
    cancelled = False

    def on_term(_signum: int, _frame: Any) -> None:
        nonlocal cancelled
        cancelled = True
        if child is not None:
            stop_group(child)

    signal.signal(signal.SIGTERM, on_term)
    try:
        meta = read_json(exchange / "meta.json")
        with exchange_lock(exchange):
            status = read_status(exchange, turn)
            if status["state"] == "cancel_requested" or cancelled:
                status["state"] = "cancelled"
                status["finished_at"] = time.time()
                write_status(exchange, turn, status)
                return
            status["state"] = "running"
            status["started_at"] = time.time()
            write_status(exchange, turn, status)
        environment = os.environ.copy()
        environment.pop("CLAUDE_CODE_DISABLE_THINKING", None)
        environment.pop("CLAUDE_CODE_DISABLE_1M_CONTEXT", None)
        environment.pop("MAX_THINKING_TOKENS", None)
        environment["CLAUDE_CODE_EFFORT_LEVEL"] = meta["effort"]
        environment["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
        environment["CLAUDE_CODE_SKIP_PROMPT_HISTORY"] = "1"
        child = subprocess.Popen(
            command(meta),
            cwd=meta["working_directory"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            start_new_session=True,
        )
        if cancelled:
            stop_group(child)
        prompt = (current / "prompt.txt").read_bytes()
        try:
            stdout, stderr = child.communicate(prompt, timeout=meta["timeout_seconds"])
        except subprocess.TimeoutExpired:
            stop_group(child)
            stdout, stderr = child.communicate()
            write_private(
                current / "stdout.json", stdout.decode("utf-8", errors="replace")
            )
            write_private(
                current / "stderr.log", stderr.decode("utf-8", errors="replace")
            )
            finish(exchange, turn, "cancelled" if cancelled else "timed_out")
            return
        record_completion(
            exchange, turn, current, meta, child, stdout, stderr, cancelled
        )
    except (OSError, ValueError, TypeError) as error:
        finish(exchange, turn, "cancelled" if cancelled else "failed", error=str(error))
    finally:
        if child is not None:
            stop_group(child)
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


if __name__ == "__main__":
    os.umask(0o077)
    run(Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]))
