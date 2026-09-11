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


def locally_registered(root):
    path = root / ".codex/hooks.json"
    if not path.is_file():
        return False
    script = str(Path(__file__).resolve().parents[3] / "hooks/session/quality.py")
    data = read_hooks(path)
    for groups in data["hooks"].values():
        for group in groups:
            for hook in group.get("hooks", []):
                if script in shlex.split(hook.get("command", "")):
                    return True
    return False


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
                "timeout": 1800 if event == "Stop" else 300,
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


def upgrade_stop(data, toolkit):
    """Migrate only our exact former definition; custom handlers still conflict."""
    entry = hook_entry("Stop", toolkit)
    previous = {"hooks": [dict(entry["hooks"][0], timeout=300)]}
    changed = False
    for group in data["hooks"].get("Stop", []):
        if equivalent(group, previous):
            group["hooks"][0]["timeout"] = 1800
            changed = True
    return changed


def user_hooks_path():
    return (
        Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        .expanduser()
        .resolve()
        / "hooks.json"
    )


def plan_codex(root, toolkit):
    if not (toolkit / "hooks/session/quality.py").is_file():
        raise SetupError(
            "Shared quality hook is missing; use a complete agent-toolkit checkout"
        )
    destination = inside(root, ".codex")
    if destination.exists() and not destination.is_dir():
        raise SetupError(f"Hook destination is not a directory: {destination}")
    path = inside(destination, "hooks.json")
    data = read_hooks(path)
    shared = read_hooks(user_hooks_path())
    if any("quality.py" in str(groups) for groups in shared["hooks"].values()):
        raise SetupError(
            "Global quality hooks remain; run uninstall-codex --global before opting in per repository"
        )
    changed = upgrade_stop(data, toolkit)
    for event in EVENTS:
        entry = hook_entry(event, toolkit)
        if not registered(data, event, entry, path):
            data["hooks"].setdefault(event, []).append(entry)
            changed = True
    return path, data, changed


def uninstall_global(toolkit, dry_run=False):
    """Remove only recognized toolkit registrations; preserve unrelated user hooks."""
    path = user_hooks_path()
    data = read_hooks(path)
    upgrade_stop(data, toolkit)
    for event in EVENTS:
        entry = hook_entry(event, toolkit)
        registered(data, event, entry, path)  # Reject custom or duplicate definitions.
        if event in data["hooks"]:
            remaining = [
                group for group in data["hooks"][event] if not equivalent(group, entry)
            ]
            if remaining:
                data["hooks"][event] = remaining
            else:
                del data["hooks"][event]
    if dry_run:
        print(f"Would remove toolkit quality hooks from {path}")
        print(json.dumps(data, indent=2))
    elif path.exists():
        path.write_text(json.dumps(data, indent=2) + "\n")
        print(f"Removed global toolkit quality hooks from {path}")


def install_codex(root, toolkit, dry_run=False):
    path, data, changed = plan_codex(root, toolkit)
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
