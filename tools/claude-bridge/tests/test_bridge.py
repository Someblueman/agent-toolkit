"""Exercise the actual CLI with a controlled Claude process."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "bin/claude-bridge"

FAKE_CLAUDE = """#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path

args = sys.argv[1:]
log = Path(os.environ['FAKE_CLAUDE_LOG']) / f'{os.getpid()}.json'
messages = []
for line in sys.stdin:
    prompt = json.loads(line)['message']['content']
    messages.append(prompt)
    log.write_text(json.dumps({'args': args, 'messages': messages, 'environment': {
        key: os.environ.get(key) for key in (
            'CLAUDE_CODE_EFFORT_LEVEL', 'CLAUDE_CODE_DISABLE_AUTO_MEMORY',
            'CLAUDE_CODE_SKIP_PROMPT_HISTORY', 'CLAUDE_CODE_DISABLE_THINKING',
            'CLAUDE_CODE_DISABLE_1M_CONTEXT',
            'MAX_THINKING_TOKENS')
    }}))
    mode = os.environ.get('FAKE_CLAUDE_MODE', 'success')
    if mode == 'slow' or 'slow' in prompt:
        time.sleep(2)
    if mode == 'hang' or 'Concurrent follow-up' in prompt:
        time.sleep(30)
    if mode == 'nonzero':
        sys.exit(7)
    if mode == 'invalid':
        print('not json', flush=True)
    else:
        if mode == 'verbose':
            print(json.dumps({'type': 'assistant', 'message': {'content': 'x' * 2048}}), flush=True)
        answer = 'second response' if len(messages) > 1 or '<claude_response>' in prompt else 'first response'
        print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False,
                          'result': answer, 'modelUsage': {'claude-opus-test': {}},
                          'total_cost_usd': 0.01}), flush=True)
    if mode == 'exit_after_first':
        sys.exit(0)
"""


class BridgeTest(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="claude-bridge-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state = self.root / "state"
        self.logs = self.root / "logs"
        self.logs.mkdir()
        self.claude = self.root / "claude"
        self.claude.write_text(FAKE_CLAUDE)
        self.claude.chmod(0o755)
        self.environment = {
            **os.environ,
            "FAKE_CLAUDE_LOG": str(self.logs),
            "CLAUDE_CODE_DISABLE_THINKING": "1",
            "CLAUDE_CODE_DISABLE_1M_CONTEXT": "1",
            "MAX_THINKING_TOKENS": "0",
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
            env={**self.environment, "FAKE_CLAUDE_MODE": mode},
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(run.returncode, code, run.stdout + run.stderr)
        return json.loads(run.stdout) if run.stdout else {"error": run.stderr}

    def start(self, *, mode: str = "success", timeout: str = "10") -> dict:
        message_file = self.root / "initial-message.txt"
        message_file.write_text("Initial claim with evidence")
        return self.cli(
            "start",
            "--claude",
            str(self.claude),
            "--timeout-seconds",
            timeout,
            "--message-file",
            str(message_file),
            mode=mode,
        )

    def test_async_reply_uses_one_live_claude(self) -> None:
        started_at = time.monotonic()
        first = self.start(mode="slow")
        self.assertLess(time.monotonic() - started_at, 1.5)
        exchange_id = first["exchange_id"]
        self.assertIn(first["state"], {"queued", "running"})
        pending = self.cli("wait", exchange_id, "--timeout-seconds", "0", code=3)
        self.assertIn(pending["state"], {"queued", "running"})
        finished = self.cli("wait", exchange_id, "--timeout-seconds", "5", mode="slow")
        self.assertEqual(finished["response"], "first response")
        self.assertEqual(finished["observed_models"], ["claude-opus-test"])
        self.assertEqual(finished["cost_usd"], 0.01)

        followup_file = self.root / "followup.txt"
        followup_file.write_text("Challenge the claim")
        second = self.cli("reply", exchange_id, "--message-file", str(followup_file))
        self.assertEqual(second["turn"], 2)
        answer = self.cli("wait", exchange_id, "--timeout-seconds", "5")
        self.assertEqual(answer["response"], "second response")
        logs = [json.loads(path.read_text()) for path in self.logs.iterdir()]
        self.assertEqual(len(logs), 1)
        followup = logs[0]
        self.assertIn("Initial claim with evidence", followup["messages"][0])
        self.assertEqual(followup["messages"][1], "Challenge the claim")
        self.assertEqual(followup["args"][0:2], ["--restricted", "--safe-mode"])
        for flag in ("--no-session-persistence", "--tools", "--disallowedTools"):
            self.assertIn(flag, followup["args"])
        self.assertEqual(followup["args"][followup["args"].index("--tools") + 1], "")
        self.assertEqual(
            followup["args"][followup["args"].index("--model") + 1], "opus"
        )
        self.assertEqual(
            followup["args"][followup["args"].index("--effort") + 1], "high"
        )
        self.assertEqual(followup["environment"]["CLAUDE_CODE_EFFORT_LEVEL"], "high")
        self.assertEqual(
            followup["environment"]["CLAUDE_CODE_DISABLE_AUTO_MEMORY"], "1"
        )
        self.assertEqual(
            followup["environment"]["CLAUDE_CODE_SKIP_PROMPT_HISTORY"], "1"
        )
        self.assertIsNone(followup["environment"]["CLAUDE_CODE_DISABLE_THINKING"])
        self.assertIsNone(followup["environment"]["CLAUDE_CODE_DISABLE_1M_CONTEXT"])
        self.assertIsNone(followup["environment"]["MAX_THINKING_TOKENS"])
        self.assertEqual(
            followup["args"][followup["args"].index("--input-format") + 1],
            "stream-json",
        )

    def test_active_turn_rejects_followup_and_cancel_stops_it(self) -> None:
        first = self.start(mode="hang")
        exchange_id = first["exchange_id"]
        self.cli("reply", exchange_id, "--message", "Too soon", code=2)
        self.assertEqual(len(list((self.state / exchange_id / "turns").iterdir())), 1)
        cancelled = self.cli("cancel", exchange_id)
        self.assertIn(cancelled["state"], {"cancel_requested", "cancelled"})
        final = self.cli("wait", exchange_id, "--timeout-seconds", "5", code=1)
        self.assertEqual(final["state"], "cancelled")

    def test_long_exchange_is_sent_without_character_truncation(self) -> None:
        message = "Evidence " * 26_000
        message_file = self.root / "long-message.txt"
        message_file.write_text(message)
        first = self.cli(
            "start", "--claude", str(self.claude), "--message-file", str(message_file)
        )
        exchange_id = first["exchange_id"]
        self.cli("wait", exchange_id, "--timeout-seconds", "5")
        self.cli("reply", exchange_id, "--message", "Follow up")
        self.cli("wait", exchange_id, "--timeout-seconds", "5")
        logs = [json.loads(path.read_text()) for path in self.logs.iterdir()]
        self.assertEqual(len(logs), 1)
        self.assertIn(message, logs[0]["messages"][0])
        self.assertEqual(logs[0]["messages"][1], "Follow up")

    def test_default_and_reply_timeout_override(self) -> None:
        first = self.cli(
            "start", "--claude", str(self.claude), "--message", "Default limit"
        )
        exchange = self.state / first["exchange_id"]
        self.assertEqual(
            json.loads((exchange / "meta.json").read_text())["timeout_seconds"], 0
        )
        self.cli("wait", first["exchange_id"], "--timeout-seconds", "5")

        older = self.start(timeout="1")
        exchange_id = older["exchange_id"]
        self.cli("wait", exchange_id, "--timeout-seconds", "5")
        self.cli(
            "reply",
            exchange_id,
            "--timeout-seconds",
            "3",
            "--message",
            "First slow follow-up",
            mode="slow",
        )
        result = self.cli("wait", exchange_id, "--timeout-seconds", "5")
        self.assertEqual(result["state"], "succeeded")
        self.assertEqual(result["timeout_seconds"], 3)
        self.assertEqual(
            json.loads((self.state / exchange_id / "meta.json").read_text())[
                "timeout_seconds"
            ],
            3,
        )
        self.cli(
            "reply", exchange_id, "--message", "Second slow follow-up", mode="slow"
        )
        result = self.cli("wait", exchange_id, "--timeout-seconds", "5")
        self.assertEqual(result["state"], "succeeded")
        self.assertEqual(result["timeout_seconds"], 3)
        self.cli(
            "reply",
            exchange_id,
            "--timeout-seconds",
            "0",
            "--message",
            "No turn limit",
        )
        result = self.cli("wait", exchange_id, "--timeout-seconds", "5")
        self.assertEqual(result["state"], "succeeded")
        self.assertEqual(result["timeout_seconds"], 0)
        self.cli(
            "reply",
            exchange_id,
            "--timeout-seconds",
            "-1",
            "--message",
            "Invalid",
            code=2,
        )

    def test_concurrent_followups_create_only_one_turn(self) -> None:
        first = self.start()
        exchange_id = first["exchange_id"]
        self.cli("wait", exchange_id, "--timeout-seconds", "5")
        command = [
            str(CLI),
            "--state-dir",
            str(self.state),
            "reply",
            exchange_id,
            "--message",
            "Concurrent follow-up",
        ]
        environment = {**self.environment, "FAKE_CLAUDE_MODE": "hang"}
        processes = [
            subprocess.Popen(
                command,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for _ in range(2)
        ]
        outcomes = [process.communicate(timeout=5) for process in processes]
        self.assertEqual(sorted(process.returncode for process in processes), [0, 2])
        self.assertEqual(len(list((self.state / exchange_id / "turns").iterdir())), 2)
        self.assertEqual(sum(bool(stdout) for stdout, _ in outcomes), 1)
        self.cli("cancel", exchange_id)
        self.cli("wait", exchange_id, "--timeout-seconds", "5", code=1)

    def test_timeout_invalid_output_and_nonzero_are_not_success(self) -> None:
        for mode, timeout, state in (
            ("hang", "0.3", "timed_out"),
            ("invalid", "5", "failed"),
            ("nonzero", "5", "failed"),
        ):
            with self.subTest(mode=mode):
                first = self.start(mode=mode, timeout=timeout)
                result = self.cli(
                    "wait", first["exchange_id"], "--timeout-seconds", "5", code=1
                )
                self.assertEqual(result["state"], state)
                self.assertNotIn("response", result)
                if state == "timed_out":
                    self.assertIn("0.3-second turn limit", result["error"])

    def test_stream_events_do_not_consume_final_result_limit(self) -> None:
        started = self.cli(
            "start",
            "--claude",
            str(self.claude),
            "--max-output-bytes",
            "1024",
            "--message",
            "A short answer",
            mode="verbose",
        )
        result = self.cli("wait", started["exchange_id"], "--timeout-seconds", "5")
        self.assertEqual(result["response"], "first response")

    def test_private_files_and_input_validation(self) -> None:
        first = self.start()
        exchange = self.state / first["exchange_id"]
        self.cli("wait", first["exchange_id"], "--timeout-seconds", "5")
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(exchange.stat().st_mode), 0o700)
        for path in exchange.rglob("*"):
            if path.is_file():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600, path)
        self.cli("result", "invalid-id", code=2)
        self.cli("reply", first["exchange_id"], "--message", "", code=2)

    def test_dead_worker_is_reported_as_failure(self) -> None:
        first = self.start()
        exchange_id = first["exchange_id"]
        self.cli("wait", exchange_id, "--timeout-seconds", "5")
        exchange = self.state / exchange_id
        current = exchange / "turns/0001"
        status_path = current / "status.json"
        status = json.loads(status_path.read_text())
        status["state"] = "running"
        status["created_at"] = time.time() - 20
        status_path.write_text(json.dumps(status))
        result = self.cli("result", exchange_id, code=1)
        self.assertEqual(result["state"], "failed")
        self.assertIn("worker exited", result["error"])

    def test_worker_restart_replays_successful_history(self) -> None:
        first = self.start(mode="exit_after_first")
        exchange_id = first["exchange_id"]
        self.cli("wait", exchange_id, "--timeout-seconds", "5")
        exchange = self.state / exchange_id
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            import fcntl

            with (exchange / "daemon.lock").open("rb") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(lock, fcntl.LOCK_UN)
                    break
                except BlockingIOError:
                    time.sleep(0.1)
        self.cli("reply", exchange_id, "--message", "Resume after restart")
        result = self.cli("wait", exchange_id, "--timeout-seconds", "5")
        self.assertEqual(result["response"], "second response")
        logs = [json.loads(path.read_text()) for path in self.logs.iterdir()]
        self.assertEqual(len(logs), 2)
        replay = next(
            log["messages"][0]
            for log in logs
            if "Resume after restart" in log["messages"][0]
        )
        self.assertIn("Initial claim with evidence", replay)
        self.assertIn("first response", replay)

    def test_close_stops_idle_worker_and_rejects_reply(self) -> None:
        first = self.start()
        exchange_id = first["exchange_id"]
        result = self.cli("wait", exchange_id, "--timeout-seconds", "5")
        pid = result["worker_pid"]
        self.assertFalse(result["closed"])
        closed = self.cli("close", exchange_id)
        self.assertTrue(closed["closed"])
        self.cli("reply", exchange_id, "--message", "Too late", code=2)
        self.assertEqual(len(list((self.state / exchange_id / "turns").iterdir())), 1)
        self.cli("close", exchange_id)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            self.fail("worker did not exit after close")


if __name__ == "__main__":
    unittest.main()
