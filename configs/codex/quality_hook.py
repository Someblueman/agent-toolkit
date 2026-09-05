"""Codex JSON adapter. No tool installation, source edits or trust bypasses."""

import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path

from quality_lib.config import SetupError, find_root, fingerprint, inventory, load
from quality_lib.runner import check


def reply(event, text, block=False):
    if event == "PostToolUse":
        return {
            "hookSpecificOutput": {"hookEventName": event, "additionalContext": text}
        }
    if block:
        return {"decision": "block", "reason": text}
    return {"systemMessage": text}


def handle(payload):
    event = payload.get("hook_event_name")
    if event not in ("UserPromptSubmit", "PostToolUse", "Stop"):
        return {}
    try:
        root = find_root(payload["cwd"])
    except SetupError:
        return {}  # Global installation is inert outside opted-in repositories.
    config = load(root)
    files = inventory(root, config)
    current = fingerprint(root, config, files)
    session = payload.get("session_id")
    if not isinstance(session, str) or not session:
        raise SetupError("Missing hook session_id")
    key = hashlib.sha256((str(root) + session).encode()).hexdigest()
    # OS cache, not source tree. State is per session, never a shared success certificate.
    directory = Path(
        os.environ.get(
            "QUALITY_HOOK_STATE_DIR", str(Path.home() / ".cache/agent-toolkit/quality")
        )
    )
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / (key + ".json")
    with (directory / (key + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(path.read_text()) if path.exists() else {}
        result = process(event, payload, root, config, current, state)
        with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as f:
            json.dump(state, f)
        os.replace(f.name, path)
    return result


def process(event, payload, root, config, current, state):
    if event == "UserPromptSubmit":
        if not state.get("pending"):
            state.clear()
            state["baseline"] = current
        return {}
    if current == state.get("baseline"):
        return {}
    if event == "PostToolUse":
        if current == state.get("fast_checked"):
            return {}
        code, output = check(root, config, "fast")
        state["fast_checked"] = current
        return reply(event, output) if output else {}
    code, output = check(root, config, "full")
    if not code:
        state.clear()
        state["baseline"] = current
        return {}
    if payload.get("stop_hook_active") or state.get("pending"):
        state["pending"] = False
        state["baseline"] = current
        return reply(
            event,
            "Quality checks still fail. Report this unresolved result; do not claim a pass.\n"
            + output,
        )
    state["pending"] = True
    return reply(
        event,
        "Quality checks found violations. Fix only defects within the authorized task; "
        "report pre-existing findings or setup blockers without expanding scope.\n"
        + output,
        True,
    )


def main(stream):
    payload = {}
    try:
        payload = json.load(stream)
        if not isinstance(payload, dict):
            raise SetupError("Hook input must be an object")
        return handle(payload)
    except (SetupError, OSError, ValueError, TypeError, KeyError) as exc:
        event = payload.get("hook_event_name") if isinstance(payload, dict) else None
        return reply(
            event, f"Quality check unavailable; setup required (not a pass): {exc}"
        )
