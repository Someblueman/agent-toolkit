"""Exercise the real completion CLI, roster and hook installation boundary."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "configs/codex/native-skills/team-leader/scripts/completion.py"
)


class Completion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="leader test ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, CODEX_HOME=str(self.root))
        self.base = self.root / "team-leader/leader"
        self.base.mkdir(parents=True)
        self.data = {
            "version": 1,
            "thread_id": "leader",
            "objective": "Finish selected item",
            "status": "active",
            "next_action": "Verify repaired CLI",
            "progress": "worker returned commit abc",
            "deadline": time.time() + 3600,
            "evidence": [],
        }
        self.roster()

    def roster(self):
        (self.base / "roster.md").write_text(
            "```json\n" + json.dumps(self.data) + "\n```\n# Existing assignments\n"
        )

    def run_cli(self, *args, payload=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            input=json.dumps(payload) if payload else None,
            text=True,
            capture_output=True,
            env=self.env,
            timeout=10,
            check=False,
        )

    def hook(self, **extra):
        result = self.run_cli(
            "hook", payload=dict(hook_event_name="Stop", session_id="leader", **extra)
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_incomplete_repair_and_complete_cycle(self):
        self.assertEqual(self.hook()["decision"], "block")
        self.data.update(
            progress="CLI now passes", next_action="Integrate checked commit"
        )
        self.roster()
        self.assertNotIn("decision", self.hook(stop_hook_active=True))
        self.assertEqual(
            json.loads(self.run_cli("check", "leader").stdout)["decision"], "block"
        )
        self.data.update(
            status="complete", evidence=["Integrated abc; CLI passed; review passed"]
        )
        self.roster()
        self.assertNotIn("decision", self.hook())

    def test_no_progress_bound_and_explicit_resume(self):
        for _ in range(3):
            self.assertEqual(
                json.loads(self.run_cli("check", "leader").stdout)["decision"], "block"
            )
        self.assertIn(
            "Three recovery",
            json.loads(self.run_cli("check", "leader").stdout)["systemMessage"],
        )
        self.assertIn("suspended", self.hook()["systemMessage"])
        self.assertEqual(self.run_cli("resume", "leader").returncode, 0)
        self.assertEqual(self.hook()["decision"], "block")

    def test_interrupt_and_deadline(self):
        self.run_cli(
            "hook", payload={"hook_event_name": "Interrupt", "session_id": "leader"}
        )
        self.assertIn("suspended", self.hook()["systemMessage"])
        self.run_cli("resume", "leader")
        self.data["deadline"] = time.time() - 1
        self.roster()
        self.assertIn("deadline reached", self.hook()["systemMessage"])

    def test_unregistered_and_legacy_rosters_inert(self):
        for session in (None, "", 123):
            result = self.run_cli(
                "hook", payload={"hook_event_name": "Stop", "session_id": session}
            )
            self.assertEqual(json.loads(result.stdout), {})
        result = self.run_cli(
            "hook", payload={"hook_event_name": "Stop", "session_id": "worker"}
        )
        self.assertEqual(json.loads(result.stdout), {})
        (self.base / "roster.md").write_text("# Old roster\n")
        self.assertEqual(self.hook(), {})

    def test_missing_evidence_and_wrong_identity(self):
        self.data["status"] = "complete"
        self.roster()
        self.assertIn("unavailable", self.hook()["systemMessage"])
        self.assertEqual(self.run_cli("check", "leader").returncode, 1)
        self.data.update(thread_id="another", status="active")
        self.roster()
        self.assertIn("identity mismatch", self.hook()["systemMessage"])

    def test_invalid_bounds_and_terminal_states(self):
        for deadline in (True, float("nan"), float("inf"), -1, "tomorrow"):
            with self.subTest(deadline=deadline):
                self.data["deadline"] = deadline
                self.roster()
                self.assertEqual(self.run_cli("check", "leader").returncode, 1)
        self.data.update(
            deadline=time.time() + 3600,
            status="blocked",
            evidence=["External host offline; reconnect required"],
        )
        self.roster()
        self.assertNotIn("decision", self.hook())
        self.data.update(status="paused", evidence=[])
        self.roster()
        self.assertNotIn("decision", self.hook())

    def test_runtime_stops_do_not_spend_heartbeat_attempts(self):
        for _ in range(5):
            self.assertEqual(self.hook()["decision"], "block")
        state = json.loads((self.base / "completion-state.json").read_text())
        self.assertNotIn("unchanged", state)
        events = [
            json.loads(line)["event"]
            for line in (self.base / "completion-events.jsonl").read_text().splitlines()
        ]
        self.assertEqual(events, ["Stop"] * 5)

    def test_corrupt_runtime_state_suspends_recovery(self):
        path = self.base / "completion-state.json"
        for value in ("[]", "null", '"scalar"', '{"unchanged": "bad"}', "broken"):
            with self.subTest(value=value):
                path.write_text(value)
                result = json.loads(self.run_cli("check", "leader").stdout)
                self.assertIn("suspended", result["systemMessage"])
                self.assertTrue(json.loads(path.read_text())["suspended"])
                self.assertIn("error", json.loads(path.read_text()))

    def test_live_worker_wait_does_not_exhaust_attempts(self):
        self.data["waiting_on"] = ["existing-worker"]
        self.roster()
        for _ in range(5):
            self.assertEqual(
                json.loads(self.run_cli("check", "leader").stdout)["decision"], "block"
            )
        self.data["deadline"] = time.time() - 1
        self.roster()
        self.assertIn(
            "deadline",
            json.loads(self.run_cli("check", "leader").stdout)["systemMessage"],
        )

    def test_install_preserves_other_hooks_and_is_idempotent(self):
        project = self.root / "project with spaces"
        (project / ".codex").mkdir(parents=True)
        path = project / ".codex/hooks.json"
        original = {
            "hooks": {
                "Stop": [{"hooks": [{"type": "command", "command": "echo existing"}]}]
            }
        }
        path.write_text(json.dumps(original))
        self.assertEqual(self.run_cli("install", str(project)).returncode, 0)
        first = path.read_bytes()
        self.assertEqual(self.run_cli("install", str(project)).returncode, 0)
        self.assertEqual(first, path.read_bytes())
        self.assertEqual(
            json.loads(first)["hooks"]["Stop"][0], original["hooks"]["Stop"][0]
        )
        path.write_text("invalid json")
        self.assertEqual(self.run_cli("install", str(project)).returncode, 1)
        self.assertEqual(path.read_text(), "invalid json")


if __name__ == "__main__":
    unittest.main()
