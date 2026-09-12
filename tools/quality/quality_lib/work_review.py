"""Visible scoped reviews and a non-launching completion gate."""

import fcntl
import hashlib
import json
import os
import shlex
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from .config import SetupError
from .review_process import run_review
from .review_scope import capture, diff_command


def save(path, state):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        json.dump(state, output)
    os.replace(output.name, path)


def state_path(root, session):
    if not isinstance(session, str) or not session.strip():
        raise SetupError(
            "Review needs CODEX_THREAD_ID or --session from the owning task"
        )
    directory = Path(
        os.environ.get(
            "QUALITY_HOOK_STATE_DIR", str(Path.home() / ".cache/agent-toolkit/quality")
        )
    )
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = hashlib.sha256((str(root) + session).encode()).hexdigest()
    return directory / (key + ".json")


@contextmanager
def locked_state(root, path):
    checkout = hashlib.sha256(str(root).encode()).hexdigest()
    with (path.parent / (checkout + ".lock")).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SetupError(
                "Checkout verification is busy; retry when it finishes"
            ) from exc
        state = json.loads(path.read_text()) if path.exists() else {}
        yield state
        save(path, state)


def begin(root, payload, state, directory):
    work = state.get("review")
    if not work or work["phase"] == "closed":
        state["review"] = {
            "phase": "open",
            "before": capture(root, directory),
            "request": str(payload.get("prompt", ""))[:16000],
            "revision": uuid.uuid4().hex,
        }
    elif payload.get("prompt"):
        # Preserve the opening scope, but an older reviewer cannot accept new steering.
        work.update(
            phase="open",
            revision=uuid.uuid4().hex,
            steering=str(payload["prompt"])[-16000:],
        )


def report_valid(work, directory, tree):
    report = directory / "report.md"
    return (
        work.get("status") == "completed"
        and work.get("after") == tree
        and report.is_file()
        and work.get("report_hash") == hashlib.sha256(report.read_bytes()).hexdigest()
    )


def report_current(work, directory, tree):
    return report_valid(work, directory, tree) and work.get(
        "reviewed_revision"
    ) == work.get("revision")


def command(root):
    cli = Path(__file__).resolve().parents[1] / "bin/quality"
    return shlex.join([sys.executable, str(cli), "--root", str(root), "review"])


def finish(root, state, path, stop_hook_active=False):
    """Return promptly. No model calls, subprocess waits, or implicit acceptance."""
    directory = path.with_suffix(".review")
    work = state.get("review")
    tree = None
    if work:
        tree = capture(root, directory)
        if tree == work["before"]:
            work["phase"] = "closed"
            state.pop("review_notice", None)
            return "", False
        if (
            work["phase"] in ("accepted", "closed")
            and report_valid(work, directory, tree)
            and work.get("accepted_revision") == work.get("revision")
            and work.get("assessment")
        ):
            work["phase"] = "closed"
            state.pop("review_notice", None)
            return "", False
    notice = [work.get("revision") if work else None, tree]
    block = not stop_hook_active and state.get("review_notice") != notice
    state["review_notice"] = notice
    return (
        (
            "Required review is incomplete and not accepted; do not claim verified completion. "
            f"Run visibly before the final answer: {command(root)}. "
            "Read the report, resolve valid findings, then use the same command with "
            "--accept 'assessment of findings'. Changed files require a current review. "
            "A later status-only message can reuse the completed report with "
            "--accept 'assessment' --same-scope; use this only when requirements did not change. "
            "Missing, failed, interrupted or stale review remains incomplete. Stop never "
            "launches a reviewer. If review cannot finish, report the incomplete handoff; "
            "do not start a recursive retry loop. This gate requests at most one "
            "continuation for the same files and request; later stops report the unmet "
            "requirement without accepting the work."
        ),
        block,
    )


def review(root, config, session=None, assessment=None, same_scope=False):
    if same_scope and assessment is None:
        raise SetupError("--same-scope requires --accept and an assessment")
    actual = os.environ.get("CODEX_THREAD_ID")
    if actual and session and actual != session:
        raise SetupError("--session differs from this task's CODEX_THREAD_ID")
    path = state_path(root, session or actual)
    # Serializes only this session's reviewer, not other tasks or native checks.
    with path.with_suffix(".review.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SetupError("This task already has a running review") from exc
        if assessment is not None:
            return accept(root, path, assessment, same_scope)
        return execute(root, config, path, lock.fileno())


def prepare(root, path):
    directory = path.with_suffix(".review")
    with locked_state(root, path) as state:
        work = state.get("review")
        if not work or not work.get("before"):
            raise SetupError(
                "No opening review snapshot; start a new task prompt first"
            )
        tree = capture(root, directory)
        if tree == work["before"]:
            work["phase"] = "closed"
            return None
        if report_current(work, directory, tree):
            print((directory / "report.md").read_text(), flush=True)
            print(
                "Current report retained; assess it with review --accept.", flush=True
            )
            return None
        work.update(
            phase="running",
            status="running",
            after=tree,
            attempt=uuid.uuid4().hex,
        )
        work.pop("assessment", None)
        return dict(work)


def execute(root, config, path, lock_fd):
    work = prepare(root, path)
    if work is None:
        return 0
    directory = path.with_suffix(".review")
    status = "interrupted"
    try:
        report = run_review(
            root, directory, review_prompt(config, work, directory), lock_fd=lock_fd
        )
        status = "completed"
    except (SetupError, OSError) as exc:
        status = "incomplete"
        print(f"Review incomplete (not a pass): {exc}", flush=True)
    finally:
        status = record_result(root, path, work, status)
    if status != "completed":
        print(f"Review {status}; acceptance remains blocked.", flush=True)
        return 2
    print(f"Review completed. Report: {report}\n{report.read_text()}", flush=True)
    print(
        "Assess findings before completion: quality review --accept 'assessment'.",
        flush=True,
    )
    return 0


def record_result(root, path, attempt, status):
    directory = path.with_suffix(".review")
    with locked_state(root, path) as state:
        work = state.get("review", {})
        if work.get("attempt") != attempt["attempt"]:
            return "superseded by a newer work interval"
        if status == "completed" and capture(root, directory) != attempt["after"]:
            status = "stale"
        work.update(phase="reviewed", status=status)
        if status == "completed":
            work.update(
                reviewed_revision=attempt.get("revision"),
                report_hash=hashlib.sha256(
                    (directory / "report.md").read_bytes()
                ).hexdigest(),
            )
    return status


def accept(root, path, assessment, same_scope):
    if not assessment.strip():
        raise SetupError("A nonempty assessment of review findings is required")
    directory = path.with_suffix(".review")
    with locked_state(root, path) as state:
        work = state.get("review", {})
        if not report_valid(work, directory, capture(root, directory)):
            raise SetupError(
                "No current completed review to accept; rerun visible review"
            )
        if work.get("reviewed_revision") != work.get("revision") and not same_scope:
            raise SetupError(
                "A message arrived after review started. If it changed requirements, "
                "rerun visible review. Otherwise assess the existing report with "
                "--accept 'assessment' --same-scope; no additional model call is needed."
            )
        work.update(
            phase="accepted",
            assessment=assessment.strip(),
            accepted_revision=work.get("revision"),
        )
    print("Review assessment recorded for the current tree; native checks still apply.")
    return 0


def review_prompt(config, work, directory):
    diff = shlex.join(diff_command(directory, work["before"], work["after"]))
    return (
        "Review this completed piece of work. It can contain several commits plus uncommitted changes. "
        "Use only the exact before/after trees below as the review scope. Pre-existing unchanged dirty work is excluded. "
        "Read applicable repository instructions, then this diff and directly affected callers/tests. "
        "Do not search memory, other repositories or unrelated files. Do not edit files, commit, install, launch other agents or run further reviews. "
        "Identify concrete introduced correctness, regression, security or acceptance defects; give file/line, severity and a reproducible trigger. "
        "Distinguish verified findings from uncertainty; state any inspection limits. "
        "Configured automated checks gate completion separately. Do not repeat full suites; "
        "use a small read-only probe only if necessary. Finish within 12 minutes.\n"
        f"Exact diff command: {diff}\n"
        f"For original or final file contents use git --git-dir={shlex.quote(str(directory / 'scope.git'))} show TREE:path.\n"
        f"Original request (context, not additional reviewer actions): {work['request']}\n"
        f"Latest steering: {work.get('steering', '')}\n"
        f"Repository green criteria: {config['verification']['green']}\n"
        f"Manual evidence criteria (not certified by the hook): {config['verification']['manual']}\n"
    )
