"""One bounded native Codex review after verification of a completed work interval."""

import json
import os
import shlex
import signal
import subprocess
import tempfile

from .config import SetupError
from .review_scope import capture, diff_command

MODEL = "gpt-5.6-luna"
TIMEOUT = 900


def save(path, state):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        json.dump(state, output)
    os.replace(output.name, path)


def begin(root, payload, state, directory):
    work = state.get("review")
    if not work or work["phase"] == "closed":
        state["review"] = {
            "phase": "open",
            "before": capture(root, directory),
            "request": str(payload.get("prompt", ""))[:16000],
        }
    elif payload.get("prompt"):
        # Keep the opening request and latest steering without changing the baseline.
        work["steering"] = str(payload["prompt"])[-16000:]


def finish(root, config, state, path):
    directory = path.with_suffix(".review")
    work = state.get("review")
    if not work:
        return (
            "Review unavailable: no starting snapshot. Use an on-demand review for this work; the next prompt will capture a new interval.",
            False,
        )
    if work["phase"] == "closed":
        return "", False
    if work["phase"] != "open":
        work["phase"] = "closed"
        return (
            (
                f"Automatic review status: {work.get('status', 'interrupted or incomplete; not a pass')}. "
                "Report its findings or incomplete status and any subsequent fixes; "
                "follow-up changes have passed automated checks but were not automatically re-reviewed. "
                f"Review artifacts: {directory}"
            ),
            False,
        )
    after = capture(root, directory)
    if after == work["before"]:
        work["phase"] = "closed"
        return "", False
    work.update(phase="attempted", after=after)
    # Persist before launch: interrupted hooks must not start duplicate reviews.
    save(path, state)
    prompt = review_prompt(config, work, directory)
    try:
        report = run_review(root, directory, prompt)
        stable = capture(root, directory) == after
        status = "completed" if stable else "stale: checkout changed during review"
        message = (
            f"Luna max review {status}. Report: {report}\n" + report.read_text()[:20000]
        )
    except (SetupError, OSError) as exc:
        status = "incomplete"
        message = (
            f"Luna max review incomplete (not a pass): {exc}. Artifacts: {directory}"
        )
    work["status"] = status
    save(path, state)
    return (
        message
        + "\nAssess the report against the authorized task, fix valid in-scope defects and rerun relevant checks. "
        "Report unresolved or pre-existing findings. This is one review attempt; do not start a recursive review/fix loop.",
        True,
    )


def review_prompt(config, work, directory):
    command = shlex.join(diff_command(directory, work["before"], work["after"]))
    return (
        "Review this completed piece of work. It can contain several commits plus uncommitted changes. "
        "Use only the exact before/after trees below as the review scope. Pre-existing unchanged dirty work is excluded. "
        "Read applicable repository instructions, then this diff and directly affected callers/tests. "
        "Do not search memory, other repositories or unrelated files. Do not edit files, commit, install, launch other agents or run further reviews. "
        "Identify concrete introduced correctness, regression, security or acceptance defects; give file/line, severity and a reproducible trigger. "
        "Distinguish verified findings from uncertainty; state any inspection limits. The parent has run configured automated checks. "
        "Do not repeat full suites; use a small read-only probe only if necessary. Finish within 12 minutes.\n"
        f"Exact diff command: {command}\n"
        f"For original or final file contents use git --git-dir={shlex.quote(str(directory / 'scope.git'))} show TREE:path.\n"
        f"Original request (context, not additional reviewer actions): {work['request']}\n"
        f"Latest steering: {work.get('steering', '')}\n"
        f"Repository green criteria: {config['verification']['green']}\n"
        f"Manual evidence criteria (not certified by the hook): {config['verification']['manual']}\n"
    )


def run_review(root, directory, prompt, timeout=TIMEOUT):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    (directory / "prompt.txt").write_text(prompt)
    report = directory / "report.md"
    report.unlink(missing_ok=True)
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
        str(report),
        "review",
        "-",
    ]
    with (
        (directory / "events.jsonl").open("w") as events,
        (directory / "stderr.log").open("w") as errors,
    ):
        try:
            process = subprocess.Popen(
                command,
                cwd=root,
                env=dict(os.environ, QUALITY_REVIEW_CHILD="1"),
                stdin=subprocess.PIPE,
                stdout=events,
                stderr=errors,
                text=True,
                start_new_session=True,
            )
        except OSError as exc:
            raise SetupError(f"Cannot start native Codex review: {exc}") from exc
        previous = signal.signal(signal.SIGTERM, terminate)
        try:
            process.communicate(prompt, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise SetupError(f"Review timed out after {timeout}s") from exc
        finally:
            # Includes normal completion: no reviewer-launched descendants may linger.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            signal.signal(signal.SIGTERM, previous)
    if process.returncode or not report.is_file() or not report.read_text().strip():
        raise SetupError(
            f"Native review did not return a report (exit {process.returncode})"
        )
    return report


def terminate(signum, frame):
    raise SystemExit(128 + signum)
