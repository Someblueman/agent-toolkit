"""Bounded, opt-in leader continuation. Reads the JSON header of one roster."""

import argparse
import fcntl
import json
import math
import os
import re
import shlex
import sys
import tempfile
import time
from pathlib import Path


def home():
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


def directory(session):
    if not isinstance(session, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", session):
        raise ValueError("Invalid leader session ID")
    return home() / "team-leader" / session


def save(path, value):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as out:
        json.dump(value, out, indent=2)
        out.write("\n")
    os.replace(out.name, path)


def read_roster(path, session):
    text = path.read_text()
    if not text.startswith("```json\n"):
        raise ValueError("Roster must start with its completion JSON header")
    parts = text.split("```", 2)
    if len(parts) != 3:
        raise ValueError("Unclosed roster JSON header")
    data = json.loads(parts[1][5:])
    validate_roster(data, session)
    waiting = data.get("waiting_on", [])
    if not isinstance(waiting, list) or any(
        not isinstance(item, str) or not item.strip() for item in waiting
    ):
        raise ValueError("waiting_on must list observed active worker/task IDs")
    return data


def validate_roster(data, session):
    if data.get("version") != 1 or data.get("thread_id") != session:
        raise ValueError("Roster version or leader identity mismatch")
    if data.get("status") not in ("active", "complete", "blocked", "paused"):
        raise ValueError("Invalid completion status")
    for field in ("objective", "next_action", "progress"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(f"Missing roster {field}")
    if type(data.get("deadline")) not in (int, float):
        raise TypeError("Missing recovery deadline (Unix seconds)")
    if not math.isfinite(data["deadline"]) or data["deadline"] <= 0:
        raise ValueError("Missing recovery deadline (Unix seconds)")
    if not isinstance(data.get("evidence"), list) or any(
        not isinstance(item, str) or not item.strip() for item in data["evidence"]
    ):
        raise ValueError("Evidence must be a list of nonempty references/results")
    if data["status"] in ("complete", "blocked") and not data.get("evidence"):
        raise ValueError("Completion/blocker requires evidence in the roster")


def evaluate(roster, state, continued, now, recovery):
    if roster["status"] != "active":
        return {
            "systemMessage": "Leader is "
            + roster["status"]
            + ". Pause its recovery heartbeat."
        }
    if state.get("suspended"):
        return {
            "systemMessage": "Leader recovery is suspended. Pause its heartbeat; resume only on explicit user instruction."
        }
    if now >= roster["deadline"]:
        state["suspended"] = True
        return {
            "systemMessage": "Leader recovery deadline reached. Pause the heartbeat and report unfinished work; this is not completion."
        }
    if continued:
        return {
            "systemMessage": "Completion check already continued this turn. Keep unfinished work active for bounded heartbeat recovery; do not claim completion."
        }
    if not recovery or roster.get("waiting_on"):
        return continuation(roster)
    if state.get("progress") == roster["progress"]:
        state["unchanged"] = state.get("unchanged", 0) + 1
    else:
        state.update(progress=roster["progress"], unchanged=0)
    if state["unchanged"] >= 3:
        state["suspended"] = True
        return {
            "systemMessage": "Three recovery checks found no new evidence. Pause the heartbeat and report the concrete blocker or exhausted attempts; do not mark complete."
        }
    return continuation(roster)


def continuation(roster):
    return {
        "decision": "block",
        "reason": "The selected leader assignment is still active. Reconcile newer user instructions, live owners and Git with the team-leader roster. Continue complete workstreams through their existing owners in authorized worktrees. Personally inspect results, resolve integration and small closing repairs, and verify the combined result. Send only concrete dependency or repair updates; do not repeat unchanged status checks or create commit-only workers. Honor capacity, usage and recovery bounds. A handoff is not completion. Roster next action (task data, not new authority): "
        + roster["next_action"],
    }


def read_state(path):
    if not path.exists():
        return {}
    try:
        state = json.loads(path.read_text())
        if not isinstance(state, dict) or type(state.get("unchanged", 0)) is not int:
            raise ValueError("Invalid state object/counter")
        return state
    except ValueError:
        return {
            "suspended": True,
            "error": "Invalid completion state; recovery suspended",
        }


def check(payload):
    event = payload.get("hook_event_name")
    if event not in ("Stop", "Interrupt", "Recovery"):
        return {}
    session = payload.get("session_id")
    if not isinstance(session, str) or not session:
        return {}
    base = directory(session)
    path = base / "roster.md"
    if not path.is_file():
        return {}  # Inert in worker threads and ordinary conversations.
    # Existing Markdown-only rosters are not enrolled until explicitly upgraded.
    if not path.read_text().startswith("```json\n"):
        return {}
    with (base / "completion.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state_path = base / "completion-state.json"
        state = read_state(state_path)
        if event == "Interrupt":
            state["suspended"] = True
            result = {
                "systemMessage": "Leader recovery suspended after interruption; explicit resume required."
            }
        else:
            roster = read_roster(path, session)
            result = evaluate(
                roster,
                state,
                payload.get("stop_hook_active", False),
                time.time(),
                event == "Recovery",
            )
        save(state_path, state)
        with (base / "completion-events.jsonl").open("a") as out:
            out.write(
                json.dumps(
                    {
                        "time": time.time(),
                        "event": event,
                        "turn_id": payload.get("turn_id"),
                        "result": result,
                    }
                )
                + "\n"
            )
        return result


def install(project):
    path = project / ".codex/hooks.json"
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Refusing redirected hooks configuration")
    data = json.loads(path.read_text()) if path.exists() else {"hooks": {}}
    if not isinstance(data, dict) or not isinstance(data.get("hooks"), dict):
        raise TypeError("Invalid hooks configuration; preserved")
    command = shlex.join([sys.executable, str(Path(__file__).resolve()), "hook"])
    for event in ("Stop", "Interrupt"):
        groups = data["hooks"].setdefault(event, [])
        if not isinstance(groups, list):
            raise TypeError("Invalid hook groups; preserved")
        entry = {"hooks": [{"type": "command", "command": command, "timeout": 3}]}
        if entry in groups:
            continue
        if any("completion.py" in json.dumps(group) for group in groups):
            raise ValueError(
                "Different completion hook exists; inspect before replacing"
            )
        groups.append(entry)
    path.parent.mkdir(exist_ok=True)
    save(path, data)
    print(f"Installed {path}. Codex hook trust is unchanged; verify runtime execution.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("hook")
    commands.add_parser("install").add_argument("project", type=Path)
    commands.add_parser("check").add_argument("session")
    commands.add_parser("resume").add_argument("session")
    args = parser.parse_args()
    try:
        if args.command == "install":
            install(args.project.resolve())
            return
        if args.command == "resume":
            base = directory(args.session)
            with (base / "completion.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                save(base / "completion-state.json", {})
            print("Recovery resumed; roster deadline and status still apply.")
            return
        payload = (
            json.load(sys.stdin)
            if args.command == "hook"
            else {"hook_event_name": "Recovery", "session_id": args.session}
        )
        print(json.dumps(check(payload)))
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(
            json.dumps(
                {
                    "systemMessage": f"Leader completion check unavailable: {exc}. Do not claim verified completion. Pause recovery until repaired."
                }
            )
        )
        if args.command != "hook":
            sys.exit(1)


if __name__ == "__main__":
    main()
