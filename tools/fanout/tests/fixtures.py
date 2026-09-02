"""Shared test fixtures and helpers for tools/fanout test suite."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
TOOL_ROOT = TESTS_DIR.parent
FANOUT_BIN = TOOL_ROOT / "bin" / "fanout"
SCHEMA_PATH = TOOL_ROOT / "schemas" / "worker-result.schema.json"
OPENCODE_HELPER_PATH = TOOL_ROOT / "lib" / "opencode_worker.mjs"


def load_fanout_module() -> types.ModuleType:
    """Dynamically load the fanout executable CLI as a Python module."""
    if not FANOUT_BIN.exists():
        raise FileNotFoundError(f"fanout binary not found at {FANOUT_BIN}")
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("fanout", str(FANOUT_BIN))
    spec = importlib.util.spec_from_loader("fanout", loader)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec for {FANOUT_BIN}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["fanout"] = module
    loader.exec_module(module)
    return module


def create_fake_agy(target_path: Path) -> Path:
    """Create an executable mock agy script."""
    script = f"#!{sys.executable}\n" + textwrap.dedent("""\
        import json
        import os
        import re
        import sys
        import time

        mode = os.environ.get("FAKE_AGY_MODE", "success")
        prompt = ""
        for arg in sys.argv:
            if arg.startswith("--print="):
                prompt = arg[8:]
                break

        match = re.search(r"worker-\\d{4}", prompt)
        worker_id = match.group(0) if match else "worker-0001"

        pid_path = os.environ.get("FAKE_AGY_PID_PATH")
        if pid_path:
            if os.path.isdir(pid_path):
                with open(os.path.join(pid_path, f"{worker_id}.pid"), "w") as f:
                    f.write(str(os.getpid()))
            else:
                with open(pid_path, "w") as f:
                    f.write(str(os.getpid()))

        state_dir = os.environ.get("FAKE_AGY_STATE_DIR")
        attempt = 1
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)
            state_path = os.path.join(state_dir, worker_id)
            try:
                with open(state_path, "r") as f:
                    attempt = int(f.read().strip()) + 1
            except (FileNotFoundError, ValueError):
                attempt = 1
            with open(state_path, "w") as f:
                f.write(str(attempt))

        delay = float(os.environ.get("FAKE_AGY_DELAY", "0"))
        if delay > 0:
            time.sleep(delay)

        if mode == "retry_success":
            if attempt == 1:
                time.sleep(30)
        if mode == "hang":
            time.sleep(30)
        if mode == "malformed":
            print("not-json-content")
            sys.exit(0)
        if mode == "oversized":
            size = int(os.environ.get("FAKE_AGY_OVERSIZED_BYTES", "4096"))
            print("x" * size)
            sys.exit(0)
        if mode == "nonzero":
            sys.stderr.write("provider failed\\n")
            sys.exit(int(os.environ.get("FAKE_AGY_EXIT_CODE", "7")))
        if mode == "partial" and worker_id == "worker-0002":
            sys.stderr.write("partial worker failure\\n")
            sys.exit(7)

        result = {
            "worker_id": worker_id,
            "summary": f"Completed {worker_id}",
            "findings": ["bounded finding 1", "bounded finding 2"],
            "uncertainties": [],
        }
        envelope = {
            "status": "SUCCESS",
            "structured_output": result,
            "duration_seconds": 0.05,
            "num_turns": 1,
            "usage": {"total_tokens": 150},
        }
        print(json.dumps(envelope))
    """)
    target_path.write_text(script, encoding="utf-8")
    target_path.chmod(0o755)
    return target_path


def create_fake_node(target_path: Path) -> Path:
    """Create an executable mock node script handling opencode worker invocations."""
    script = f"#!{sys.executable}\n" + textwrap.dedent("""\
        import json
        import os
        import sys
        import time

        mode = os.environ.get("FAKE_OPENCODE_MODE", "success")

        def get_arg(name: str, default: str = "") -> str:
            if name in sys.argv:
                idx = sys.argv.index(name)
                if idx + 1 < len(sys.argv):
                    return sys.argv[idx + 1]
            return default

        worker_id = get_arg("--worker-id", "worker-0001")
        agent = get_arg("--agent", "plan")

        pid_path = os.environ.get("FAKE_OPENCODE_PID_PATH")
        if pid_path:
            if os.path.isdir(pid_path):
                with open(os.path.join(pid_path, f"{worker_id}.pid"), "w") as f:
                    f.write(str(os.getpid()))
            else:
                with open(pid_path, "w") as f:
                    f.write(str(os.getpid()))

        delay = float(os.environ.get("FAKE_OPENCODE_DELAY", "0"))
        if delay > 0:
            time.sleep(delay)

        if mode == "hang":
            time.sleep(30)
        if mode == "malformed":
            print("not-json-content")
            sys.exit(0)
        if mode == "oversized":
            size = int(os.environ.get("FAKE_OPENCODE_OVERSIZED_BYTES", "4096"))
            print("x" * size)
            sys.exit(0)
        if mode == "nonzero":
            sys.stderr.write("helper failed\\n")
            sys.exit(int(os.environ.get("FAKE_OPENCODE_EXIT_CODE", "7")))

        outcome = "completed"
        if mode == "blocked":
            outcome = "blocked"
        elif mode == "failed":
            outcome = "failed"

        receipt_worker_id = worker_id
        if mode == "invalid":
            receipt_worker_id = "wrong-worker-id"

        payload_str = json.dumps({
            "kind": "task-specific",
            "selected_agent": agent,
            "recommendations": ["OpenCode recommendation"],
        })
        if mode == "bad_payload":
            payload_str = "not-json-string"

        receipt = {
            "worker_id": receipt_worker_id,
            "outcome": outcome,
            "summary": f"Completed {worker_id}",
            "result_json": payload_str,
        }

        envelope = {
            "status": "SUCCESS",
            "structured_output": receipt,
            "usage": {"tokens": {"total": 42}, "cost": 0.01},
        }
        print(json.dumps(envelope))
    """)
    target_path.write_text(script, encoding="utf-8")
    target_path.chmod(0o755)
    return target_path


def create_fake_opencode(target_path: Path) -> Path:
    """Create an executable mock opencode binary."""
    target_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    target_path.chmod(0o755)
    return target_path


def create_fake_sdk(target_path: Path) -> Path:
    """Create a mock @opencode-ai/sdk dist index.js."""
    target_path.write_text("export {};\n", encoding="utf-8")
    return target_path


class BaseFanoutTestCase(unittest.TestCase):
    """Base test case providing isolated temp dir and mock harness fixtures."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.prompt = self.root / "prompt.md"
        self.prompt.write_text("Inspect the bounded task and report structured findings.\n", encoding="utf-8")

        self.fake_agy = create_fake_agy(self.root / "fake-agy")
        self.fake_opencode = create_fake_opencode(self.root / "fake-opencode")
        self.fake_sdk = create_fake_sdk(self.root / "index.js")
        self.fake_node = create_fake_node(self.root / "fake-node")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_fanout(
        self,
        mode: str = "success",
        *,
        workers: int = 1,
        concurrency: int = 1,
        timeout: float = 3.0,
        max_output: int = 1024,
        min_results: int | None = None,
        retries: int = 1,
        harness: str = "agy",
        agent: str = "plan",
        model: str | None = None,
        working_directory: Path | None = None,
        prompt_file: Path | None = None,
        output_dir: Path | None = None,
        extra_args: list[str] | None = None,
        env_vars: dict[str, str] | None = None,
        timeout_process: float = 10.0,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, Any] | None]:
        output = output_dir or (self.root / f"run-{harness}-{mode}-{workers}-{concurrency}")
        prompt = prompt_file or self.prompt
        work_dir = working_directory or self.root

        command = [
            sys.executable,
            str(FANOUT_BIN),
            str(prompt),
            "--harness",
            harness,
            "--workers",
            str(workers),
            "--concurrency",
            str(concurrency),
            "--timeout-seconds",
            str(timeout),
            "--max-output-bytes",
            str(max_output),
            "--output",
            str(output),
            "--working-directory",
            str(work_dir),
        ]
        if model is not None:
            command.extend(["--model", model])
        if harness == "agy":
            command.extend(["--agy", str(self.fake_agy)])
            command.extend(["--agy-retries", str(retries)])
        else:
            command.extend(["--opencode", str(self.fake_opencode)])
            command.extend(["--node", str(self.fake_node)])
            command.extend(["--opencode-sdk", str(self.fake_sdk)])
            command.extend(["--agent", agent])

        if min_results is not None:
            command.extend(["--min-results", str(min_results)])
        if extra_args:
            command.extend(extra_args)

        environment = os.environ.copy()
        environment["FAKE_AGY_MODE"] = mode
        environment["FAKE_OPENCODE_MODE"] = mode

        state_dir = self.root / f"state-{mode}-{workers}-{concurrency}"
        state_dir.mkdir(parents=True, exist_ok=True)
        environment["FAKE_AGY_STATE_DIR"] = str(state_dir)

        if env_vars:
            environment.update(env_vars)

        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            env=environment,
            timeout=timeout_process,
        )

        packet: dict[str, Any] | None = None
        packet_path = output / "packet.json"
        if packet_path.is_file():
            try:
                packet = json.loads(packet_path.read_text(encoding="utf-8"))
            except Exception:
                packet = None

        return completed, packet
