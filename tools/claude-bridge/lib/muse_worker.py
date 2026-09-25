"""Run one isolated Muse turn with bridge-owned conversation replay."""

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
    private_dir,
    read_json,
    read_status,
    turn_path,
    write_private,
    write_status,
)
from worker import finish, stop_group


def isolated_environment(current: Path) -> tuple[dict[str, str], Path]:
    environment = os.environ.copy()
    original_config = Path(
        environment.get("XDG_CONFIG_HOME", Path.home() / ".config")
    ).expanduser()
    auth = Path(
        environment.get("MUSE_AUTH_PATH", original_config / "muse/auth.json")
    ).expanduser()
    config = current / "muse-config"
    data = current / "muse-data"
    workspace = current / "muse-workspace"
    for directory in (config, config / "muse", data, workspace):
        private_dir(directory)
    link = config / "muse/auth.json"
    if auth.is_file() and not link.exists():
        link.symlink_to(auth.resolve())
    environment["XDG_CONFIG_HOME"] = str(config)
    environment["XDG_DATA_HOME"] = str(data)
    environment.pop("MUSE_HOME", None)
    return environment, workspace


def remove_auth_link(current: Path) -> None:
    link = current / "muse-config/muse/auth.json"
    if link.is_symlink():
        link.unlink(missing_ok=True)


def command(meta: dict[str, Any], prompt: Path) -> list[str]:
    args = [
        meta["muse"],
        "exec",
        "--json",
        "--no-session-log",
        "--no-foreign-personal-context",
        "--disable-shell",
        "--disable-write",
        "--disable-web-tools",
        "--reasoning-effort",
        meta["effort"],
        "--prompt-file",
        str(prompt),
    ]
    if meta["model"] is not None:
        args.extend(["--model", meta["model"]])
    return args


def decode_event(line: bytes) -> tuple[str | None, dict[str, Any]]:
    try:
        record = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Muse did not return valid JSONL") from error
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        raise ValueError("Muse returned an unsupported event envelope")
    payload = record.get("payload")
    if not isinstance(payload, dict):
        raise TypeError("Muse returned an invalid event payload")
    return record.get("payload_type"), payload


def accept_event(line: bytes, events: dict[str, Any], limit: int) -> None:
    kind, payload = decode_event(line)
    if (
        kind == "runtime.command.accepted"
        and payload.get("command_kind") == "turn.submit"
    ):
        if events["root_id"] is not None:
            raise ValueError("Muse accepted more than one root turn")
        root_id = payload.get("command_id")
        if not isinstance(root_id, str) or not root_id:
            raise ValueError("Muse root command id is missing")
        events["root_id"] = root_id
    elif isinstance(kind, str) and kind.startswith("run.terminal."):
        if events["root_id"] is None or payload.get("command_id") != events["root_id"]:
            return
        if events["terminal"] is not None:
            raise ValueError("Muse returned multiple root terminal events")
        if len(line) > limit:
            raise ValueError("Muse final result exceeded the configured limit")
        events["terminal"] = payload
        events["terminal_json"] = line.decode("utf-8")


def consume_stdout(
    output: bytearray, chunk: bytes, events: dict[str, Any], limit: int
) -> None:
    output.extend(chunk)
    while b"\n" in output:
        line, _, tail = output.partition(b"\n")
        output[:] = tail
        if line:
            accept_event(bytes(line), events, limit)
    if len(output) > max(limit * 16, 16_000_000):
        raise ValueError("Muse stream event exceeded the safety limit")


def collect(
    child: subprocess.Popen[bytes], timeout: float, limit: int
) -> tuple[dict[str, Any], str]:
    assert child.stdout is not None and child.stderr is not None
    streams = [child.stdout, child.stderr]
    output = bytearray()
    stderr = bytearray()
    events: dict[str, Any] = {"root_id": None, "terminal": None, "terminal_json": None}
    deadline = time.monotonic() + timeout if timeout else None
    while streams:
        remaining = deadline - time.monotonic() if deadline is not None else None
        if remaining is not None and remaining <= 0:
            raise TimeoutError(f"Muse exceeded {timeout:g}-second turn limit")
        ready, _, _ = select.select(streams, [], [], remaining)
        if not ready:
            raise TimeoutError(f"Muse exceeded {timeout:g}-second turn limit")
        for stream in ready:
            chunk = os.read(stream.fileno(), 65536)
            if not chunk:
                streams.remove(stream)
                continue
            if stream is child.stderr:
                stderr.extend(chunk)
                if len(stderr) > limit:
                    raise ValueError("Muse stderr exceeded the configured limit")
                continue
            consume_stdout(output, chunk, events, limit)
    child.wait()
    if output.strip():
        accept_event(bytes(output), events, limit)
    return events, stderr.decode("utf-8", errors="replace")


def record_completion(
    exchange: Path,
    turn: int,
    current: Path,
    child: subprocess.Popen[bytes],
    events: dict[str, Any],
    stderr: str,
) -> None:
    write_private(current / "stderr.log", stderr)
    terminal = events["terminal"]
    if terminal is None:
        raise ValueError(f"Muse exited without a root result (code {child.returncode})")
    write_private(current / "stdout.json", events["terminal_json"])
    if terminal.get("terminal") != "completed" or child.returncode != 0:
        raise ValueError(
            f"Muse did not complete: {terminal.get('reason') or child.returncode}"
        )
    answer = terminal.get("text")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("Muse returned an empty response")
    write_private(current / "response.txt", answer)
    finish(exchange, turn, "succeeded")


def run(root: Path, exchange_id: str, turn: int) -> None:
    exchange = exchange_path(root, exchange_id)
    current = turn_path(exchange, turn)
    descriptor = os.open(current / "worker.lock", os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX)
    child: subprocess.Popen[bytes] | None = None
    cancelled = [False]

    def on_term(_signum: int, _frame: Any) -> None:
        cancelled[0] = True
        if child is not None:
            stop_group(child)

    signal.signal(signal.SIGTERM, on_term)
    try:
        meta = read_json(exchange / "meta.json")
        with exchange_lock(exchange):
            status = read_status(exchange, turn)
            if status["state"] == "cancel_requested" or meta.get("closed_at"):
                status["state"] = "cancelled"
                status["finished_at"] = time.time()
                write_status(exchange, turn, status)
                return
            status["state"] = "running"
            status["started_at"] = time.time()
            write_status(exchange, turn, status)
        message = (current / "message.txt").read_text(encoding="utf-8")
        prompt = current / "prompt.txt"
        write_private(
            prompt,
            message if turn == 1 else build_prompt(exchange, message, peer="muse"),
        )
        if cancelled[0]:
            finish(exchange, turn, "cancelled")
            return
        environment, workspace = isolated_environment(current)
        child = subprocess.Popen(
            command(meta, prompt),
            cwd=workspace,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            start_new_session=True,
        )
        if cancelled[0]:
            stop_group(child)
        events, stderr = collect(
            child, status["timeout_seconds"], meta["max_output_bytes"]
        )
        if cancelled[0]:
            finish(exchange, turn, "cancelled")
            return
        record_completion(exchange, turn, current, child, events, stderr)
    except TimeoutError as error:
        finish(
            exchange,
            turn,
            "cancelled" if cancelled[0] else "timed_out",
            error=str(error),
        )
    except (OSError, ValueError, TypeError) as error:
        finish(
            exchange, turn, "cancelled" if cancelled[0] else "failed", error=str(error)
        )
    finally:
        if child is not None:
            stop_group(child)
        remove_auth_link(current)
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


if __name__ == "__main__":
    os.umask(0o077)
    run(Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]))
