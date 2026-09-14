"""Run the actual Node helper against a small SDK fixture."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from fixtures import OPENCODE_HELPER_PATH


@unittest.skipUnless(
    shutil.which("node"), "Node is required for OpenCode helper checks"
)
class OpenCodeHelper(unittest.TestCase):
    def test_deepseek_thinking_override_is_scoped_to_that_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / "sdk.mjs"
            sdk.write_text("""
import assert from 'node:assert/strict';
export async function createOpencode(options) {
  return {
    server: { close() {} },
    client: { session: {
      async create() { return { data: { id: 'session-1' } }; },
      async delete() {},
      async prompt(request) {
        assert.equal(request.agent, 'plan');
        assert.equal(request.model.providerID, 'opencode-go');
        assert.equal(request.format.type, 'json_schema');
        if (request.model.modelID === 'deepseek-v4.1-flash') {
          assert.deepEqual(options.config, {
            agent: { plan: { thinking: { type: 'disabled' } } }
          });
        } else {
          assert.equal(options.config, undefined);
        }
        return { data: { info: { structured: {
          worker_id: 'worker-0001', outcome: 'completed', summary: 'Done', result_json: '{}'
        } } } };
      }
    } }
  };
}
""")
            for model in ["deepseek-v4.1-flash", "minimax-m3"]:
                with self.subTest(model=model):
                    result = subprocess.run(
                        [
                            "node",
                            str(OPENCODE_HELPER_PATH),
                            "--sdk",
                            str(sdk),
                            "--directory",
                            directory,
                            "--port",
                            "12345",
                            "--model",
                            f"opencode-go/{model}",
                            "--agent",
                            "plan",
                            "--worker-id",
                            "worker-0001",
                            "--prompt",
                            "Review only.",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout)["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
