"""Workflow receipts avoid encoded payloads and retain explicit failures."""

import json
import os
import subprocess
import unittest

from fixtures import load_fanout_module
from workflow_fixture import WorkflowCase, member

load_fanout_module()
from structured_worker import validate_receipt
from workflow_config import PACKAGE, resolve_recipe, validate_payload


class WorkflowContracts(WorkflowCase):
    def test_direct_receipt_and_legacy_format_are_explicit(self):
        receipt = {
            "worker_id": "worker-0001",
            "outcome": "completed",
            "summary": "Done",
            "payload": {"strengths": [], "improvements": [], "uncertainties": []},
        }
        result, error = validate_receipt(receipt, "worker-0001", True)
        self.assertIsNone(error)
        validate_payload(
            result["payload"], resolve_recipe("critique")["payload_schema"]
        )
        self.assertIsNotNone(validate_receipt(receipt, "worker-0001")[1])
        self.assertIsNotNone(validate_receipt(receipt, "worker-0002", True)[1])
        self.assertIsNotNone(
            validate_receipt({**receipt, "payload": "{}"}, "worker-0001", True)[1]
        )

    def test_workflow_stream_threshold_and_explicit_lower_limit(self):
        self.configure([member("one", "agy")])
        executable = self.executables["agy"]
        executable.write_text(
            executable.read_text().replace(
                "event('start')", "event('start')\nprint(' '*1500000)"
            )
        )
        result = self.run_workflow()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.packet()["max_output_bytes"], 8_000_000)
        self.output = self.root / "small"
        result = self.run_workflow(extra=["--max-output-bytes", "1024"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.packet()["workers"][0]["status"], "oversized_output")

    def test_native_quota_error_is_retained_without_substitution(self):
        self.configure([member("one", "agy")])
        executable = self.executables["agy"]
        executable.write_text(
            executable.read_text().replace(
                "event('start')",
                "event('start')\nprint(json.dumps({'status':'ERROR','error':'quota exceeded'}))\nsys.exit(0)",
            )
        )
        result = self.run_workflow()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            self.packet()["workers"][0]["attempts"][0]["native_error"], "quota exceeded"
        )
        self.assertEqual(self.packet()["workers"][0]["attempt_count"], 1)

    def test_install_preserves_user_roster_and_includes_complete_package(self):
        self.config = self.root / "xdg" / "agent-toolkit" / "fanout.json"
        self.config.parent.mkdir(parents=True)
        config = self.configure([member("user-model", model="provider/future")])
        destination = self.root / "codex"
        script = PACKAGE.parents[1] / "scripts" / "install.sh"
        for _ in range(2):
            result = subprocess.run(
                ["bash", str(script), "codex"],
                env={
                    **os.environ,
                    "CODEX_HOME": str(destination),
                    "XDG_CONFIG_HOME": str(self.config.parent.parent),
                },
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.config.read_text()), config)
        installed = destination / "skills" / "fanout"
        for source in PACKAGE.rglob("*"):
            if source.is_file():
                self.assertEqual(
                    source.read_bytes(),
                    (installed / source.relative_to(PACKAGE)).read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()
