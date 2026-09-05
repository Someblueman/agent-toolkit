import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "tools/quality/bin/quality"
HOOK = ROOT / "hooks/session/quality.py"
sys.path.insert(0, str(ROOT / "tools/quality"))
build = importlib.import_module("quality_lib.profiles").build


class Repository(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        self.source = self.root / "src/example.py"
        self.source.write_text("value = 1\n")

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), *args],
            text=True,
            capture_output=True,
            timeout=660,
            check=False,
        )

    def config(self, body="raise SystemExit(0)"):
        config = build(self.root, "python", roots=["src"])
        script = self.root / "linter.py"
        script.write_text(
            "import sys\nif '--version' in sys.argv:\n print('lint 1.0.0')\nelse:\n "
            + body
            + "\n"
        )
        config["tools"]["native"] = {
            "command": [sys.executable, str(script)],
            "version": "1.0.0",
            "version_args": ["--version"],
            "install": [],
        }
        config["checks"] = config["checks"][:1]
        config["checks"][0]["args"] = []
        self.write_config(config)
        return config

    def write_config(self, config):
        (self.root / "quality.json").write_text(json.dumps(config))

    def hook(self, event, **fields):
        payload = dict(
            cwd=str(self.root),
            session_id="test-session",
            hook_event_name=event,
            **fields,
        )
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
            env=dict(os.environ, QUALITY_HOOK_STATE_DIR=str(self.root / "state")),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)
