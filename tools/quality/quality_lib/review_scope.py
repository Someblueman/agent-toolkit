"""Capture a work interval without changing the checkout, real index or Git objects."""

import os
import subprocess
import tempfile
from pathlib import Path

from .config import SetupError


def git(root, *args, env=None):
    try:
        result = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", *args],
            cwd=root,
            env=dict(os.environ if env is None else env, GIT_OPTIONAL_LOCKS="0"),
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SetupError(f"Cannot capture review scope: {exc}") from exc
    if result.returncode:
        raise SetupError(
            "Cannot capture review scope: " + result.stderr.decode(errors="replace")
        )
    return result.stdout.decode().strip()


def capture(root, directory):
    if (
        git(root, "config", "--bool", "--default", "false", "core.sparseCheckout")
        == "true"
    ):
        raise SetupError(
            "Automatic review needs a full checkout; sparse checkout is unsupported"
        )
    objects = Path(
        git(root, "rev-parse", "--path-format=absolute", "--git-path", "objects")
    )
    # A superproject tree cannot represent uncommitted submodule contents.
    status = git(root, "status", "--porcelain=v2", "--ignore-submodules=none")
    for line in status.splitlines():
        fields = line.split(" ")
        if fields[0] == "u" or (fields[0] in ("1", "2") and fields[2].startswith("S")):
            raise SetupError(
                "Resolve merge conflicts or changed submodules before automatic review"
            )
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    database = directory / "scope.git"
    if not database.exists():
        git(root, "init", "--bare", str(database))
        (database / "objects/info/alternates").write_text(str(objects) + "\n")
    with tempfile.TemporaryDirectory(dir=directory) as temporary:
        env = dict(
            os.environ,
            GIT_INDEX_FILE=str(Path(temporary) / "index"),
            GIT_OBJECT_DIRECTORY=str(database / "objects"),
        )
        head = git(root, "rev-parse", "--revs-only", "HEAD")
        if not head:
            git(root, "read-tree", "--empty", env=env)
        else:
            git(root, "read-tree", head, env=env)
        git(root, "add", "--all", "--", ".", env=env)
        return git(root, "write-tree", env=env)


def diff_command(directory, before, after):
    return [
        "git",
        f"--git-dir={directory / 'scope.git'}",
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--find-renames",
        before,
        after,
        "--",
    ]
