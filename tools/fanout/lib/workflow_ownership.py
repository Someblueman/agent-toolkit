"""Read-only checkout identity, assignment validation, and final-state ownership checks."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path, PurePosixPath

from workflow_config import fields, identifier, read_json, text


def git(directory, *args, check=True):
    result = subprocess.run(
        ["git", "-C", str(directory), *args],
        capture_output=True,
        check=False,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    if check and result.returncode:
        raise ValueError(
            f"git {args[0]} in {directory}: {result.stderr.decode(errors='replace').strip()}"
        )
    return result


def snapshot(directory, *, implementation=False):
    directory = Path(directory).resolve()
    head_result = git(directory, "rev-parse", "--verify", "HEAD", check=False)
    head = head_result.stdout.decode().strip() if head_result.returncode == 0 else None
    files = {}
    for root, dirs, names in os.walk(directory, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for name in sorted(names + [d for d in dirs if (Path(root) / d).is_symlink()]):
            path = Path(root) / name
            if name == ".git":
                continue
            relative = path.relative_to(directory).as_posix()
            if path.is_symlink():
                if implementation:
                    raise ValueError(
                        f"implementation checkouts cannot contain symlinks: {relative}"
                    )
                files[relative] = {"link": os.readlink(path)}
            elif path.is_file():
                files[relative] = {
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "executable": bool(path.stat().st_mode & 0o111),
                }
            else:
                raise ValueError(f"unsupported special file: {relative}")
    return {"head": head, "files": files}


def owned_path(value):
    text(value, "owned path")
    raw = value.rstrip("/")
    path = PurePosixPath(raw)
    if (
        path.is_absolute()
        or not raw
        or any(p in {"", ".", "..", ".git"} for p in raw.split("/"))
        or any(c in value for c in "*?[]\\")
    ):
        raise ValueError(
            f"ownership needs literal relative files or directory/ paths: {value}"
        )
    return value


def covers(owner, path):
    return path.startswith(owner) if owner.endswith("/") else owner == path


def overlaps(left, right):
    return (
        left.rstrip("/") == right.rstrip("/")
        or covers(left, right)
        or covers(right, left)
    )


def resolve_assignments(path, members):
    data = read_json(path)
    fields(data, ("version", "assignments"))
    if (
        data["version"] != 1
        or not isinstance(data["assignments"], list)
        or not 1 <= len(data["assignments"]) <= 50
    ):
        raise ValueError("assignments version 1 requires 1..50 items")
    member_map = {m["id"]: m for m in members}
    result, ids, directories, ownership, bases = [], set(), set(), [], set()
    branches = set()
    for item in data["assignments"]:
        fields(
            item,
            (
                "id",
                "member",
                "task",
                "working_directory",
                "base",
                "owned_paths",
                "acceptance",
                "interfaces",
                "depends_on",
            ),
        )
        item_id = identifier(item["id"])
        if item_id in ids:
            raise ValueError("duplicate assignment id")
        ids.add(item_id)
        if not isinstance(item["member"], str) or item["member"] not in member_map:
            raise ValueError("assignment references unknown member")
        member = member_map[item["member"]]
        if member["harness"] == "agy" or (
            member["harness"] == "opencode"
            and member.get("settings", {}).get("agent", "plan") == "plan"
        ):
            raise ValueError("assignment requires a write-capable harness/profile")
        text(item["task"], "task")
        text(item["interfaces"], "interfaces")
        directory = Path(
            text(item["working_directory"], "working_directory")
        ).expanduser()
        if not directory.is_absolute():
            raise ValueError("assignment working_directory must be absolute")
        directory = directory.resolve()
        if (
            str(directory)
            != git(directory, "rev-parse", "--show-toplevel").stdout.decode().strip()
        ):
            raise ValueError("assignment must name the checkout root")
        if any(
            directory == p or directory.is_relative_to(p) or p.is_relative_to(directory)
            for p in directories
        ):
            raise ValueError("assignments need distinct non-nested checkouts")
        directories.add(directory)
        common = (
            git(directory, "rev-parse", "--path-format=absolute", "--git-common-dir")
            .stdout.decode()
            .strip()
        )
        branch = (
            git(directory, "symbolic-ref", "-q", "HEAD", check=False)
            .stdout.decode()
            .strip()
        )
        if branch and (common, branch) in branches:
            raise ValueError("assignments cannot share a branch")
        branches.add((common, branch))
        if git(directory, "status", "--porcelain").stdout:
            raise ValueError(f"assignment checkout must start clean: {directory}")
        if b"160000 " in git(directory, "ls-files", "--stage").stdout:
            raise ValueError("implementation submodules are not supported")
        base = (
            git(
                directory,
                "rev-parse",
                "--verify",
                text(item["base"], "base") + "^{commit}",
            )
            .stdout.decode()
            .strip()
        )
        before = snapshot(directory, implementation=True)
        if before["head"] != base:
            raise ValueError("checkout HEAD must match assignment base")
        bases.add(base)
        for key in ("owned_paths", "acceptance", "depends_on"):
            if not isinstance(item[key], list) or any(
                not isinstance(v, str) or not v.strip() for v in item[key]
            ):
                raise ValueError(f"{key} must be an array of strings")
        if not item["owned_paths"] or not item["acceptance"]:
            raise ValueError("owned_paths and acceptance must be nonempty")
        for commit in item["depends_on"]:
            if git(
                directory, "merge-base", "--is-ancestor", commit, base, check=False
            ).returncode:
                raise ValueError(f"unmet prerequisite commit: {commit}")
        for owner in item["owned_paths"]:
            owned_path(owner)
            if any(overlaps(owner, other) for other in ownership):
                raise ValueError(f"overlapping ownership: {owner}")
            existing = directory / owner
            if existing.is_dir() and not owner.endswith("/"):
                raise ValueError("directory ownership must end with /")
            ownership.append(owner)
        result.append(
            {
                **item,
                "base": base,
                "working_directory": str(directory),
                "before": before,
                "route": member,
            }
        )
    if len(bases) != 1:
        raise ValueError("assignments must share the same approved base commit")
    return result


def audit_assignment(item):
    directory = Path(item["working_directory"])
    after = snapshot(directory, implementation=True)
    before = item["before"]
    changed = sorted(
        p
        for p in before["files"].keys() | after["files"].keys()
        if before["files"].get(p) != after["files"].get(p)
    )
    violations = [
        p for p in changed if not any(covers(owner, p) for owner in item["owned_paths"])
    ]
    if git(
        directory,
        "merge-base",
        "--is-ancestor",
        item["base"],
        after["head"] or "",
        check=False,
    ).returncode:
        violations.append("HEAD is not a descendant of the assigned base")
    # Include committed changes even if a worker subsequently restores the worktree.
    committed = (
        git(
            directory, "diff", "--name-only", "-z", "--no-renames", item["base"], "HEAD"
        )
        .stdout.decode()
        .split("\0")
    )
    violations += [
        p
        for p in committed
        if p and not any(covers(owner, p) for owner in item["owned_paths"])
    ]
    return {
        "head": after["head"],
        "changed_paths": changed,
        "violations": sorted(set(violations)),
        "conforming": not violations,
    }
