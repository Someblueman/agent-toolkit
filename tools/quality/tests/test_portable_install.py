"""Install a relocated toolkit into independent repositories and execute its hooks."""

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import ROOT


class PortableInstall(unittest.TestCase):
    def test_relocated_toolkit_serves_python_and_shell_repositories(self):
        with tempfile.TemporaryDirectory(prefix="quality portability '") as temporary:
            base = Path(temporary).resolve()
            toolkit = base / "shared toolkit"
            for relative in ("tools/quality", "hooks/session"):
                shutil.copytree(
                    ROOT / relative,
                    toolkit / relative,
                    ignore=shutil.ignore_patterns("__pycache__", "tests"),
                )
            for suffix, launcher, program, expected in (
                ("py", sys.executable, "print('python app')\n", "python app"),
                ("sh", "sh", "printf 'shell app\\n'\n", "shell app"),
            ):
                with self.subTest(language=suffix):
                    self.exercise(base, toolkit, suffix, launcher, program, expected)

    def exercise(self, base, toolkit, suffix, launcher, program, expected):
        repo = base / (suffix + " repository")
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "src").mkdir()
        source = repo / ("src/app." + suffix)
        source.write_text(program)
        test = (
            "import subprocess; result = subprocess.check_output("
            + repr([launcher, source.relative_to(repo).as_posix()])
            + ", text=True); assert result.strip() == "
            + repr(expected)
        )
        config = {
            "version": 1,
            "verification": {
                "green": "The application prints the expected output.",
                "manual": [],
            },
            "roots": ["src"],
            "exclude": [],
            "tools": {
                "runtime": {
                    "command": [sys.executable],
                    "version": sys.version.split()[0],
                    "version_args": ["--version"],
                    "install": [],
                }
            },
            "checks": [
                {
                    "name": "Application behavior",
                    "kind": "test",
                    "tool": "runtime",
                    "args": ["-c", test],
                    "patterns": ["*." + suffix],
                    "files": False,
                    "scope": "project",
                    "stage": "fast",
                    "failure_codes": [1],
                }
            ],
            "size": {"limit": 500, "mode": "review"},
        }
        (repo / "quality.json").write_text(json.dumps(config))
        env = dict(
            os.environ,
            CODEX_HOME=str(base / "codex"),
            QUALITY_HOOK_STATE_DIR=str(base / "state"),
        )
        command = [
            sys.executable,
            str(toolkit / "tools/quality/bin/quality"),
            "--root",
            str(repo),
            "setup",
            "--codex",
        ]
        for _ in range(2):
            result = subprocess.run(
                command,
                cwd=base,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads((repo / "quality.json").read_text()), config)
        hooks = json.loads((repo / ".codex/hooks.json").read_text())["hooks"]

        def event(name, **extra):
            registered = hooks[name][0]["hooks"][0]["command"]
            self.assertEqual(
                shlex.split(registered)[-1], str(toolkit / "hooks/session/quality.py")
            )
            result = subprocess.run(
                ["sh", "-c", registered],
                cwd=base,
                env=env,
                input=json.dumps(
                    dict(
                        cwd=str(repo), session_id=suffix, hook_event_name=name, **extra
                    )
                ),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

        event("UserPromptSubmit")
        source.write_text(program.replace(expected, "broken"))
        post = event("PostToolUse")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("FAIL Application behavior", post)
        self.assertEqual(event("Stop")["decision"], "block")
        source.write_text(program + "# repaired\n")
        self.assertEqual(event("Stop", stop_hook_active=True), {})
        log = (
            base / "state" / (hashlib.sha256(str(repo).encode()).hexdigest() + ".jsonl")
        )
        record = json.loads(log.read_text().splitlines()[-1])
        self.assertEqual(
            (record["event"], record["outcome"], record["checked"]),
            ("Stop", "pass", True),
        )
