"""Validate the small, repository-owned command contract."""

import fnmatch
import hashlib
import json
import os
from pathlib import Path


class SetupError(ValueError):
    """Configuration or tool availability prevents checking code."""


def find_root(start):
    start = Path(start).resolve()
    for root in (start, *start.parents):
        if (root / "quality.json").is_file():
            return root
        if (root / ".git").exists():
            break
    raise SetupError("No quality.json; run quality setup --profile <language> first")


def argv(value):
    if not isinstance(value, list) or not value:
        raise SetupError("Commands must be nonempty argument arrays")
    if any(not isinstance(v, str) or not v or "\x00" in v for v in value):
        raise SetupError("Command arguments must be nonempty strings without NUL")


def strings(value, name, nonempty=False):
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise SetupError(f"{name} must be a string array")
    if nonempty and (not value or any(not v for v in value)):
        raise SetupError(f"{name} must not be empty")


def inside(root, name):
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise SetupError(f"Path escapes repository or is a symlink: {name}")
    return path


def load(root):
    try:
        data = json.loads(inside(root, "quality.json").read_text())
        validate(data)
        return data
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SetupError(f"Invalid quality.json: {exc}") from exc


def validate(data):
    allowed = {"version", "roots", "exclude", "tools", "checks", "size"}
    if not isinstance(data, dict) or set(data) != allowed or data["version"] != 1:
        raise SetupError(
            "Expected version 1 and roots/exclude/tools/checks/size fields"
        )
    strings(data["roots"], "roots", True)
    strings(data["exclude"], "exclude")
    if not isinstance(data["tools"], dict) or not data["tools"]:
        raise SetupError("At least one tool is required")
    for tool in data["tools"].values():
        validate_tool(tool)
    if not isinstance(data["checks"], list) or not data["checks"]:
        raise SetupError("At least one check is required")
    for check in data["checks"]:
        validate_check(check, data["tools"])
    size = data["size"]
    if set(size) != {"limit", "mode"} or type(size["limit"]) is not int:
        raise SetupError("size requires integer limit and mode")
    if size["limit"] < 1 or size["mode"] not in ("review", "error"):
        raise SetupError("Invalid size policy")


def validate_tool(tool):
    if set(tool) != {"command", "version_args", "version", "install"}:
        raise SetupError("Tool requires command/version_args/version/install")
    argv(tool["command"])
    argv(tool["version_args"])
    if not isinstance(tool["version"], str) or not tool["version"]:
        raise SetupError("Tool version must be an exact nonempty version")
    if not isinstance(tool["install"], list):
        raise SetupError("install must be an array of commands (empty means external)")
    for command in tool["install"]:
        argv(command)


def validate_check(check, tools):
    if set(check) != {
        "name",
        "tool",
        "args",
        "patterns",
        "stage",
        "files",
        "failure_codes",
    }:
        raise SetupError(
            "Check requires name/tool/args/patterns/stage/files/failure_codes"
        )
    codes = check["failure_codes"]
    if (
        not isinstance(codes, list)
        or not codes
        or any(type(n) is not int or n < 1 or n > 255 for n in codes)
    ):
        raise SetupError("failure_codes must contain positive exit codes")
    if check["tool"] not in tools:
        raise SetupError("Check references an unknown tool")
    strings(check["args"], "args")
    strings(check["patterns"], "patterns", True)
    if check["stage"] not in ("fast", "full") or type(check["files"]) is not bool:
        raise SetupError("Invalid check stage or files flag")
    if not isinstance(check["name"], str) or not check["name"]:
        raise SetupError("Check name is required")


def matches(name, patterns):
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def inventory(root, config):
    files = source_files(root, config)
    if not files:
        raise SetupError("Source inventory is empty")
    patterns = [p for c in config["checks"] for p in c["patterns"]]
    covered = sorted(f for f in files if matches(f, patterns))
    known = {
        ".py",
        ".pyi",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".rs",
        ".go",
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".h",
        ".hpp",
        ".hs",
        ".lhs",
        ".sh",
        ".bash",
    }
    uncovered = sorted(f for f in files if Path(f).suffix in known and f not in covered)
    if uncovered:
        raise SetupError("No configured check covers: " + ", ".join(uncovered[:10]))
    if not covered:
        raise SetupError("No source files match configured checks")
    for check in config["checks"]:
        if not any(matches(f, check["patterns"]) for f in covered):
            raise SetupError(f"{check['name']}: no matching source files")
    return covered


def source_files(root, config):
    files = set()
    for name in config["roots"]:
        path = inside(root, name)
        if not path.exists():
            raise SetupError(f"Missing source root: {name}")
        candidates = [path] if path.is_file() else walk(root, path, config["exclude"])
        for item in candidates:
            relative = item.relative_to(root).as_posix()
            if matches(relative, config["exclude"]):
                continue
            if item.is_symlink():
                raise SetupError(f"Symlink in source inventory: {relative}")
            if item.is_file():
                files.add(relative)
    return files


def walk(root, path, exclude):
    for base, dirs, files in os.walk(path):
        dirs[:] = [
            d
            for d in dirs
            if not matches((Path(base) / d).relative_to(root).as_posix() + "/", exclude)
        ]
        for name in dirs + files:
            item = Path(base) / name
            if item.is_symlink():
                raise SetupError(f"Symlink in source tree: {item}")
        yield from (Path(base) / f for f in files)


def fingerprint(root, config, files):
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode())
    # Include native configuration and lockfiles, including nested package configs.
    extra = {
        "quality.json",
        "pyproject.toml",
        "ruff.toml",
        ".ruff.toml",
        "uv.lock",
        "biome.json",
        "biome.jsonc",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "Cargo.toml",
        "Cargo.lock",
        "go.mod",
        "go.sum",
        ".golangci.yml",
        ".golangci.yaml",
        ".clang-tidy",
        ".hlint.yaml",
        "quality.biome.json",
        "quality.golangci.json",
        ".shellcheckrc",
        "eslint.config.js",
        "eslint.config.mjs",
        "eslint.config.cjs",
        "rust-toolchain.toml",
        "rust-toolchain",
    }
    selected = set(files)
    for name in config["roots"]:
        path = root / name
        if path.is_dir():
            selected.update(
                p.relative_to(root).as_posix()
                for p in walk(root, path, config["exclude"])
                if p.name in extra
                and p.is_file()
                and not matches(p.relative_to(root).as_posix(), config["exclude"])
            )
    selected.update(p.name for p in root.iterdir() if p.name in extra)
    for name in sorted(selected):
        digest.update(name.encode())
        digest.update(inside(root, name).read_bytes())
    return digest.hexdigest()
