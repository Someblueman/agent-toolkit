#!/usr/bin/env python3
"""Native, paired evaluation of repository skills across agent harnesses."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from skill_eval_contract import (
    SuiteSpec,
    TaskSpec,
    directory_fingerprint,
    load_suite,
    package_matches,
    runtime_fingerprint,
    skill_fingerprint,
    task_fingerprint,
)
from skill_eval_runners import (
    build_command,
    detect_activation,
    inspect_runtime,
    prepare_runner,
    run_agent,
    runner_version,
)
from skill_eval_telemetry import trace_metrics, workspace_metrics
from skill_eval_validation import classify_run, validate_task, verify_workspace

REPO = Path(__file__).resolve().parent.parent
EVALS = REPO / "evals"
RESULTS = EVALS / "results"
HISTORY = EVALS / "history"
PROMPT_SUFFIX = (
    "\n\nWork directly in the current directory. Make the requested change, "
    "then stop. Do not ask questions.\n"
)
def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(message: str) -> None:
    print(f"[skill-eval] {message}", flush=True)


def _save_artifacts(
    artifact_dir: Path, stdout: str, stderr: str, verify_stderr: str,
    run_dir: Path,
) -> dict[str, str]:
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "stdout.jsonl").write_text(stdout)
    (artifact_dir / "stderr.log").write_text(stderr)
    (artifact_dir / "verifier.stderr.log").write_text(verify_stderr)
    shutil.copytree(run_dir, artifact_dir / "workspace")
    return {name: str(artifact_dir / target) for name, target in {
        "stdout": "stdout.jsonl", "stderr": "stderr.log",
        "verifier_stderr": "verifier.stderr.log", "workspace": "workspace",
    }.items()}


def one_run(
    *, batch: str, suite: SuiteSpec, task: TaskSpec, runner: str, arm: str,
    sample: int, pair_id: str, timeout: int, concurrency: int,
    purpose: str, version: str | None, repo_root: Path, results_root: Path,
) -> dict:
    task_dir = repo_root / "evals" / "tasks" / task.id
    skill_dir = repo_root / "skills" / suite.skill
    spec = suite.runners[runner]
    started_at = utcnow()
    with tempfile.TemporaryDirectory(prefix="skill-eval-") as temporary:
        base = Path(temporary)
        run_dir = base / "workspace"
        shutil.copytree(task_dir / "scaffold", run_dir)
        prepared = prepare_runner(runner, base / "runner", arm, skill_dir, suite.skill)
        command = build_command(
            runner, run_dir, timeout, spec.model, spec.thinking,
            prepared.command_args,
        )
        result = run_agent(
            command, prepared.env, (task_dir / "task.md").read_text() + PROMPT_SUFFIX,
            timeout,
        )
        workspace = workspace_metrics(task_dir / "scaffold", run_dir)
        verified = verify_workspace(run_dir, task_dir / "verify.py")
        package_present = prepared.skill_path.is_dir()
        installed_matches = package_matches(skill_dir, prepared.skill_path)
        isolation_ok = installed_matches if arm == "with" else not package_present
        runtime = inspect_runtime(runner, result.stdout, spec.model)
        trace = trace_metrics(runner, result.stdout)
        classification = classify_run(
            started=result.started, exit_code=result.exit_code,
            budget_exhausted=result.budget_exhausted,
            verifier_scored=verified["scored"], isolation_ok=isolation_ok,
            runtime_identity_ok=runtime.identity_ok,
            provider_error=runtime.provider_error, stderr=result.stderr,
        )
        artifact_dir = (
            results_root / batch / "artifacts" / task.id / runner / arm
            / f"{sample:03d}"
        )
        artifacts = _save_artifacts(
            artifact_dir, result.stdout, result.stderr, verified["stderr"], run_dir
        )
        command_record = [
            token.replace(str(run_dir), "$WORKSPACE").replace(str(base), "$RUN_ROOT")
            for token in command
        ]
        installed_hash = (
            directory_fingerprint(prepared.skill_path) if package_present else None
        )
    record = {
        "schema_version": 2, "batch": batch, "series": suite.series,
        "purpose": purpose, "skill": suite.skill, "task": task.id,
        "task_family": task.family, "runner": runner, "runner_version": version,
        "model": spec.model,
        "thinking": spec.thinking, "arm": arm, "sample": sample,
        "pair_id": pair_id, "started_at": started_at, "finished_at": utcnow(),
        "task_fingerprint": task_fingerprint(task, repo_root),
        "skill_fingerprint": skill_fingerprint(suite.skill, repo_root),
        "runtime_fingerprint": runtime_fingerprint(
            runner, version, suite, timeout, concurrency, repo_root
        ),
        "command": command_record, "environment": prepared.env_contract,
        "skill_available": package_present,
        "skill_package_matches": installed_matches if arm == "with" else None,
        "installed_package_fingerprint": installed_hash,
        "activation": detect_activation(runner, result.stdout, suite.skill),
        "actual_model": runtime.actual_model,
        "observed_models": list(runtime.observed_models),
        "model_fallback_applied": runtime.fallback_applied,
        "runtime_identity_ok": runtime.identity_ok,
        "provider_error": runtime.provider_error,
        "input_tokens": runtime.input_tokens,
        "output_tokens": runtime.output_tokens,
        "cached_input_tokens": runtime.cached_input_tokens,
        "total_tokens": runtime.total_tokens,
        "cost_usd": runtime.cost_usd,
        **trace,
        **workspace,
        "task_started": runtime.task_started,
        "runner_started": result.started, "runner_exit_code": result.exit_code,
        "budget_exhausted": result.budget_exhausted,
        "duration_s": result.duration_s, "valid": classification.valid,
        "invalid_class": classification.invalid_class,
        "invalid_reason": classification.reason, "score": verified["score"],
        "quality_score": verified["quality_score"], "pass": verified["pass"],
        "metrics": verified["metrics"],
        "ceiling_threshold": suite.ceiling_threshold,
        "quality_effect": suite.quality_effect,
        "efficiency_effect": suite.efficiency_effect,
        "instability_threshold": suite.instability_threshold,
        "artifacts": artifacts,
    }
    record_path = (
        results_root / batch / "records" / task.id / runner / arm
        / f"{sample:03d}.json"
    )
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    label = "VALID" if record["valid"] else f"INVALID:{record['invalid_class']}"
    log(f"{pair_id} {arm}: {label}, score={record['score']}")
    return record


def _manifest(
    suite: SuiteSpec, tasks: tuple[TaskSpec, ...], runners: tuple[str, ...],
    samples: int, concurrency: int, batch: str, timeout: int, purpose: str,
    arms: tuple[str, ...], versions: dict[str, str | None], repo_root: Path,
) -> dict:
    try:
        suite_path = str(suite.source_path.relative_to(repo_root))
    except ValueError:
        suite_path = suite.source_path.name
    return {
        "schema_version": 2, "batch": batch, "series": suite.series,
        "purpose": purpose, "started_at": utcnow(), "suite": suite_path,
        "skill": suite.skill, "calibration_basis": suite.calibration_basis,
        "screen_samples": suite.screen_samples,
        "thresholds": {
            "ceiling": suite.ceiling_threshold,
            "quality_effect": suite.quality_effect,
            "efficiency_effect": suite.efficiency_effect,
            "instability": suite.instability_threshold,
        },
        "samples_per_arm": samples, "concurrency": concurrency,
        "timeout_seconds": timeout, "arms": list(arms),
        "tasks": [asdict(task) for task in tasks],
        "runners": {
            name: {**asdict(suite.runners[name]), "version": versions[name]}
            for name in runners
        },
        "fingerprints": {
            "skill": skill_fingerprint(suite.skill, repo_root),
            "tasks": {task.id: task_fingerprint(task, repo_root) for task in tasks},
            "runtimes": {name: runtime_fingerprint(
                name, versions[name], suite, timeout, concurrency, repo_root
            ) for name in runners},
        },
    }


def _sanitized_record(record: dict, results_root: Path) -> dict:
    clean = dict(record)
    clean.pop("provider_error", None)
    clean["artifacts"] = {
        name: str(Path(path).relative_to(results_root))
        for name, path in record.get("artifacts", {}).items()
    }
    return clean


def _write_history(
    manifest: dict, records: list[dict], repo_root: Path, results_root: Path,
) -> None:
    target = repo_root / "evals" / "history" / manifest["batch"]
    target.mkdir(parents=True, exist_ok=False)
    (target / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    lines = [json.dumps(_sanitized_record(record, results_root), sort_keys=True)
             for record in records]
    (target / "runs.jsonl").write_text("\n".join(lines) + "\n")


def run_batch(
    *, suite: SuiteSpec, tasks: tuple[TaskSpec, ...], runners: tuple[str, ...],
    samples: int, concurrency: int, batch: str, timeout: int,
    repo_root: Path = REPO, results_root: Path = RESULTS,
    purpose: str = "confirmatory",
    arms: tuple[str, ...] = ("with", "without"),
) -> list[dict]:
    """Run randomized adjacent arm pairs and return every completed record."""
    batch_dir = results_root / batch
    batch_dir.mkdir(parents=True, exist_ok=False)
    versions = {name: runner_version(name) for name in runners}
    manifest = _manifest(
        suite, tasks, runners, samples, concurrency, batch, timeout, purpose,
        arms, versions, repo_root
    )
    (batch_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    blocks = [(task, runner, sample) for task in tasks for runner in runners
              for sample in range(1, samples + 1)]

    def run_pair(task: TaskSpec, runner: str, sample: int) -> list[dict]:
        pair_id = f"{task.id}:{runner}:{sample:03d}"
        ordered_arms = list(arms)
        random.Random(f"{batch}:{pair_id}").shuffle(ordered_arms)
        return [one_run(
            batch=batch, suite=suite, task=task, runner=runner, arm=arm,
            sample=sample, pair_id=pair_id, timeout=timeout,
            concurrency=concurrency, purpose=purpose, repo_root=repo_root,
            results_root=results_root, version=versions[runner],
        ) for arm in ordered_arms]

    records: list[dict] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(run_pair, *block) for block in blocks]
        for future in as_completed(futures):
            records.extend(future.result())
    records.sort(key=lambda item: (
        item["task"], item["runner"], item["sample"], item["arm"]
    ))
    finished = {**manifest, "finished_at": utcnow(), "record_count": len(records)}
    (batch_dir / "manifest.json").write_text(
        json.dumps(finished, indent=2, sort_keys=True) + "\n"
    )
    _write_history(finished, records, repo_root, results_root)
    return records


def _select_tasks(suite: SuiteSpec, raw: str) -> tuple[TaskSpec, ...]:
    if raw == "all":
        return suite.tasks
    wanted = raw.split(",")
    by_id = {task.id: task for task in suite.tasks}
    unknown = set(wanted) - set(by_id)
    if unknown:
        raise ValueError(f"unknown task: {sorted(unknown)[0]}")
    return tuple(by_id[name] for name in wanted)


def _select_runners(suite: SuiteSpec, raw: str) -> tuple[str, ...]:
    wanted = tuple(suite.runners) if raw == "all" else tuple(raw.split(","))
    unknown = set(wanted) - set(suite.runners)
    if unknown:
        raise ValueError(f"runner not in suite: {sorted(unknown)[0]}")
    return wanted


def main() -> int:
    parser = argparse.ArgumentParser(prog="skill-eval")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--suite", type=Path, required=True)
    validate_parser.add_argument("--tasks", default="all")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--suite", type=Path, required=True)
    run_parser.add_argument("--tasks", default="all")
    run_parser.add_argument("--runners", default="all")
    run_parser.add_argument(
        "--purpose", choices=("validation", "screen", "confirmatory"),
        default="validation",
    )
    run_parser.add_argument("--batch")
    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--batch", required=True,
                               help="comma-separated native-v2 batch ids")
    args = parser.parse_args()

    if args.command == "report":
        from skill_eval_report import build_report
        batches = tuple(args.batch.split(","))
        (EVALS / "REPORT.md").write_text(build_report(batches, HISTORY))
        log(f"wrote evals/REPORT.md from {', '.join(batches)}")
        return 0

    suite = load_suite(args.suite)
    tasks = _select_tasks(suite, args.tasks)
    if args.command == "validate":
        for task in tasks:
            log(f"validated {task.id}: {validate_task(task, REPO)}")
        return 0

    runners = _select_runners(suite, args.runners)
    if args.purpose == "confirmatory" and (
        tasks != suite.tasks or runners != tuple(suite.runners)
    ):
        parser.error("confirmatory runs must use every frozen task and runner")
    if args.purpose == "confirmatory" and len(tasks) != 3:
        parser.error("a confirmatory suite requires exactly three frozen tasks")
    if args.purpose == "screen" and len(tasks) > 6:
        parser.error("screen at most six candidate tasks")
    samples = {
        "validation": 1,
        "screen": suite.screen_samples,
        "confirmatory": suite.samples,
    }[args.purpose]
    arms = ("without",) if args.purpose == "screen" else ("with", "without")
    batch = args.batch or (
        f"{suite.series}-{args.purpose}-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-"
        f"{uuid.uuid4().hex[:4]}"
    )
    concurrency = min(suite.concurrency, len(tasks) * len(runners) * samples)
    records = run_batch(
        suite=suite, tasks=tasks, runners=runners, samples=samples,
        concurrency=concurrency, batch=batch, timeout=suite.timeout_seconds,
        purpose=args.purpose, arms=arms,
    )
    from skill_eval_report import build_report
    (EVALS / "REPORT.md").write_text(build_report((batch,), HISTORY))
    invalid = sum(not record["valid"] for record in records)
    log(f"completed {len(records)} records ({invalid} invalid); wrote REPORT.md")
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
