"""Native runner setup and process execution for skill evaluations."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_RUNNERS = ("codex", "omp")


@dataclass(slots=True, frozen=True)
class PreparedRunner:
    env: dict[str, str]
    env_contract: dict[str, str]
    skill_path: Path
    command_args: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class RuntimeObservation:
    actual_model: str | None
    observed_models: tuple[str, ...]
    fallback_applied: bool
    identity_ok: bool
    provider_error: str | None
    input_tokens: int | None
    output_tokens: int | None
    cached_input_tokens: int | None
    total_tokens: int | None
    cost_usd: float | None
    task_started: bool


@dataclass(slots=True, frozen=True)
class RunnerResult:
    started: bool
    exit_code: int | None
    budget_exhausted: bool
    duration_s: float
    stdout: str
    stderr: str


def _copy_file(source: Path, target: Path) -> None:
    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _prepare_codex(
    base: Path,
    arm: str,
    skill_dir: Path,
    skill_name: str,
    user_home: Path,
) -> PreparedRunner:
    home = base / "codex-home"
    home.mkdir(parents=True)
    _copy_file(user_home / ".codex" / "auth.json", home / "auth.json")
    skill_path = home / "skills" / skill_name
    if arm == "with":
        shutil.copytree(skill_dir, skill_path)
    env = os.environ.copy()
    env["CODEX_HOME"] = str(home)
    env.pop("PI_CODING_AGENT_DIR", None)
    return PreparedRunner(
        env=env,
        env_contract={
            "CODEX_HOME": "$RUNNER_HOME",
            "config": "isolated",
            "rules": "disabled",
            "skills": "native",
        },
        skill_path=skill_path,
        command_args=(),
    )


def _prepare_omp(
    base: Path,
    arm: str,
    skill_dir: Path,
    skill_name: str,
    user_home: Path,
) -> PreparedRunner:
    home = base / "omp-home"
    source_agent = user_home / ".omp" / "agent"
    target_agent = home / ".omp" / "agent"
    if source_agent.is_dir():
        shutil.copytree(
            source_agent,
            target_agent,
            ignore=shutil.ignore_patterns(
                "skills", "sessions", "history.db*", "terminal-sessions"
            ),
        )
    else:
        target_agent.mkdir(parents=True)
    overlay = base / "eval-config.yml"
    overlay.write_text(
        "retry:\n"
        "  modelFallback: false\n"
        "  usageAwareFallback: false\n"
    )
    (home / ".codex").mkdir(exist_ok=True)
    skill_path = target_agent / "skills" / skill_name
    if arm == "with":
        shutil.copytree(skill_dir, skill_path)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("CODEX_HOME", None)
    env.pop("PI_CODING_AGENT_DIR", None)
    return PreparedRunner(
        env=env,
        env_contract={
            "HOME": "$RUNNER_HOME",
            "config": "isolated-copy-without-skills-or-sessions; fallback-disabled",
            "rules": "disabled",
            "extensions": "disabled",
            "skills": "native",
        },
        skill_path=skill_path,
        command_args=("--config", str(overlay)),
    )


def prepare_runner(
    runner: str,
    base: Path,
    arm: str,
    skill_dir: Path,
    skill_name: str,
    user_home: Path | None = None,
) -> PreparedRunner:
    """Create an isolated runner profile; only the with arm receives the skill."""
    if runner not in SUPPORTED_RUNNERS:
        raise ValueError(f"unsupported runner: {runner}")
    if arm not in {"with", "without"}:
        raise ValueError(f"unsupported arm: {arm}")
    source_home = user_home or Path.home()
    base.mkdir(parents=True)
    if runner == "codex":
        return _prepare_codex(base, arm, skill_dir, skill_name, source_home)
    return _prepare_omp(base, arm, skill_dir, skill_name, source_home)


def build_command(
    runner: str,
    run_dir: Path,
    timeout: int,
    model: str,
    thinking: str,
    command_args: tuple[str, ...],
) -> list[str]:
    """Build a structured-output command without disabling native skills."""
    if runner == "codex":
        return [
            "codex", "exec", "--skip-git-repo-check", "--ephemeral",
            "--ignore-user-config", "--ignore-rules", "--json",
            "-C", str(run_dir), "-s", "workspace-write", "-m", model,
            "-c", f'model_reasoning_effort="{thinking}"', "-",
        ]
    if runner == "omp":
        return [
            "omp", *command_args, "-p", "--cwd", str(run_dir), "--mode", "json",
            "--no-rules", "--no-extensions", "--no-lsp", "--no-pty",
            "--no-prewalk", "--auto-approve", "--no-session",
            "--max-time", str(timeout),
            "--thinking", thinking, "--model", model,
        ]
    raise ValueError(f"unsupported runner: {runner}")


def run_agent(
    command: list[str],
    env: dict[str, str],
    prompt: str,
    timeout: int,
) -> RunnerResult:
    """Run one agent and terminate its complete process group at the budget."""
    started_at = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as error:
        return RunnerResult(
            started=False,
            exit_code=None,
            budget_exhausted=False,
            duration_s=round(time.monotonic() - started_at, 3),
            stdout="",
            stderr=str(error),
        )

    exhausted = False
    try:
        stdout, stderr = process.communicate(input=prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        exhausted = True
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (PermissionError, ProcessLookupError):
            process.kill()
        stdout, stderr = process.communicate()
    return RunnerResult(
        started=True,
        exit_code=process.returncode,
        budget_exhausted=exhausted,
        duration_s=round(time.monotonic() - started_at, 3),
        stdout=stdout or "",
        stderr=stderr or "",
    )


def detect_activation(runner: str, stdout: str, skill_name: str) -> bool | str:
    """Use only structured successful read events; otherwise return unknown."""
    if runner != "codex":
        return "unknown"
    suffix = f"/skills/{skill_name}/SKILL.md"
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if not isinstance(item, dict) or item.get("type") != "command_execution":
            continue
        if item.get("status") == "completed" and item.get("exit_code") == 0:
            if suffix in str(item.get("command", "")):
                return True
    return False


def inspect_runtime(
    runner: str, stdout: str, requested_model: str
) -> RuntimeObservation:
    """Verify model identity when a runner's structured trace exposes it."""
    if runner == "codex":
        terminal: str | None = None
        task_started = False
        provider_error: str | None = None
        usage: dict = {}
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "turn.started":
                task_started = True
            elif event.get("type") == "turn.completed":
                terminal = "completed"
                provider_error = None
                usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
            elif event.get("type") in {"turn.failed", "error"}:
                terminal = "failed"
                error = event.get("error")
                if isinstance(error, dict):
                    error = error.get("message")
                provider_error = str(
                    error or event.get("message") or "runner terminal model error"
                )
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        cached_tokens = usage.get("cached_input_tokens")
        total_tokens = (
            input_tokens + output_tokens
            if isinstance(input_tokens, int) and isinstance(output_tokens, int)
            else None
        )
        return RuntimeObservation(
            None, (), False,
            terminal in {"completed", "failed"} or task_started, provider_error,
            input_tokens if isinstance(input_tokens, int) else None,
            output_tokens if isinstance(output_tokens, int) else None,
            cached_tokens if isinstance(cached_tokens, int) else None,
            total_tokens, None, task_started,
        )
    if runner != "omp":
        raise ValueError(f"unsupported runner: {runner}")

    observed: list[str] = []
    successful: list[str] = []
    last_assistant: dict | None = None
    input_tokens = output_tokens = cached_tokens = total_tokens = 0
    cost_usd = 0.0
    usage_seen = False
    task_started = False
    fallback = False
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "turn_start":
            task_started = True
        if event.get("type") == "retry_fallback_applied":
            fallback = True
        if event.get("type") != "message_end":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        last_assistant = message
        provider, model = message.get("provider"), message.get("model")
        if not isinstance(provider, str) or not isinstance(model, str):
            continue
        identity = f"{provider}/{model}"
        if identity not in observed:
            observed.append(identity)
        if message.get("stopReason") != "error":
            successful.append(identity)
        usage = message.get("usage")
        if isinstance(usage, dict):
            usage_seen = True
            input_tokens += int(usage.get("input", 0) or 0)
            output_tokens += int(usage.get("output", 0) or 0)
            cached_tokens += int(usage.get("cacheRead", 0) or 0)
            total_tokens += int(usage.get("totalTokens", 0) or 0)
            cost = usage.get("cost")
            if isinstance(cost, dict) and isinstance(cost.get("total"), (int, float)):
                cost_usd += float(cost["total"])
    identity_ok = (bool(observed) or task_started) and not fallback and all(
        item == requested_model for item in observed
    )
    actual = successful[-1] if successful else (observed[-1] if observed else None)
    provider_error = None
    if last_assistant and last_assistant.get("stopReason") == "error":
        provider_error = str(
            last_assistant.get("errorMessage") or "runner terminal model error"
        )
    return RuntimeObservation(
        actual, tuple(observed), fallback, identity_ok, provider_error,
        input_tokens if usage_seen else None,
        output_tokens if usage_seen else None,
        cached_tokens if usage_seen else None,
        total_tokens if usage_seen else None,
        round(cost_usd, 8) if usage_seen else None,
        task_started,
    )


def runner_version(runner: str) -> str | None:
    command = {
        "codex": ["codex", "--version"],
        "omp": ["omp", "--version"],
    }.get(runner)
    if command is None:
        raise ValueError(f"unsupported runner: {runner}")
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=30, check=False
        )
    except OSError:
        return None
    output = (result.stdout or result.stderr).strip()
    return output or None
