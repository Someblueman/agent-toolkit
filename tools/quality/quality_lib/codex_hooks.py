"""Install shared hook commands; repositories retain their own quality policy."""

import json
import os
import re
import shlex
import sys
from pathlib import Path

from .config import SetupError, inside
from .runner import run

EVENTS = ("UserPromptSubmit", "PostToolUse", "Stop")


def read_hooks(path):
    if not path.exists():
        return {"hooks": {}}
    try:
        data = json.loads(path.read_text())
    except ValueError as exc:
        raise SetupError(f"Invalid {path}; leaving it untouched") from exc
    if not isinstance(data, dict) or not isinstance(data.get("hooks"), dict):
        raise SetupError(f"Unsupported hooks shape in {path}")
    return data


def hook_entry(event, toolkit):
    entry = {
        "hooks": [
            {
                "type": "command",
                "command": shlex.join(
                    [sys.executable, str(toolkit / "hooks/session/quality.py")]
                ),
                "timeout": 300,
                "statusMessage": "Checking repository quality",
            }
        ]
    }
    if event == "PostToolUse":
        entry["matcher"] = "Bash|apply_patch|Edit|Write"
    return entry


def equivalent(group, entry):
    if group == entry:
        return True
    hooks = group.get("hooks", []) if isinstance(group, dict) else []
    if not isinstance(hooks, list) or len(hooks) != 1 or not isinstance(hooks[0], dict):
        return False
    if not isinstance(hooks[0].get("command"), str):
        return False
    try:
        command = shlex.split(hooks[0].get("command", ""))
    except ValueError:
        return False
    wanted = shlex.split(entry["hooks"][0]["command"])
    if len(command) != 2 or command[1] != wanted[1]:
        return False
    if (
        not Path(command[0]).is_absolute()
        or not Path(command[0]).is_file()
        or not os.access(command[0], os.X_OK)
    ):
        return False
    # Reuse the already configured Python interpreter across project environments.
    code, version = run(Path.cwd(), [command[0], "--version"], 20)
    match = re.fullmatch(r"Python 3\.(\d+)\.\d+.*", version.strip())
    if code or not match or int(match[1]) < 10:
        return False
    normalized = dict(
        group, hooks=[dict(hooks[0], command=entry["hooks"][0]["command"])]
    )
    return normalized == entry


def registered(data, event, entry, path):
    groups = data["hooks"].get(event, [])
    if not isinstance(groups, list):
        raise SetupError(f"Invalid {event} hook list in {path}")
    owned = [group for group in groups if "quality.py" in str(group)]
    if len(owned) > 1 or any(not equivalent(group, entry) for group in owned):
        raise SetupError(
            f"Existing quality adapter differs or is duplicated for {event} in {path}; "
            "review before replacing"
        )
    return bool(owned)


def plan_codex(root, toolkit, user=False):
    if not (toolkit / "hooks/session/quality.py").is_file():
        raise SetupError(
            "Shared quality hook is missing; use a complete agent-toolkit checkout"
        )
    user_home = (
        Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        .expanduser()
        .resolve()
    )
    destination = user_home if user else inside(root, ".codex")
    if destination.exists() and not destination.is_dir():
        raise SetupError(f"Hook destination is not a directory: {destination}")
    path = inside(destination, "hooks.json")
    user_path = inside(user_home, "hooks.json")
    data = read_hooks(path)
    inherited = (
        read_hooks(user_path) if not user and path != user_path else {"hooks": {}}
    )
    changed, reused = False, []
    for event in EVENTS:
        entry = hook_entry(event, toolkit)
        local = registered(data, event, entry, path)
        shared = registered(inherited, event, entry, user_path)
        if shared:
            reused.append(event)
        if not local and not shared:
            data["hooks"].setdefault(event, []).append(entry)
            changed = True
    return path, data, changed, reused


def install_codex(root, toolkit, dry_run=False, user=False):
    path, data, changed, reused = plan_codex(root, toolkit, user)
    if reused:
        print("Reusing configured user hooks for: " + ", ".join(reused))
    if dry_run:
        print(f"{'Would update' if changed else 'No changes to'} {path}")
        print(json.dumps(data, indent=2))
    elif changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")
        print(f"Installed {path}")
    else:
        print(f"No hook registration changes needed for {path}")
    print(
        "Review/trust the configured hooks in Codex; registration does not grant trust or enablement."
    )
