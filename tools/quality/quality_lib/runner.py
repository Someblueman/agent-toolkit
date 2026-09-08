"""Execute exact tools; never download during doctor or check."""

import os
import re
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

from .config import SetupError, SnapshotChanged, fingerprint, inside, inventory, matches


def run(root, command, timeout=120):
    command = [a.replace("{root}", str(root)) for a in command]
    env = dict(
        os.environ,
        GOTOOLCHAIN="local",
        CARGO_NET_OFFLINE="true",
        UV_OFFLINE="1",
        npm_config_offline="true",
    )
    # Files avoid pipe deadlocks and unbounded in-memory output.
    with tempfile.TemporaryFile() as output:
        try:
            process = subprocess.Popen(
                command,
                cwd=root,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as exc:
            raise SetupError(f"Cannot launch {command[0]}: {exc}") from exc
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise SetupError(f"Timed out after {timeout}s: {command[0]}") from exc
        text = summarize_output(output, code)
    return code, text


def summarize_output(output, code):
    size = output.seek(0, os.SEEK_END)
    output.seek(0)
    if size <= 24000:
        return output.read().decode("utf-8", errors="replace")
    directory = Path.home() / ".cache/agent-toolkit/quality/reports"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        dir=directory, suffix=".log", delete=False
    ) as report:
        shutil.copyfileobj(output, report)
        path = report.name
    output.seek(0)
    head = output.read(6000).decode("utf-8", errors="replace")
    output.seek(-6000, os.SEEK_END)
    tail = output.read().decode("utf-8", errors="replace")
    sections = (
        [("Final output", tail), ("Initial output", head)]
        if code
        else [("Initial output", head), ("Final output", tail)]
    )
    return (
        f"Full command output: {path}\n[output excerpt; middle omitted]\n"
        + "\n".join(f"{title}:\n{body}" for title, body in sections)
    )


def doctor(root, config):
    messages = []
    for name, tool in config["tools"].items():
        code, text = run(root, tool["command"] + tool["version_args"], 20)
        version = re.escape(tool["version"])
        if code or not re.search(r"(?<![\w.])v?" + version + r"(?![\w.+-])", text):
            raise SetupError(
                f"{name}: expected version {tool['version']}; got {text.strip()}"
            )
        messages.append(f"{name}: {tool['version']}")
    files = inventory(root, config)
    messages.append(
        f"Source coverage: {len(files)} files; "
        + ", ".join(c["name"] for c in config["checks"])
    )
    return messages


def check(root, config, stage="full"):
    doctor(root, config)
    files = inventory(root, config)
    before = fingerprint(root, config, files)
    messages, summaries, failed = [], [], False
    for name in files:
        raw = inside(root, name).read_bytes()
        if b"\0" in raw:
            raise SetupError(f"Binary source file: {name}")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SetupError(f"Source must be UTF-8: {name}") from exc
        count = raw.count(b"\n") + int(bool(raw) and not raw.endswith(b"\n"))
        if count > config["size"]["limit"]:
            messages.append(
                f"SIZE {name}: {count} physical lines (limit {config['size']['limit']})"
            )
            failed |= config["size"]["mode"] == "error"
    for spec in config["checks"]:
        if stage == "fast" and spec["stage"] == "full":
            continue
        command = config["tools"][spec["tool"]]["command"] + spec["args"]
        selected = ["./" + f for f in files if matches(f, spec["patterns"])]
        if spec["files"]:
            command += selected
        code, output = run(root, command)
        # Native failure conventions differ (Cargo uses 101 for compiler/lint errors).
        if code != 0 and code not in spec["failure_codes"]:
            raise SetupError(f"{spec['name']} could not check (exit {code}):\n{output}")
        failed |= code != 0
        summaries.append(f"{'FAIL' if code else 'PASS'} {spec['name']}")
        detail = f"{spec['name']}:\n{output}".rstrip()
        messages.insert(0 if code else len(messages), detail)
    if before != fingerprint(root, config, inventory(root, config)):
        raise SnapshotChanged(
            "Sources/configuration changed during checks; rerun on a stable snapshot"
        )
    return int(failed), "\n".join(
        sorted(summaries, key=lambda s: not s.startswith("FAIL")) + messages
    )
