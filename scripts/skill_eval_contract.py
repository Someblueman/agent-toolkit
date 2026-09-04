"""Frozen suite schema and independent evaluation fingerprints."""

from __future__ import annotations

import hashlib
import json
import platform
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from skill_eval_runners import SUPPORTED_RUNNERS

REPO = Path(__file__).resolve().parent.parent
IGNORED_TREE_NAMES = {".DS_Store", "__pycache__"}


@dataclass(slots=True, frozen=True)
class RunnerSpec:
    model: str
    thinking: str


@dataclass(slots=True, frozen=True)
class TaskSpec:
    id: str
    family: str
    source: str
    pristine_max: float
    correctness_min: float
    flawed_quality_max: float
    reference_quality_min: float


@dataclass(slots=True, frozen=True)
class SuiteSpec:
    series: str
    skill: str
    calibration_basis: str
    screen_samples: int
    samples: int
    concurrency: int
    timeout_seconds: int
    ceiling_threshold: float
    quality_effect: float
    efficiency_effect: float
    instability_threshold: float
    runners: dict[str, RunnerSpec]
    tasks: tuple[TaskSpec, ...]
    source_path: Path


def _required(
    data: dict, key: str, kind: type | tuple[type, ...], context: str
):
    value = data.get(key)
    if not isinstance(value, kind):
        names = kind.__name__ if isinstance(kind, type) else "/".join(
            item.__name__ for item in kind
        )
        raise ValueError(f"{context}.{key} must be {names}")
    return value


def load_suite(path: Path, repo_root: Path = REPO) -> SuiteSpec:
    """Load and strictly validate the frozen experiment contract."""
    data = tomllib.loads(path.read_text())
    allowed = {
        "series", "skill", "screen_samples", "samples", "concurrency",
        "timeout_seconds", "ceiling_threshold", "quality_effect",
        "efficiency_effect", "instability_threshold", "runners", "tasks",
        "calibration_basis",
    }
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"unknown suite field: {sorted(unknown)[0]}")

    runners_raw = _required(data, "runners", dict, "suite")
    runners: dict[str, RunnerSpec] = {}
    for name, raw in runners_raw.items():
        if name not in SUPPORTED_RUNNERS:
            raise ValueError(f"unsupported runner in suite: {name}")
        if not isinstance(raw, dict) or set(raw) - {"model", "thinking"}:
            raise ValueError(f"invalid runner fields: {name}")
        runners[name] = RunnerSpec(
            model=_required(raw, "model", str, name),
            thinking=_required(raw, "thinking", str, name),
        )
    if len(runners) != 2:
        raise ValueError("the native-v2 proof requires exactly two runners")

    tasks_raw = _required(data, "tasks", list, "suite")
    tasks: list[TaskSpec] = []
    task_allowed = {
        "id", "family", "source", "pristine_max", "correctness_min",
        "flawed_quality_max", "reference_quality_min",
    }
    for raw in tasks_raw:
        if not isinstance(raw, dict):
            raise ValueError("each task must be a table")
        task_unknown = set(raw) - task_allowed
        if task_unknown:
            raise ValueError(f"unknown task field: {sorted(task_unknown)[0]}")
        task = TaskSpec(
            id=_required(raw, "id", str, "task"),
            family=_required(raw, "family", str, "task"),
            source=_required(raw, "source", str, "task"),
            pristine_max=float(_required(
                raw, "pristine_max", (int, float), "task"
            )),
            correctness_min=float(_required(
                raw, "correctness_min", (int, float), "task"
            )),
            flawed_quality_max=float(_required(
                raw, "flawed_quality_max", (int, float), "task"
            )),
            reference_quality_min=float(_required(
                raw, "reference_quality_min", (int, float), "task"
            )),
        )
        if not (0 <= task.pristine_max < task.correctness_min <= 1):
            raise ValueError(f"invalid correctness thresholds for task {task.id}")
        if not (
            0 <= task.flawed_quality_max < task.reference_quality_min <= 1
        ):
            raise ValueError(f"invalid quality thresholds for task {task.id}")
        task_dir = repo_root / "evals" / "tasks" / task.id
        for required in ("task.md", "verify.py", "scaffold", "flawed", "reference"):
            if not (task_dir / required).exists():
                raise ValueError(f"task {task.id} is missing {required}")
        tasks.append(task)
    if not tasks:
        raise ValueError("suite must contain at least one task")
    if len(tasks) > 6:
        raise ValueError("a screening suite may contain at most six tasks")
    task_ids = [task.id for task in tasks]
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("suite task ids must be unique")

    suite = SuiteSpec(
        series=_required(data, "series", str, "suite"),
        skill=_required(data, "skill", str, "suite"),
        calibration_basis=_required(data, "calibration_basis", str, "suite"),
        screen_samples=_required(data, "screen_samples", int, "suite"),
        samples=_required(data, "samples", int, "suite"),
        concurrency=_required(data, "concurrency", int, "suite"),
        timeout_seconds=_required(data, "timeout_seconds", int, "suite"),
        ceiling_threshold=float(_required(
            data, "ceiling_threshold", (int, float), "suite"
        )),
        quality_effect=float(_required(
            data, "quality_effect", (int, float), "suite"
        )),
        efficiency_effect=float(_required(
            data, "efficiency_effect", (int, float), "suite"
        )),
        instability_threshold=float(_required(
            data, "instability_threshold", (int, float), "suite"
        )),
        runners=runners,
        tasks=tuple(tasks),
        source_path=path.resolve(),
    )
    thresholds = (
        suite.ceiling_threshold, suite.quality_effect,
        suite.efficiency_effect, suite.instability_threshold,
    )
    if any(not 0 < value < 1 for value in thresholds):
        raise ValueError("suite thresholds must be between 0 and 1")
    if min(
        suite.screen_samples, suite.samples, suite.concurrency,
        suite.timeout_seconds,
    ) < 1:
        raise ValueError("sample counts, concurrency, and timeout must be positive")
    if not (repo_root / "skills" / suite.skill / "SKILL.md").is_file():
        raise ValueError(f"skill does not exist: {suite.skill}")
    return suite


def tree_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*")
        if path.is_file()
        and not any(part in IGNORED_TREE_NAMES for part in path.parts)
        and path.suffix != ".pyc"
    )


def _fingerprint_files(root: Path, files: list[Path], prefix: bytes = b"") -> str:
    digest = hashlib.sha256(prefix)
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def directory_fingerprint(root: Path) -> str:
    return _fingerprint_files(root, tree_files(root))


def task_fingerprint(task: TaskSpec, repo_root: Path = REPO) -> str:
    task_dir = repo_root / "evals" / "tasks" / task.id
    metadata = json.dumps(asdict(task), sort_keys=True).encode()
    return _fingerprint_files(task_dir, tree_files(task_dir), metadata)


def skill_fingerprint(skill: str, repo_root: Path = REPO) -> str:
    return directory_fingerprint(repo_root / "skills" / skill)


def runtime_fingerprint(
    runner: str,
    version: str | None,
    suite: SuiteSpec,
    timeout: int,
    concurrency: int,
    repo_root: Path = REPO,
) -> str:
    spec = suite.runners[runner]
    payload = json.dumps({
        "runner": runner, "runner_version": version,
        "model": spec.model, "thinking": spec.thinking,
        "timeout_seconds": timeout, "concurrency": concurrency,
        "series": suite.series,
        "ceiling_threshold": suite.ceiling_threshold,
        "quality_effect": suite.quality_effect,
        "efficiency_effect": suite.efficiency_effect,
        "instability_threshold": suite.instability_threshold,
        "operating_system": platform.platform(),
        "python_version": platform.python_version(),
    }, sort_keys=True).encode()
    files = [
        repo_root / "scripts" / "skill_eval.py",
        repo_root / "scripts" / "skill_eval_contract.py",
        repo_root / "scripts" / "skill_eval_runners.py",
        repo_root / "scripts" / "skill_eval_telemetry.py",
        repo_root / "scripts" / "skill_eval_validation.py",
    ]
    return _fingerprint_files(repo_root, files, payload)


def package_matches(source: Path, target: Path) -> bool:
    if not target.is_dir():
        return False
    source_files = {path.relative_to(source) for path in tree_files(source)}
    target_files = {path.relative_to(target) for path in tree_files(target)}
    if source_files != target_files:
        return False
    return all(
        (target / relative).read_bytes() == (source / relative).read_bytes()
        for relative in source_files
    )
