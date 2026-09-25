"""Exercise Muse through the bridge CLI without a network provider."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "bin/claude-bridge"
FAKE_MUSE = """#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path

args = sys.argv[1:]
prompt = Path(args[args.index('--prompt-file') + 1]).read_text()
log = Path(os.environ['FAKE_MUSE_LOG']) / f'{os.getpid()}.json'
log.write_text(json.dumps({
    'args': args, 'prompt': prompt, 'cwd': os.getcwd(),
    'config': os.environ['XDG_CONFIG_HOME'],
    'data': os.environ['XDG_DATA_HOME'],
    'auth_present': (Path(os.environ['XDG_CONFIG_HOME']) / 'muse/auth.json').is_file(),
}))
mode = os.environ.get('FAKE_MUSE_MODE', 'success')
if mode == 'hang':
    time.sleep(30)
if mode == 'invalid':
    print('not json', flush=True)
    sys.exit(0)
def emit(kind, payload):
    print(json.dumps({'schema_version': 1, 'payload_type': kind, 'payload': payload}), flush=True)
emit('runtime.command.accepted', {'command_kind': 'turn.submit', 'command_id': 'root'})
if mode == 'missing_terminal':
    sys.exit(0)
if mode == 'failed':
    emit('run.terminal.failed', {'command_id': 'root', 'terminal': 'failed', 'reason': 'provider failed'})
else:
    answer = 'second response' if "Muse's earlier answer:" in prompt else 'first response'
    emit('run.terminal.completed', {'command_id': 'root', 'terminal': 'completed', 'text': answer})
"""


class MuseBridgeTest(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="muse-bridge-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state = self.root / "state"
        self.logs = self.root / "logs"
        self.logs.mkdir()
        self.muse = self.root / "muse"
        self.muse.write_text(FAKE_MUSE)
        self.muse.chmod(0o755)
        config = self.root / "original-config/muse"
        config.mkdir(parents=True)
        (config / "auth.json").write_text("{}")
        (config / "auth.json").chmod(0o600)
        self.environment = {
            **os.environ,
            "FAKE_MUSE_LOG": str(self.logs),
            "XDG_CONFIG_HOME": str(config.parent),
        }

    def tearDown(self) -> None:
        if self.state.exists():
            for exchange in self.state.iterdir():
                if exchange.is_dir():
                    subprocess.run(
                        [
                            str(CLI),
                            "--state-dir",
                            str(self.state),
                            "close",
                            exchange.name,
                        ],
                        capture_output=True,
                        timeout=5,
                        check=False,
                    )

    def cli(self, *args: str, code: int = 0, mode: str = "success") -> dict:
        run = subprocess.run(
            [str(CLI), "--state-dir", str(self.state), *args],
            cwd=self.root,
            env={**self.environment, "FAKE_MUSE_MODE": mode},
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(run.returncode, code, run.stdout + run.stderr)
        return json.loads(run.stdout) if run.stdout else {"error": run.stderr}

    def start(self, *, mode: str = "success", timeout: str = "0") -> dict:
        return self.cli(
            "start",
            "--peer",
            "muse",
            "--muse",
            str(self.muse),
            "--timeout-seconds",
            timeout,
            "--message",
            "Initial evidence",
            mode=mode,
        )

    def test_followup_replays_private_history_with_isolation(self) -> None:
        first = self.start()
        exchange_id = first["exchange_id"]
        result = self.cli("wait", exchange_id, "--timeout-seconds", "5")
        self.assertEqual(result["response"], "first response")
        self.assertEqual(result["peer"], "muse")
        self.cli("reply", exchange_id, "--message", "Challenge the evidence")
        result = self.cli("wait", exchange_id, "--timeout-seconds", "5")
        self.assertEqual(result["response"], "second response")
        logs = [json.loads(path.read_text()) for path in self.logs.iterdir()]
        self.assertEqual(len(logs), 2)
        initial = next(log for log in logs if log["prompt"] == "Initial evidence")
        followup = next(
            log for log in logs if "Challenge the evidence" in log["prompt"]
        )
        self.assertIn("Initial evidence", followup["prompt"])
        self.assertIn("first response", followup["prompt"])
        self.assertIn("Muse's earlier answer:", followup["prompt"])
        for log in (initial, followup):
            for flag in (
                "--json",
                "--no-session-log",
                "--no-foreign-personal-context",
                "--disable-shell",
                "--disable-write",
                "--disable-web-tools",
            ):
                self.assertIn(flag, log["args"])
            self.assertNotIn("--trust-workspace", log["args"])
            self.assertNotIn("--workspace", log["args"])
            exchange_root = (self.state / exchange_id).resolve()
            self.assertTrue(Path(log["cwd"]).is_relative_to(exchange_root))
            self.assertTrue(Path(log["config"]).is_relative_to(exchange_root))
            self.assertTrue(Path(log["data"]).is_relative_to(exchange_root))
            self.assertTrue(log["auth_present"])
        self.assertNotEqual(initial["config"], followup["config"])
        self.cli("close", exchange_id)
        for turn in ("0001", "0002"):
            auth_link = (
                self.state / exchange_id / "turns" / turn / "muse-config/muse/auth.json"
            )
            self.assertFalse(auth_link.exists())
        self.assertEqual(stat.S_IMODE((self.state / exchange_id).stat().st_mode), 0o700)

    def test_model_and_effort_override(self) -> None:
        started = self.cli(
            "start",
            "--peer",
            "muse",
            "--muse",
            str(self.muse),
            "--model",
            "custom-model",
            "--effort",
            "ultra",
            "--message",
            "Check options",
        )
        self.cli("wait", started["exchange_id"], "--timeout-seconds", "5")
        log = json.loads(next(self.logs.iterdir()).read_text())
        self.assertEqual(log["args"][log["args"].index("--model") + 1], "custom-model")
        self.assertEqual(
            log["args"][log["args"].index("--reasoning-effort") + 1], "ultra"
        )

    def test_cancel_timeout_and_invalid_results(self) -> None:
        hanging = self.start(mode="hang", timeout="0.2")
        result = self.cli(
            "wait", hanging["exchange_id"], "--timeout-seconds", "5", code=1
        )
        self.assertEqual(result["state"], "timed_out")
        for mode in ("invalid", "missing_terminal", "failed"):
            with self.subTest(mode=mode):
                first = self.start(mode=mode)
                result = self.cli(
                    "wait", first["exchange_id"], "--timeout-seconds", "5", code=1
                )
                self.assertEqual(result["state"], "failed")
                self.assertNotIn("response", result)
        active = self.start(mode="hang")
        self.cli("cancel", active["exchange_id"])
        result = self.cli(
            "wait", active["exchange_id"], "--timeout-seconds", "5", code=1
        )
        self.assertEqual(result["state"], "cancelled")


if __name__ == "__main__":
    unittest.main()
