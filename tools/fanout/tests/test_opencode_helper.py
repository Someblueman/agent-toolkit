"""Run the real Node helper through async SDK completion and error boundaries."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from fixtures import OPENCODE_HELPER_PATH

SDK = """
import assert from 'node:assert/strict';
export async function createOpencode(options) {
  assert.deepEqual(options.config, { agent: { plan: { permission: { edit: 'deny' } } } });
  let submitted = false;
  let polls = 0;
  return { server: { close() {} }, client: { session: {
    async create() { return { data: { id: 's1' } }; },
    async delete() {},
    async promptAsync(request) {
      assert.equal(submitted, false);
      submitted = true;
      assert.equal(request.format, undefined);
      assert.equal(request.agent, 'plan');
      assert.equal(request.model.providerID, 'opencode-go');
      return {};
    },
    async status() { return { data: {} }; },
    async messages() {
      assert.equal(submitted, true);
      polls++;
      if (polls === 1) return { data: [] };
      if (process.env.SCENARIO === 'http-error') return { error: { message: 'database is locked' } };
      const receipt = { worker_id: 'worker-0001', outcome: 'completed', summary: 'Done', result_json: '{}' };
      return { data: [{ info: { role: 'assistant', time: { completed: 1 }, finish: process.env.SCENARIO === 'truncated' ? 'length' : 'stop',
        error: process.env.SCENARIO === 'provider-error' ? { name: 'APIError', message: 'provider failed' } : undefined,
        cost: 0.01, tokens: { total: 42 } },
        parts: [{ type: 'text', text: process.env.SCENARIO === 'invalid-json' ? 'not json' : JSON.stringify(receipt) }]
      }] };
    }
  } } };
}
"""


@unittest.skipUnless(
    shutil.which("node"), "Node is required for OpenCode helper checks"
)
class OpenCodeHelper(unittest.TestCase):
    def test_async_completion_preserves_config_and_reports_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory) / "sdk.mjs"
            sdk.write_text(SDK)
            for scenario in [
                "success",
                "http-error",
                "provider-error",
                "invalid-json",
                "truncated",
            ]:
                with self.subTest(scenario=scenario):
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
                            "opencode-go/deepseek-v4.1-flash",
                            "--agent",
                            "plan",
                            "--worker-id",
                            "worker-0001",
                            "--prompt",
                            "Review only.",
                        ],
                        env={
                            **os.environ,
                            "SCENARIO": scenario,
                            "OPENCODE_CONFIG_CONTENT": '{"agent":{"plan":{"permission":{"edit":"deny"}}}}',
                        },
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    envelope = json.loads(result.stdout)
                    self.assertEqual(
                        envelope["status"],
                        "SUCCESS" if scenario == "success" else "ERROR",
                    )
                    if scenario == "http-error":
                        self.assertIn("database is locked", envelope["error"])
                    if scenario == "success":
                        self.assertEqual(
                            envelope["usage"], {"cost": 0.01, "tokens": 42}
                        )


if __name__ == "__main__":
    unittest.main()
