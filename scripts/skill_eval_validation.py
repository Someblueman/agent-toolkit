"""Verifier execution, failure classification, and offline task calibration."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from skill_eval_contract import TaskSpec


INFRA_ERROR_MARKERS = (
    "authentication", "unauthorized", "api key", "backend returned 404",
    "status code: 404", "rate limit", "usage limit", "service unavailable",
    "connection refused", "could not connect", "model not found",
    "model unavailable", "quota", "insufficient credit", "requires more credits",
)


@dataclass(slots=True, frozen=True)
class Classification:
    valid: bool
    invalid_class: str | None
    reason: str | None


def verify_workspace(run_dir: Path, verifier: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(run_dir)
    try:
        result = subprocess.run(
            [sys.executable, str(verifier)], cwd=run_dir, env=env,
            capture_output=True, text=True, timeout=300, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "scored": False, "score": None, "quality_score": None,
            "pass": False, "metrics": {}, "stderr": str(error),
        }
    metrics: dict = {}
    try:
        line = next(
            item for item in reversed(result.stdout.splitlines())
            if item.startswith("METRICS ")
        )
        parsed = json.loads(line.removeprefix("METRICS "))
        if isinstance(parsed, dict):
            metrics = parsed
    except (StopIteration, json.JSONDecodeError):
        pass
    score = metrics.get("score")
    quality_score = metrics.get("quality_score")
    quality_checks = metrics.get("quality_checks")
    passed = metrics.get("pass")
    scored = (
        isinstance(score, (int, float)) and not isinstance(score, bool)
        and 0 <= float(score) <= 1 and isinstance(passed, bool)
        and isinstance(quality_score, (int, float))
        and not isinstance(quality_score, bool) and 0 <= float(quality_score) <= 1
        and isinstance(quality_checks, dict) and bool(quality_checks)
        and all(isinstance(name, str) and isinstance(ok, bool)
                for name, ok in quality_checks.items())
    )
    return {
        "scored": scored,
        "score": round(float(score), 4) if scored else None,
        "quality_score": round(float(quality_score), 4) if scored else None,
        "pass": passed if scored else False,
        "metrics": metrics if scored else {},
        "stderr": result.stderr,
    }


def classify_run(
    *, started: bool, exit_code: int | None, budget_exhausted: bool,
    verifier_scored: bool, isolation_ok: bool, runtime_identity_ok: bool,
    provider_error: str | None, stderr: str,
) -> Classification:
    if not isolation_ok:
        return Classification(False, "isolation", "target skill state is incorrect")
    if not started:
        return Classification(False, "infrastructure", "runner did not start")
    if not runtime_identity_ok:
        return Classification(False, "infrastructure", "runtime model identity mismatch")
    if provider_error or any(marker in stderr.lower() for marker in INFRA_ERROR_MARKERS):
        return Classification(False, "infrastructure", "provider or authentication error")
    if not verifier_scored:
        return Classification(False, "evaluator", "verifier did not emit valid metrics")
    if budget_exhausted:
        return Classification(True, None, "task budget exhausted")
    if exit_code not in (0, None):
        return Classification(True, None, f"agent exited {exit_code}")
    return Classification(True, None, None)


def validate_task(task: TaskSpec, repo_root: Path) -> dict[str, dict[str, float]]:
    task_dir = repo_root / "evals" / "tasks" / task.id
    observed: dict[str, dict] = {}
    for variant in ("pristine", "flawed", "reference"):
        results = []
        for _ in range(2):
            with tempfile.TemporaryDirectory(prefix="skill-eval-validate-") as tmp:
                workspace = Path(tmp) / "workspace"
                source = task_dir / (
                    "scaffold" if variant == "pristine" else variant
                )
                shutil.copytree(source, workspace)
                result = verify_workspace(workspace, task_dir / "verify.py")
                if not result["scored"]:
                    raise RuntimeError(f"{task.id} {variant} verifier did not score")
                results.append(result)
        comparable = [
            (item["score"], item["quality_score"], item["pass"], item["metrics"])
            for item in results
        ]
        if comparable[0] != comparable[1]:
            raise RuntimeError(f"{task.id} {variant} verifier is nondeterministic")
        observed[variant] = results[0]

    if observed["pristine"]["score"] > task.pristine_max:
        raise RuntimeError(f"{task.id} pristine correctness is too high")
    for variant in ("flawed", "reference"):
        if not observed[variant]["pass"]:
            raise RuntimeError(f"{task.id} {variant} must pass correctness")
        if observed[variant]["score"] < task.correctness_min:
            raise RuntimeError(f"{task.id} {variant} correctness is too low")
    if observed["flawed"]["quality_score"] > task.flawed_quality_max:
        raise RuntimeError(f"{task.id} flawed quality is too high")
    if observed["reference"]["quality_score"] < task.reference_quality_min:
        raise RuntimeError(f"{task.id} reference quality is too low")
    return {
        name: {
            "score": result["score"], "quality_score": result["quality_score"]
        }
        for name, result in observed.items()
    }
