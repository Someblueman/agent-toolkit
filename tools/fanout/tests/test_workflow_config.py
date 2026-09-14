"""Roster replacement, unknown future routes, and validation before dispatch."""

import json
import os
import unittest
from unittest.mock import patch

from fixtures import load_fanout_module
from workflow_fixture import WorkflowCase, member

load_fanout_module()
from workflow_config import resolve_recipe


class WorkflowConfig(WorkflowCase):
    def test_replacement_removal_other_defaults_and_explicit_precedence(self):
        self.config.write_text(json.dumps({"version": 1, "workflows": {}}))
        defaults = resolve_recipe("critique", self.config)
        user = self.root / "xdg" / "agent-toolkit" / "fanout.json"
        user.parent.mkdir(parents=True)
        user.write_text(
            json.dumps(
                {
                    "version": 1,
                    "workflows": {"review-plan": {"members": [member("user")]}},
                }
            )
        )
        self.configure([member("explicit", "muse", "a/future-model")])
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(user.parent.parent)}):
            self.assertEqual(resolve_recipe("review-plan")["members"][0]["id"], "user")
            explicit = resolve_recipe("review-plan", self.config)
            self.assertEqual([m["id"] for m in explicit["members"]], ["explicit"])
            self.assertEqual(
                resolve_recipe("critique", self.config)["members"], defaults["members"]
            )
        self.assertEqual(explicit["config_path"], str(self.config))

    def test_malformed_configs_fail_without_launch(self):
        valid = self.configure([member("one")])
        bads = [
            {},
            {**valid, "version": 2},
            {**valid, "workflows": {"unknown": {"members": [member("one")]}}},
            {**valid, "workflows": {"review-plan": {"members": []}}},
            {
                **valid,
                "workflows": {
                    "review-plan": {"members": [member("one"), member("one")]}
                },
            },
            {
                **valid,
                "workflows": {
                    "review-plan": {
                        "members": [member("one", settings={"argv": ["--bad"]})]
                    }
                },
            },
            {
                **valid,
                "workflows": {"review-plan": {"members": [member("one", "absent")]}},
            },
        ]
        for bad in bads:
            self.config.write_text(json.dumps(bad))
            result = self.run_workflow(extra=["--describe"])
            self.assertEqual(result.returncode, 2, result.stderr)
        self.config.write_text('{"version":1,"version":1,"workflows":{}}')
        self.assertEqual(self.run_workflow().returncode, 2)
        self.config.unlink()
        self.assertEqual(self.run_workflow().returncode, 2)
        self.assertFalse(self.events.exists())


if __name__ == "__main__":
    unittest.main()
