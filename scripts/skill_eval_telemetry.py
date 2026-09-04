"""Deterministic trace and workspace measurements for skill evaluations."""

from __future__ import annotations

import difflib
import json
from pathlib import Path


IGNORED_PARTS = {".git", ".pytest_cache", "__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
SOURCE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".go", ".h", ".hpp", ".js", ".mjs",
    ".py", ".rs", ".sh", ".ts", ".tsx",
}
CODEX_TOOL_ITEMS = {
    "command_execution", "dynamic_tool_call", "file_change", "mcp_tool_call",
}


def _events(stdout: str) -> list[dict]:
    events: list[dict] = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def trace_metrics(runner: str, stdout: str) -> dict[str, int]:
    """Count native tool actions and agent loop steps within one runner."""
    events = _events(stdout)
    if runner == "codex":
        completed = [
            event.get("item", {}) for event in events
            if event.get("type") == "item.completed"
        ]
        return {
            "tool_calls": sum(
                item.get("type") in CODEX_TOOL_ITEMS for item in completed
            ),
            "agent_steps": sum(
                item.get("type") == "agent_message" for item in completed
            ),
        }
    if runner == "omp":
        return {
            "tool_calls": sum(
                event.get("type") == "tool_execution_start" for event in events
            ),
            "agent_steps": sum(
                event.get("type") == "turn_start" for event in events
            ),
        }
    raise ValueError(f"unsupported runner: {runner}")


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(part in IGNORED_PARTS for part in path.parts)
        and path.suffix not in IGNORED_SUFFIXES
    }


def _lines(value: bytes | None) -> list[str]:
    if value is None:
        return []
    try:
        return value.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return []


def _line_delta(before: list[str], after: list[str]) -> tuple[int, int]:
    added = deleted = 0
    for operation, old_start, old_end, new_start, new_end in (
        difflib.SequenceMatcher(a=before, b=after).get_opcodes()
    ):
        if operation in {"replace", "delete"}:
            deleted += old_end - old_start
        if operation in {"replace", "insert"}:
            added += new_end - new_start
    return added, deleted


def workspace_metrics(before: Path, after: Path) -> dict:
    """Measure the final patch without invoking Git inside task workspaces."""
    original, final = _tree(before), _tree(after)
    changed = sorted(
        path for path in set(original) | set(final)
        if original.get(path) != final.get(path)
    )
    additions = deletions = 0
    for path in changed:
        added, deleted = _line_delta(
            _lines(original.get(path)), _lines(final.get(path))
        )
        additions += added
        deletions += deleted
    final_loc = sum(
        len(_lines(contents)) for path, contents in final.items()
        if Path(path).suffix in SOURCE_SUFFIXES
    )
    return {
        "changed_files": changed,
        "files_changed": len(changed),
        "lines_added": additions,
        "lines_deleted": deletions,
        "final_loc": final_loc,
    }
