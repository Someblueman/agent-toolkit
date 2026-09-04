"""Materialize selected Codex content and protect edits using installed fingerprints."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = ".agent-toolkit-install.json"
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


def fingerprint(path: Path) -> str | None:
    if path.is_symlink():
        return "link:" + os.readlink(path)
    if not path.exists():
        return None
    if path.is_file():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return f"file:{path.stat().st_mode & 0o111}:{digest}"
    entries = []
    for child in sorted(path.iterdir()):
        if child.name not in IGNORE(str(path), [child.name]):
            entries.append((child.name, fingerprint(child)))
    return "dir:" + hashlib.sha256(json.dumps(entries).encode()).hexdigest()


def valid_target(name: str) -> bool:
    return name in {
        "AGENTS.md",
        "scripts/check_anti_bloat.py",
        "scripts/test_check_anti_bloat.py",
    } or (name.startswith("skills/") and NAME.fullmatch(name[7:]) is not None)


def read_state(path: Path) -> dict[str, str]:
    if path.is_symlink():
        raise ValueError(f"Refusing linked ownership record: {path}")
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Invalid installer ownership record")
    managed = data.get("managed")
    if not isinstance(managed, dict) or any(
        not valid_target(k) or not isinstance(v, str) for k, v in managed.items()
    ):
        raise ValueError("Invalid managed paths in installer ownership record")
    return managed


def stage_content(stage: Path) -> dict[str, Path]:
    adapter = REPO / "configs/codex"
    names = [
        line.strip()
        for line in (adapter / "skills.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(names) != len(set(names)) or any(not NAME.fullmatch(n) for n in names):
        raise ValueError("Invalid or duplicate name in configs/codex/skills.txt")
    sources = {
        "AGENTS.md": adapter / "AGENTS.md",
        "scripts/check_anti_bloat.py": REPO
        / "skills/pragmatic-engineering/scripts/check_anti_bloat.py",
    }
    sources["scripts/test_check_anti_bloat.py"] = (
        REPO / "skills/pragmatic-engineering/scripts/test_check_anti_bloat.py"
    )
    for name in names:
        shared = REPO / "skills" / name
        native = adapter / "native-skills" / name
        if shared.exists() and native.exists():
            raise ValueError(f"Ambiguous shared/native source for {name}")
        source = native if native.exists() else shared
        if not (source / "SKILL.md").is_file():
            raise ValueError(f"Missing skill source: {source}")
        target = stage / "skills" / name
        shutil.copytree(source, target, symlinks=True, ignore=IGNORE)
        metadata = adapter / "skills" / name / "openai.yaml"
        if metadata.is_file():
            (target / "agents").mkdir(exist_ok=True)
            shutil.copy2(metadata, target / "agents/openai.yaml")
        sources[f"skills/{name}"] = target
    # Validate every source before changing any installed files.
    for name, source in sources.items():
        if name.startswith("skills/"):
            continue
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if name.startswith("scripts/"):
            target.chmod(target.stat().st_mode | 0o111)
        sources[name] = target
    return sources


def remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def install(home: Path, args: argparse.Namespace, sources: dict[str, Path]) -> int:
    managed = read_state(home / STATE)
    updated = managed.copy()
    problems = 0
    readonly = args.check or args.dry_run
    # Refuse redirected parent directories even with --force.
    for name in sources.keys() | managed.keys():
        for parent in (home / name).parents:
            if parent == home:
                break
            if parent.is_symlink():
                raise ValueError(f"Refusing linked installation parent: {parent}")
    for name, source in sources.items():
        target = home / name
        expected = fingerprint(source)
        current = fingerprint(target)
        if current == expected:
            print(f"[install] unchanged: {name}")
            updated[name] = expected
            continue
        if args.check:
            print(f"[install] differs or missing: {name}")
            problems += 1
            continue
        if current is not None and current != managed.get(name) and not args.force:
            print(
                f"[install] conflict: {name}; inspect before using --force",
                file=sys.stderr,
            )
            problems += 1
            continue
        print(f"[install] {'would install' if readonly else 'install'}: {name}")
        if not readonly:
            target.parent.mkdir(parents=True, exist_ok=True)
            remove(target)
            if source.is_dir():
                shutil.copytree(source, target, symlinks=True)
            else:
                shutil.copy2(source, target)
            updated[name] = expected
    for name in managed.keys() - sources.keys():
        target = home / name
        current = fingerprint(target)
        if current is None:
            updated.pop(name)
            continue
        if args.check or not args.prune:
            print(f"[install] retired managed item: {name}; use --prune")
            problems += 1
            continue
        if current != managed[name] and not args.force:
            print(f"[install] edited retired item: {name}; preserved", file=sys.stderr)
            problems += 1
            continue
        print(f"[install] {'would prune' if readonly else 'prune'}: {name}")
        if not readonly:
            remove(target)
            updated.pop(name)
    if not readonly:
        home.mkdir(parents=True, exist_ok=True)
        state_text = (
            json.dumps({"version": 1, "managed": updated}, indent=2, sort_keys=True)
            + "\n"
        )
        state_path = home / STATE
        if not state_path.exists() or state_path.read_text() != state_text:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=home, delete=False
            ) as handle:
                handle.write(state_text)
            os.replace(handle.name, state_path)
    return int(problems > 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="Replace conflicting selected items"
    )
    parser.add_argument(
        "--prune", action="store_true", help="Remove retired managed items only"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without changing the installation",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 on missing, different, or retired content",
    )
    args = parser.parse_args()
    home = (
        Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        .expanduser()
        .absolute()
    )
    try:
        with tempfile.TemporaryDirectory(prefix="agent-toolkit-stage-") as directory:
            return install(home, args, stage_content(Path(directory)))
    except (OSError, ValueError) as error:
        print(f"[install] error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
