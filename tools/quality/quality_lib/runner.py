"""Execute exact tools; never download during doctor or check."""

import os
import re
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

from .config import SetupError, SnapshotChanged, inside, inventory, matches
from .incremental import snapshot


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


def doctor(root, config, *, automated=False):
    messages = []
    required = (
        {c["tool"] for c in config["checks"] if c["stage"] != "manual"}
        if automated
        else set(config["tools"])
    )
    for name in sorted(required):
        verify_tool(root, name, config["tools"][name])
        messages.append(f"{name}: {config['tools'][name]['version']}")
    return messages + coverage(root, config)


def coverage(root, config):
    files = inventory(root, config)
    messages = [f"Configured source inventory: {len(files)} files"]
    for stage in ("fast", "full", "manual"):
        names = [
            f"{c['name']} ({c.get('kind', 'unspecified')})"
            for c in config["checks"]
            if c["stage"] == stage
        ]
        label = "manual (excluded from hooks)" if stage == "manual" else stage
        messages.append(f"{label}: {', '.join(names) or 'none'}")
    behavioral = [
        p
        for c in config["checks"]
        if c["stage"] != "manual" and c.get("kind") in ("test", "invariant")
        for p in c["patterns"] + c.get("inputs", [])
    ]
    undeclared = [f for f in files if not matches(f, behavioral)]
    if undeclared:
        messages.append(
            f"No automated behavioral check declared for {len(undeclared)} files: "
            + ", ".join(undeclared[:10])
            + ". Configure kind=test/invariant and its actual inputs; this is not test coverage."
        )
    return messages


def verify_tool(root, name, tool):
    code, text = run(root, tool["command"] + tool["version_args"], 20)
    version = re.escape(tool["version"])
    if code or not re.search(r"(?<![\w.])v?" + version + r"(?![\w.+-])", text):
        raise SetupError(
            f"{name}: expected version {tool['version']}; got {text.strip()}"
        )


def execute_check(root, config, spec, selected):
    command = config["tools"][spec["tool"]]["command"] + spec["args"]
    if spec["files"]:
        paths = ["./" + name for name in selected]
        # clang and script adapters may have trailing compiler arguments.
        position = command.index("{files}") if "{files}" in command else len(command)
        command[position : position + int("{files}" in command)] = paths
    code, output = run(root, command)
    if code != 0 and code not in spec["failure_codes"]:
        raise SetupError(f"{spec['name']} could not check (exit {code}):\n{output}")
    size_messages = []
    size_files = set(selected)
    if spec.get("scope") == "translation-units":
        size_files.update(
            name
            for name in inventory(root, config)
            if matches(name, spec["patterns"])
            and Path(name).suffix not in (".c", ".cc", ".cpp", ".cxx")
        )
    for name in sorted(size_files):
        raw = inside(root, name).read_bytes()
        if b"\0" in raw:
            raise SetupError(f"Binary source file: {name}")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SetupError(f"Source must be UTF-8: {name}") from exc
        count = raw.count(b"\n") + int(bool(raw) and not raw.endswith(b"\n"))
        if count > config["size"]["limit"]:
            size_messages.append(
                f"SIZE {name}: {count} physical lines (limit {config['size']['limit']})"
            )
    failed = bool(code) or (bool(size_messages) and config["size"]["mode"] == "error")
    return int(failed), "\n".join([output, *size_messages]).strip()


def check(root, config, stage="full"):
    doctor(root, config)
    files = inventory(root, config)
    before = snapshot(root, config, include_manual=True)
    messages, summaries, failed = [], [], False
    for spec in config["checks"]:
        if stage == "fast" and spec["stage"] != "fast":
            continue
        selected = [f for f in files if matches(f, spec["patterns"])]
        if spec.get("scope") == "translation-units":
            selected = [
                f for f in selected if Path(f).suffix in (".c", ".cc", ".cpp", ".cxx")
            ]
        code, output = execute_check(root, config, spec, selected)
        failed |= bool(code)
        summaries.append(f"{'FAIL' if code else 'PASS'} {spec['name']}")
        messages.insert(0 if code else len(messages), f"{spec['name']}:\n{output}")
    if before != snapshot(root, config, include_manual=True):
        raise SnapshotChanged(
            "Sources/configuration changed during checks; rerun on a stable snapshot"
        )
    return int(failed), "\n".join(
        sorted(summaries, key=lambda s: not s.startswith("FAIL")) + messages
    )
