"""Size advisories survive successful and cached completion checks."""

import json

from support import Repository
from test_work_review import ReviewRepository


class SizeHooks(Repository):
    def test_full_only_warning_survives_cached_stop_and_new_session(self):
        config = self.config()
        config["checks"][0]["stage"] = "full"
        self.write_config(config)
        self.hook("UserPromptSubmit")
        self.source.write_text("value = 1\n" * 501)
        self.assertNotIn("SIZE", str(self.hook("PostToolUse")))
        for fields in ({}, {"stop_hook_active": True}, {"session_id": "other"}):
            result = self.hook("Stop", **fields)
            self.assertNotIn("decision", result)
            self.assertIn("SIZE src/example.py: 501", result["systemMessage"])
            self.assertIn("Assess oversized files changed", result["systemMessage"])
            self.assertNotIn("PASS Ruff", result["systemMessage"])
        log = next((self.root / "state").glob("*.jsonl"))
        self.assertEqual(
            json.loads(log.read_text().splitlines()[-1])["outcome"], "cached"
        )
        self.source.write_text("value = 1\n" * 500)
        self.assertEqual(self.hook("Stop"), {})

    def test_size_error_still_blocks(self):
        config = self.config()
        config["size"]["mode"] = "error"
        self.write_config(config)
        self.source.write_text("value = 1\n" * 501)
        result = self.hook("Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("SIZE src/example.py: 501", result["reason"])


class SizeReviewHooks(ReviewRepository):
    def test_incomplete_review_keeps_size_warning(self):
        self.changed()
        self.source.write_text("value = 2\n" * 501)
        result = self.hook("Stop")
        self.assertEqual(result["decision"], "block")
        self.assertIn("Required review is incomplete", result["reason"])
        self.assertIn("SIZE src/example.py: 501", result["reason"])
        self.assertFalse(self.calls.exists())
