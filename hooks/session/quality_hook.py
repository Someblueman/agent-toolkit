"""Codex JSON adapter. No tool installation, source edits or trust bypasses."""

import fcntl
import hashlib
import json
import os
import shlex
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from quality_lib import work_review
from quality_lib.codex_hooks import locally_registered
from quality_lib.config import (
    SetupError,
    SnapshotChanged,
    find_root,
    load,
)
from quality_lib.incremental import digest, evaluate, snapshot
from quality_lib.runner import doctor, manual_requirements, size_findings


def reply(event, text, block=False):
    if event in ("UserPromptSubmit", "PostToolUse"):
        return {
            "hookSpecificOutput": {"hookEventName": event, "additionalContext": text}
        }
    if block:
        return {"decision": "block", "reason": text}
    return {"systemMessage": text}


def unverified(payload, text):
    event = payload.get("hook_event_name")
    block = event == "Stop" and not payload.get("stop_hook_active")
    if event == "Stop":
        text += (
            "\nRepository verification is incomplete. Retry once when ready; if verification cannot "
            "finish, report the blocker without claiming successful acceptance."
        )
    return reply(event, text, block)


def setup_required(payload, root, metrics):
    metrics["outcome"] = "setup_required"
    command = shlex.join(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[2] / "tools/quality/bin/quality"),
            "--root",
            str(root),
            "setup",
            "--codex",
        ]
    )
    return unverified(
        payload,
        f"Project verification setup required for {root}.\n"
        "Before implementation, make defining this repository's green state the first task: "
        "read its AGENTS.md, development docs, CI and native test/build commands. "
        "Create or complete quality.json with verification.green (concrete acceptance criteria), "
        "verification.manual (relevant evidence that needs judgment), and the existing useful "
        "automated checks with their source/dependency inputs. Run the selected checks to "
        "establish the baseline; report existing failures and unavailable checks. "
        "Do not add tests, test counts or coverage targets just to satisfy this setup. "
        "Use proportionate evidence for the requested change; ask only when the repository "
        "does not resolve a material acceptance decision. For read-only requests, report "
        "missing setup without modifying the project.\n"
        f"After defining the configuration, provision/register with: {command}\n"
        "Language profiles are tooling starters, not a definition of green.",
    )


def preflight(root, config, current, state, metrics):
    key = digest(
        [
            config,
            {
                name: [check["policy"], sorted(check["files"])]
                for name, check in current.items()
            },
        ]
    )
    if state.get("preflight") == key:
        return ""
    messages = doctor(root, config, automated=True)
    state["preflight"] = key
    metrics["preflight"] = True
    return (
        "Verification preflight (repository criteria and tool availability):\n"
        + "\n".join(messages)
    )


def add_preflight(event, result, message):
    if not message or event == "Stop":
        return result
    if not result:
        return reply(event, message)
    if event in ("UserPromptSubmit", "PostToolUse"):
        result["hookSpecificOutput"]["additionalContext"] += "\n" + message
    else:
        result["systemMessage"] += "\n" + message
    return result


def handle(payload, metrics):
    if os.environ.get("QUALITY_REVIEW_CHILD") == "1":
        return {}
    event = payload.get("hook_event_name")
    if event not in ("UserPromptSubmit", "PostToolUse", "Stop"):
        return {}
    try:
        root = find_root(payload["cwd"], require_config=False)
    except SetupError:
        return {}  # No Git repository or explicit project configuration.
    # Recheck this event on every invocation, including commands cached by Codex.
    # Keeping quality.json for the CLI does not opt a repository into hooks.
    if not locally_registered(root, event):
        metrics["outcome"] = "not_enabled"
        return {}
    if not (root / "quality.json").is_file():
        return {} if event == "PostToolUse" else setup_required(payload, root, metrics)
    config = load(root)
    if "verification" not in config and event != "PostToolUse":
        return setup_required(payload, root, metrics)
    session = payload.get("session_id")
    if not isinstance(session, str) or not session:
        raise SetupError("Missing hook session_id")
    # OS cache, not source tree. State is per session, never a shared success certificate.
    path = work_review.state_path(root, session)
    directory = path.parent
    # One lock per physical checkout, never per shared git common directory.
    checkout = hashlib.sha256(str(root).encode()).hexdigest()
    cache_path = directory / (checkout + ".checks.json")
    with (directory / (checkout + ".lock")).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            metrics["outcome"] = "busy"
            return unverified(
                payload,
                "Quality check already running in this checkout; retry on the next event (not a pass).",
            )
        return process_locked(payload, metrics, root, config, path, cache_path)


def process_locked(payload, metrics, root, config, path, cache_path):
    event = payload["hook_event_name"]
    # Compute under the lock, since another session may just have finished.
    current = snapshot(root, config)
    state = json.loads(path.read_text()) if path.exists() else {}
    if state.get("version") != 3:
        state = {"version": 3}
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    message = preflight(root, config, current, state, metrics)
    if event == "UserPromptSubmit" and config.get("verification", {}).get("review"):
        work_review.begin(root, payload, state, path.with_suffix(".review"))
        message += (
            "\nRequired scoped review must run visibly before the final answer: "
            + work_review.command(root)
            + ". Read and assess its report with review --accept 'assessment'. "
            "If a later message only asks for status, reuse the completed report with "
            "--accept 'assessment' --same-scope instead of starting another review. "
            "Stop only checks acceptance; it never launches a reviewer."
        )
    result = process(event, payload, root, config, current, state, cache, metrics)
    if (
        event == "Stop"
        and config.get("verification", {}).get("review")
        and metrics.get("outcome") in ("pass", "cached", "skipped", "manual_required")
    ):
        review, block = work_review.finish(
            root, state, path, payload.get("stop_hook_active", False)
        )
        if snapshot(root, config) != current:
            raise SnapshotChanged(
                "Sources changed during review; rerun verification on the final files"
            )
        if review:
            metrics["outcome"] = "review_incomplete"
            if result.get("systemMessage"):
                review += "\n" + result["systemMessage"]
            result = reply(event, review, block)
    result = add_preflight(event, result, message)
    for target, value in ((path, state), (cache_path, cache)):
        work_review.save(target, value)
    return result


def process(event, payload, root, config, current, state, cache, metrics):
    if event == "UserPromptSubmit":
        # A steering prompt must not erase edits still awaiting completion checks.
        state.setdefault("baseline", current)
        return {}
    if event == "PostToolUse":
        if current == state.get("baseline") or digest(current) == state.get(
            "fast_checked"
        ):
            return {}
        code, output = measured_check(
            root, config, "fast", state, current, cache, metrics
        )
        state["fast_checked"] = digest(current)
        return reply(event, output) if output else {}
    code, output = measured_check(root, config, "full", state, current, cache, metrics)
    if not code:
        advisory = completion_advisory(root, config, current)
        state["baseline"] = current
        state.pop("pending", None)
        state.pop("fast_checked", None)
        if manual_requirements(config):
            metrics["outcome"] = "manual_required"
        return reply(event, advisory) if advisory else {}
    if payload.get("stop_hook_active") or state.get("pending"):
        return reply(
            event,
            "Repository verification checks still fail. Report this unresolved result; do not claim a pass.\n"
            + output,
        )
    state["pending"] = True
    return reply(
        event,
        "Repository verification failed. Fix only defects within the authorized task; "
        "report pre-existing findings or setup blockers without expanding scope.\n"
        + output,
        True,
    )


def completion_advisory(root, config, current):
    # Recompute even when native checks were cached; warnings are not cached results.
    files = {name for check in current.values() for name in check["files"]}
    findings = size_findings(root, config, files)
    if snapshot(root, config) != current:
        raise SnapshotChanged("Sources/configuration changed during size assessment")
    if not findings:
        return ""
    return (
        "Automated checks passed; advisory size findings remain:\n"
        + "\n".join(findings)
        + "\nAssess oversized files changed by this task and report the rationale for "
        "keeping them or refactor within the authorized scope. Report pre-existing "
        "findings without expanding scope. These warnings do not block completion."
    )


def measured_check(root, config, stage, state, current, cache, metrics):
    metrics["stage"] = stage
    # Stop verifies every automated check, including unchanged parts of the repository.
    # A source snapshot taken at prompt time is not evidence that those checks passed.
    baseline = {} if stage == "full" else state.get("baseline", {})
    return evaluate(root, config, baseline, current, cache, stage, metrics)


def log_outcome(payload, metrics, started):
    if metrics.get("outcome") == "not_enabled":
        return
    if not isinstance(payload, dict) or not payload.get("cwd"):
        return
    try:
        root = find_root(payload["cwd"], require_config=False)
        directory = Path(
            os.environ.get(
                "QUALITY_HOOK_STATE_DIR",
                str(Path.home() / ".cache/agent-toolkit/quality"),
            )
        )
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        record = dict(
            metrics,
            event=payload.get("hook_event_name"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_ms=round((time.monotonic() - started) * 1000, 2),
            session=hashlib.sha256(
                str(payload.get("session_id", "")).encode()
            ).hexdigest(),
        )
        path = directory / (hashlib.sha256(str(root).encode()).hexdigest() + ".jsonl")
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as output:
            fcntl.flock(output, fcntl.LOCK_EX)
            output.write(json.dumps(record) + "\n")
    except (SetupError, OSError, ValueError):
        pass  # Telemetry must not change enforcement or break a turn.


def main(stream):
    payload = {}
    started = time.monotonic()
    metrics = {"checked": False, "outcome": "skipped", "blocked": False}

    try:
        payload = json.load(stream)
        if not isinstance(payload, dict):
            raise SetupError("Hook input must be an object")
        result = handle(payload, metrics)
    except SnapshotChanged as exc:
        metrics["outcome"] = "snapshot_changed"
        result = unverified(
            payload,
            f"Quality snapshot changed; retry on stable sources (not a pass): {exc}",
        )
    except (SetupError, OSError, ValueError, TypeError, KeyError) as exc:
        metrics["outcome"] = "setup_error"
        result = unverified(
            payload if isinstance(payload, dict) else {},
            f"Quality check unavailable; setup required (not a pass): {exc}",
        )
    metrics["blocked"] = result.get("decision") == "block"
    log_outcome(payload, metrics, started)
    return result
