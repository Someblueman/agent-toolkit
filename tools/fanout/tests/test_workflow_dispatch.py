"""Mixed native CLI dispatch, evidence validation, and all-member completion."""

import json
import unittest

from workflow_fixture import WorkflowCase, member


class WorkflowDispatch(WorkflowCase):
    def test_mixed_roster_concurrency_and_configuration_only_extension(self):
        self.configure(
            [
                member("future", model="provider/glm-future"),
                member("critic", "claude"),
                member("reviewer", "agy"),
                member("muse", "muse"),
            ]
        )
        result = self.run_workflow(
            extra=["--concurrency", "2"], env={"WORKFLOW_BARRIER": "1"}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = self.packet()
        self.assertEqual(packet["schema_version"], 4)
        self.assertEqual(packet["valid_results"], 4)
        self.assertEqual(
            [w["member_id"] for w in packet["workers"]],
            ["future", "critic", "reviewer", "muse"],
        )
        self.assertEqual(packet["workers"][0]["requested_model"], "provider/glm-future")
        events = [json.loads(line) for line in self.events.read_text().splitlines()]
        active = peak = 0
        for event in sorted(events, key=lambda e: e["time"]):
            active += 1 if event["kind"] == "start" else -1
            peak = max(peak, active)
        self.assertEqual(active, 0)
        self.assertEqual(peak, 2)
        self.assertEqual((self.output / "packet.json").stat().st_mode & 0o777, 0o600)

    def test_describe_never_launches_or_creates_output(self):
        self.configure([member("one")])
        result = self.run_workflow(extra=["--describe"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["requested_workers"], 1)
        self.assertFalse(self.events.exists())
        self.assertFalse(self.output.exists())

    def test_missing_invalid_timeout_and_input_change_are_not_success(self):
        for bad, status in [
            ("blocked", "blocked"),
            ("invalid", "invalid_result"),
            ("nonzero", "nonzero_exit"),
            ("hang", "timeout"),
            ("mutate", "ok"),
        ]:
            with self.subTest(bad=bad):
                self.output = self.root / bad
                self.configure([member("good"), member("bad", "claude", bad)])
                result = self.run_workflow(extra=["--timeout-seconds", "1.1"])
                self.assertEqual(result.returncode, 1, result.stderr)
                packet = self.packet()
                self.assertEqual(packet["workers"][1]["status"], status)
                self.assertEqual(packet["workers"][1]["attempt_count"], 1)
                if bad == "mutate":
                    self.assertIsNotNone(packet["input_change"])
                else:
                    self.assertEqual(packet["missing_assignments"], ["bad"])
                self.assertEqual(packet["workers"][0]["status"], "ok")

    def test_critique_empty_lists_and_ephemeral_settings(self):
        self.configure(
            [
                member("one", "claude", settings={"effort": "high"}),
                member("two", "pi", settings={"effort": "low"}),
            ],
            "critique",
        )
        result = self.run_workflow("critique")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.packet()["workers"][0]["result"]["payload"],
            {"strengths": [], "improvements": [], "uncertainties": []},
        )
        events = [
            json.loads(line)
            for line in self.events.read_text().splitlines()
            if json.loads(line)["kind"] == "start"
        ]
        self.assertEqual(events[0]["effort"], "high")
        self.assertIn("--thinking", events[1]["args"])

    def test_ambiguous_options_and_missing_executable_fail_before_launch(self):
        self.configure([member("one")])
        for extra in [
            ["--model", "x"],
            ["--workers", "1"],
            ["--harness", "pi"],
            ["--min-results", "1"],
            ["--pi", str(self.root / "absent")],
            ["--timeout-seconds", "nan"],
        ]:
            with self.subTest(extra=extra):
                result = self.run_workflow(extra=extra)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(self.events.exists())
                self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
