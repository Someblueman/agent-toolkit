"""Keep one isolated Claude process alive across exchange turns."""

from __future__ import annotations

import fcntl
import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from state import (
    build_prompt,
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
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
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


def pop_result(remainder: bytearray, limit: int) -> bytes | None:
    while b"\n" in remainder:
        line, _, tail = remainder.partition(b"\n")
        remainder[:] = tail
        if not line:
            continue
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Claude did not return valid stream JSON") from error
        if isinstance(event, dict) and event.get("type") == "result":
            if len(line) > limit:
                raise ValueError("Claude output exceeded the configured limit")
            return bytes(line)
    return None


def result_line(
    child: subprocess.Popen[bytes], remainder: bytearray, timeout: float, limit: int
) -> bytes:
    deadline = time.monotonic() + timeout if timeout else None
    stream_event_limit = max(limit * 16, 16_000_000)
    while True:
        result = pop_result(remainder, limit)
        if result is not None:
            return result
        if len(remainder) > stream_event_limit:
            raise ValueError("Claude stream event exceeded the safety limit")
        remaining = deadline - time.monotonic() if deadline is not None else None
        if remaining is not None and remaining <= 0:
            raise TimeoutError(f"Claude exceeded {timeout:g}-second turn limit")
        assert child.stdout is not None
        readable, _, _ = select.select([child.stdout], [], [], remaining)
        if not readable:
            raise TimeoutError(f"Claude exceeded {timeout:g}-second turn limit")
        chunk = os.read(child.stdout.fileno(), 65536)
        if not chunk:
            raise ValueError(f"Claude exited before a result (code {child.wait()})")
        remainder.extend(chunk)


def run_turn(
    exchange: Path,
    turn: int,
    meta: dict[str, Any],
    child: subprocess.Popen[bytes],
    remainder: bytearray,
    first_turn: bool,
    cancelled: list[bool],
) -> bool:
    current = turn_path(exchange, turn)
    descriptor = os.open(current / "worker.lock", os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX)
    try:
        with exchange_lock(exchange):
            status = read_status(exchange, turn)
            if status["state"] == "cancel_requested" or cancelled[0]:
                should_cancel = True
            else:
                should_cancel = False
                status["state"] = "running"
                status["started_at"] = time.time()
                write_status(exchange, turn, status)
        if should_cancel:
            finish(exchange, turn, "cancelled")
            return False
        message = (current / "message.txt").read_text(encoding="utf-8")
        prompt = build_prompt(exchange, message) if first_turn else message
        request = {"type": "user", "message": {"role": "user", "content": prompt}}
        try:
            assert child.stdin is not None
            child.stdin.write((json.dumps(request, ensure_ascii=False) + "\n").encode())
            child.stdin.flush()
            output = result_line(
                child, remainder, status["timeout_seconds"], meta["max_output_bytes"]
            )
            write_private(current / "stdout.json", output.decode("utf-8"))
            answer, models, cost = parse_result(output)
            if cancelled[0]:
                finish(exchange, turn, "cancelled")
                return False
            write_private(current / "response.txt", answer)
            finish(exchange, turn, "succeeded", observed_models=models, cost_usd=cost)
            return True
        except TimeoutError as error:
            finish(
                exchange,
                turn,
                "cancelled" if cancelled[0] else "timed_out",
                error=str(error),
            )
        except (OSError, ValueError, TypeError) as error:
            finish(
                exchange,
                turn,
                "cancelled" if cancelled[0] else "failed",
                error=str(error),
            )
        return False
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def claude_environment(meta: dict[str, Any]) -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "CLAUDE_CODE_DISABLE_THINKING",
        "CLAUDE_CODE_DISABLE_1M_CONTEXT",
        "MAX_THINKING_TOKENS",
    ):
        environment.pop(name, None)
    environment["CLAUDE_CODE_EFFORT_LEVEL"] = meta["effort"]
    environment["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    environment["CLAUDE_CODE_SKIP_PROMPT_HISTORY"] = "1"
    return environment


def serve(
    exchange: Path,
    first_turn: int,
    meta: dict[str, Any],
    child: subprocess.Popen[bytes],
    cancelled: list[bool],
    active_turn: list[int],
) -> None:
    remainder = bytearray()
    turn = first_turn
    while not cancelled[0]:
        active_turn[0] = turn
        with exchange_lock(exchange):
            current_meta = read_json(exchange / "meta.json")
            current = turn_path(exchange, turn)
            queued = (
                current.exists() and read_status(exchange, turn)["state"] == "queued"
            )
        if current_meta.get("closed_at"):
            break
        if not queued:
            if child.poll() is not None:
                break
            time.sleep(0.2)
            continue
        if not run_turn(
            exchange, turn, meta, child, remainder, turn == first_turn, cancelled
        ):
            break
        turn += 1


def mark_abandoned(exchange: Path, turn: int, cancelled: bool, error: str) -> None:
    current = turn_path(exchange, turn)
    if not current.exists():
        return
    with exchange_lock(exchange):
        status = read_status(exchange, turn)
        if status["state"] in {"queued", "running", "cancel_requested"}:
            status["state"] = (
                "cancelled"
                if cancelled or status["state"] == "cancel_requested"
                else "failed"
            )
            status["error"] = error
            status["finished_at"] = time.time()
            write_status(exchange, turn, status)


def run(root: Path, exchange_id: str, first_turn: int) -> None:
    exchange = exchange_path(root, exchange_id)
    descriptor = os.open(exchange / "daemon.lock", os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX)
    child: subprocess.Popen[bytes] | None = None
    cancelled = [False]
    active_turn = [first_turn]

    def on_term(_signum: int, _frame: Any) -> None:
        cancelled[0] = True
        if child is not None:
            stop_group(child)

    signal.signal(signal.SIGTERM, on_term)
    try:
        meta = read_json(exchange / "meta.json")
        with (exchange / "claude.stderr.log").open("ab") as stderr:
            child = subprocess.Popen(
                command(meta),
                cwd=meta["working_directory"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr,
                env=claude_environment(meta),
                start_new_session=True,
            )
            serve(exchange, first_turn, meta, child, cancelled, active_turn)
    except (OSError, ValueError, TypeError) as error:
        mark_abandoned(exchange, active_turn[0], cancelled[0], str(error))
    finally:
        if child is not None:
            stop_group(child)
        mark_abandoned(
            exchange,
            active_turn[0],
            cancelled[0],
            "worker exited before recording a result",
        )
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


if __name__ == "__main__":
    os.umask(0o077)
    run(Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]))
