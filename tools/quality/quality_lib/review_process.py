"""Run a visible reviewer; a pipe-bound supervisor cleans up even on caller SIGKILL."""

import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

from .config import SetupError

MODEL = "gpt-5.6-luna"
TIMEOUT = 900


def terminate(signum, frame):
    raise SystemExit(128 + signum)


def run_review(root, directory, prompt, timeout=TIMEOUT, lock_fd=None):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    (directory / "prompt.txt").write_text(prompt)
    report = directory / "report.md"
    report.unlink(missing_ok=True)
    print(f"Review running visibly ({MODEL}, max). Artifacts: {directory}", flush=True)
    environment = dict(os.environ, QUALITY_REVIEW_CHILD="1")
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "quality_lib.review_process",
            str(directory),
            str(timeout),
        ],
        cwd=root,
        env=environment,
        stdin=subprocess.PIPE,
        start_new_session=True,
        # Keep the session locked until cleanup finishes even if the caller is killed.
        pass_fds=() if lock_fd is None else (lock_fd,),
    )
    previous = {
        sig: signal.signal(sig, terminate) for sig in (signal.SIGTERM, signal.SIGINT)
    }
    started = time.monotonic()
    try:
        while True:
            try:
                process.wait(timeout=30)
                break
            except subprocess.TimeoutExpired:
                print(
                    f"Review still running ({int(time.monotonic() - started)}s).",
                    flush=True,
                )
    finally:
        # EOF is also delivered if this caller is killed without running finally.
        process.stdin.close()
        try:
            process.wait(timeout=5)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    if process.returncode == 124:
        raise SetupError(f"Review timed out after {timeout}s")
    if process.returncode or not report.is_file() or not report.read_text().strip():
        raise SetupError(
            f"Native review did not return a report (exit {process.returncode})"
        )
    return report


def signal_process(pid, sig):
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        pass


def kill_tree(pid):
    """Freeze each generation before finding its children, including new sessions."""
    owned = {pid}
    signal_process(pid, signal.SIGSTOP)
    try:
        while True:
            rows = subprocess.check_output(
                ["ps", "-axo", "pid=,ppid="], text=True, timeout=2
            )
            children = {
                child
                for line in rows.splitlines()
                for child, parent in [map(int, line.split())]
                if parent in owned and child not in owned
            }
            if not children:
                break
            owned.update(children)
            for child in children:
                signal_process(child, signal.SIGSTOP)
    finally:
        for child in owned:
            signal_process(child, signal.SIGKILL)
        # Covers group members even if the original reviewer already exited.
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def supervise(directory, timeout):
    command = [
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "--model",
        MODEL,
        "-c",
        f'review_model="{MODEL}"',
        "-c",
        'model_reasoning_effort="max"',
        "--disable",
        "memories",
        "--ephemeral",
        "--json",
        "--output-last-message",
        str(directory / "report.md"),
        "review",
        "-",
    ]
    with (
        (directory / "prompt.txt").open() as prompt,
        (directory / "events.jsonl").open("w") as events,
        (directory / "stderr.log").open("w") as errors,
    ):
        process = subprocess.Popen(
            command,
            stdin=prompt,
            stdout=events,
            stderr=errors,
            start_new_session=True,
            close_fds=True,
        )
        signal.signal(signal.SIGTERM, terminate)
        signal.signal(signal.SIGINT, terminate)
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if select.select([sys.stdin], [], [], 0.1)[0] and not os.read(0, 1):
                    return 130
                if time.monotonic() >= deadline:
                    return 124
            return process.returncode
        finally:
            try:
                kill_tree(process.pid)
            finally:
                process.wait()


if __name__ == "__main__":
    try:
        raise SystemExit(supervise(Path(sys.argv[1]), float(sys.argv[2])))
    except OSError as exc:
        print(f"Cannot start native review: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
