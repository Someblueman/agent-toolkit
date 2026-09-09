"""Checkout-local, content-keyed selection for lifecycle checks."""

import hashlib
import json
import os
import shutil
from pathlib import Path

from .config import SnapshotChanged, inside, inventory, load, matches

# Include nested configuration as well as files outside source roots.
DEFAULT_INPUTS = [
    "**/pyproject.toml",
    "**/*ruff.toml",
    "**/uv.lock",
    "**/biome.json*",
    "**/quality.biome.json",
    "**/package.json",
    "**/package-lock.json",
    "**/pnpm-lock.yaml",
    "**/yarn.lock",
    "**/bun.lock*",
    "**/Cargo.lock",
    "**/eslint.config.*",
    "**/tsconfig*.json",
    "**/Cargo.toml",
    "**/rust-toolchain*",
    "**/*rustfmt.toml",
    "**/.cargo/config*",
    "**/go.mod",
    "**/go.sum",
    "**/go.work*",
    "**/.golangci.*",
    "**/quality.golangci.json",
    "**/.clang-tidy",
    "**/compile_commands.json",
    "**/.hlint.yaml",
    "**/*.cabal",
    "**/cabal.project*",
    "**/stack.yaml*",
    "**/.shellcheckrc",
    "Makefile",
    "CMakeLists.txt",
]
C_SOURCES = (".c", ".cc", ".cpp", ".cxx")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def file_hash(root, name):
    return hashlib.sha256(inside(root, name).read_bytes()).hexdigest()


def config_candidates(root, config):
    ignored = {
        ".git",
        ".quality",
        "node_modules",
        ".venv",
        "target",
        "build",
        "__pycache__",
    }
    for base, dirs, files in os.walk(root):
        dirs[:] = [
            d
            for d in dirs
            if d not in ignored
            and not (Path(base) / d).is_symlink()
            and not matches(
                (Path(base) / d).relative_to(root).as_posix() + "/", config["exclude"]
            )
        ]
        for name in files:
            yield (Path(base) / name).relative_to(root).as_posix()


def input_hashes(root, patterns, candidates):
    # Literal paths can opt in generated compiler databases under ignored build/.
    selected = {
        name
        for name in candidates
        if matches(name, patterns)
        or matches(name, [p.removeprefix("**/") for p in patterns])
    }
    for pattern in patterns:
        if not any(c in pattern for c in "*?[") and (root / pattern).is_file():
            selected.add(pattern)
    return {name: file_hash(root, name) for name in sorted(selected)}


def tool_stamp(root, tool):
    stamps = []
    for index, argument in enumerate(tool["command"]):
        value = argument.replace("{root}", str(root))
        resolved = (shutil.which(value) or value) if index == 0 else value
        path = Path(resolved)
        if not path.is_absolute():
            path = root / path
        if index and not path.is_file():
            continue
        try:
            stat = path.stat()
            stamps.append([str(path.resolve()), stat.st_mtime_ns, stat.st_size])
        except OSError:
            stamps.append([str(path), "missing"])
    return stamps


def engine_stamp():
    directory = Path(__file__).parent
    return digest({p.name: p.read_text() for p in sorted(directory.glob("*.py"))})


def snapshot(root, config, include_manual=False):
    if load(root) != config:
        raise SnapshotChanged(
            "Quality configuration changed during checks; retry on stable sources"
        )
    files = inventory(root, config)
    hashes = {name: file_hash(root, name) for name in files}
    inputs = {}
    candidates = list(config_candidates(root, config))
    result = {}
    engine = engine_stamp()
    tools = {name: tool_stamp(root, tool) for name, tool in config["tools"].items()}
    for spec in config["checks"]:
        if spec["stage"] == "manual" and not include_manual:
            continue
        patterns = tuple(spec.get("inputs", DEFAULT_INPUTS))
        if patterns not in inputs:
            inputs[patterns] = input_hashes(root, patterns, candidates)
        tool = config["tools"][spec["tool"]]
        result[spec["name"]] = {
            "files": {
                name: value
                for name, value in hashes.items()
                if matches(name, spec["patterns"])
            },
            "inputs": inputs[patterns],
            "policy": digest(
                [
                    engine,
                    spec,
                    tool,
                    config["roots"],
                    config["exclude"],
                    config["size"],
                    tools,
                ]
            ),
        }
    return result


def select(spec, previous, current):
    now = current["files"]
    old = previous.get("files", {})
    changed = {
        name for name in old.keys() | now.keys() if old.get(name) != now.get(name)
    }
    invalidated = any(previous.get(key) != current[key] for key in ("inputs", "policy"))
    if not changed and not invalidated:
        return []
    mode = spec.get("scope", "files" if spec["files"] else "project")
    broad = invalidated or bool(changed - now.keys()) or mode == "project"
    if mode == "translation-units":
        broad |= any(Path(name).suffix not in C_SOURCES for name in changed)
        return sorted(
            name
            for name in (now if broad else changed)
            if Path(name).suffix in C_SOURCES
        )
    return sorted(now if broad else changed)


def evaluate(root, config, baseline, current, cache, stage, metrics):
    """Cache only successful checks on identical inputs and selected scopes."""
    from .runner import execute_check, verify_tool

    summaries, details, failed = [], [], False
    for spec in config["checks"]:
        if spec["stage"] == "manual" or (stage == "fast" and spec["stage"] == "full"):
            continue
        name = spec["name"]
        selected = select(spec, baseline.get(name, {}), current[name])
        if not selected:
            continue
        key = digest([current[name], selected])
        if cache.get(name) == key:
            metrics["cached_checks"] = metrics.get("cached_checks", 0) + 1
            continue
        metrics["checked"] = True
        metrics["selected_files"] = metrics.get("selected_files", 0) + len(selected)
        verify_tool(root, spec["tool"], config["tools"][spec["tool"]])
        code, output = execute_check(root, config, spec, selected)
        # Never certify a check if relevant inputs changed during execution.
        if snapshot(root, config).get(name) != current[name]:
            raise SnapshotChanged(
                "Sources/configuration changed during checks; retry on stable sources"
            )
        if not code:
            cache[name] = key
        failed |= bool(code)
        summaries.append(
            f"{'FAIL' if code else 'PASS'} {name} ({len(selected)} selected files)"
        )
        details.insert(0 if code else len(details), output)
    if snapshot(root, config) != current:
        raise SnapshotChanged(
            "Sources/configuration changed during checks; retry on stable sources"
        )
    metrics["outcome"] = (
        "fail" if failed else ("pass" if metrics["checked"] else "skipped")
    )
    return int(failed), "\n".join(
        sorted(summaries, key=lambda s: not s.startswith("FAIL")) + details
    )
