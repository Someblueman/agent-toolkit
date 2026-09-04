"""Task-bounded screening and paired value reporting for native skill evals."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


EFFICIENCY_FIELDS = (
    "duration_s", "total_tokens", "cached_input_tokens", "cost_usd",
    "tool_calls", "agent_steps",
)
EFFICIENCY_DIRECTION_FIELDS = (
    "duration_s", "total_tokens", "cost_usd", "tool_calls", "agent_steps",
)
FOOTPRINT_FIELDS = (
    "files_changed", "lines_added", "lines_deleted", "final_loc",
)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _optional_mean(rows: list[dict], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return _mean(values) if values else None


def _spread(rows: list[dict], key: str) -> float:
    values = [float(row[key]) for row in rows]
    return max(values) - min(values)


def _percent_change(with_value: float | None, without: float | None) -> float | None:
    if with_value is None or without in (None, 0):
        return None
    return (with_value - without) / without


def _screen_status(rows: list[dict]) -> str:
    if any(not row.get("valid") for row in rows):
        return "blocked"
    valid = [row for row in rows if row.get("valid")]
    if len(valid) < 2:
        return "insufficient"
    instability = float(valid[0]["instability_threshold"])
    if (
        _spread(valid, "score") > instability
        or _spread(valid, "quality_score") > instability
        or len({bool(row["pass"]) for row in valid}) > 1
    ):
        return "unstable"
    ceiling = float(valid[0]["ceiling_threshold"])
    if all(
        row["pass"] and float(row["score"]) >= ceiling
        and float(row["quality_score"]) >= ceiling
        for row in valid
    ):
        return "saturated"
    return "informative"


def summarize_screening(records: list[dict]) -> list[dict]:
    grouped: dict[tuple, list[dict]] = {}
    for record in records:
        if record.get("purpose") != "screen":
            continue
        required = {
            "skill", "runner", "model", "runtime_fingerprint", "task",
            "task_fingerprint", "score", "quality_score",
        }
        if required.issubset(record):
            key = (
                record["skill"], record.get("skill_fingerprint", "unknown"),
                record["runner"], record["model"], record["runtime_fingerprint"],
                record["task"], record["task_fingerprint"],
            )
            grouped.setdefault(key, []).append(record)
    rows = []
    for key, group in sorted(grouped.items()):
        valid = [row for row in group if row.get("valid")]
        rows.append({
            "skill": key[0], "skill_fingerprint": key[1],
            "runner": key[2], "model": key[3], "runtime_fingerprint": key[4],
            "task": key[5], "task_fingerprint": key[6],
            "samples": len(group), "valid": len(valid),
            "score": _optional_mean(valid, "score"),
            "quality_score": _optional_mean(valid, "quality_score"),
            "score_spread": _spread(valid, "score") if valid else None,
            "quality_spread": _spread(valid, "quality_score") if valid else None,
            "pass_rate": _optional_mean(valid, "pass"),
            "status": _screen_status(group),
        })
    return rows


def screening_gate(rows: list[dict]) -> dict:
    runners = {row["runner"] for row in rows}
    tasks = {row["task"] for row in rows}
    eligible = sorted(
        task for task in tasks
        if {row["runner"] for row in rows if row["task"] == task} == runners
        and all(
            row["status"] == "informative"
            for row in rows if row["task"] == task
        )
    )
    if len(eligible) >= 3:
        status = "passed"
    elif len(tasks) >= 6:
        status = "blocked-candidate-cap-exhausted"
    else:
        status = "needs-more-candidates"
    return {"status": status, "eligible": eligible, "screened": len(tasks)}


def _complete_pairs(group: list[dict]) -> dict[tuple[str, str], list[dict[str, dict]]]:
    by_task: dict[tuple[str, str], dict[tuple[str, str], list[dict]]] = {}
    for record in group:
        task = (record["task"], record.get("task_fingerprint", "unknown"))
        pair = (record.get("batch", "unknown"), record.get("pair_id", ""))
        by_task.setdefault(task, {}).setdefault(pair, []).append(record)
    complete: dict[tuple[str, str], list[dict[str, dict]]] = {}
    for task, pairs in by_task.items():
        for pair in pairs.values():
            arms = {row["arm"]: row for row in pair if row.get("valid")}
            if len(pair) == 2 and set(arms) == {"with", "without"}:
                complete.setdefault(task, []).append(arms)
    return complete


def _unstable(with_rows: list[dict], without_rows: list[dict]) -> bool:
    threshold = float(with_rows[0]["instability_threshold"])
    return any(
        _spread(rows, field) > threshold
        for rows in (with_rows, without_rows)
        for field in ("score", "quality_score")
    ) or any(len({bool(row["pass"]) for row in rows}) > 1
             for rows in (with_rows, without_rows))


def _value_label(row: dict, with_rows: list[dict], baseline_rows: list[dict]) -> str:
    ceiling = float(with_rows[0]["ceiling_threshold"])
    if _unstable(with_rows, baseline_rows):
        return "unstable"
    if all(
        item["pass"] and float(item["score"]) >= ceiling
        and float(item["quality_score"]) >= ceiling
        for item in baseline_rows
    ):
        return "saturated"
    effect = float(with_rows[0]["quality_effect"])
    if (
        row["with_pass"] < row["without_pass"]
        or row["score_delta"] <= -effect
        or row["quality_delta"] <= -effect
    ):
        return "regression"
    if (
        row["with_pass"] >= row["without_pass"]
        and (row["score_delta"] >= effect or row["quality_delta"] >= effect)
    ):
        return "helpful"
    return "no-observed-benefit"


def _efficiency_label(deltas: dict[str, float | None], threshold: float) -> str:
    values = [value for value in deltas.values() if value is not None]
    if not values:
        return "unknown"
    better = any(value <= -threshold for value in values)
    worse = any(value >= threshold for value in values)
    if better and not worse:
        return "more-efficient"
    if worse and not better:
        return "more-expensive"
    if better and worse:
        return "mixed"
    return "similar"


def _suite_verdict(task_rows: list[dict], invalid_count: int) -> str:
    if invalid_count:
        return "blocked"
    labels = [row["value"] for row in task_rows]
    if labels and all(label == "saturated" for label in labels):
        return "benchmark-saturated"
    if "unstable" in labels:
        return "unstable"
    helpful = labels.count("helpful")
    regressions = labels.count("regression")
    if helpful and regressions:
        return "mixed"
    if helpful:
        return "helpful-on-this-suite"
    if regressions:
        return "regression-on-this-suite"
    return "no-observed-benefit"


def summarize_records(records: list[dict]) -> list[dict]:
    screened: dict[tuple, list[dict]] = {}
    for record in records:
        if record.get("purpose") == "screen" and record.get("valid"):
            key = (
                record.get("skill"), record.get("skill_fingerprint", "unknown"),
                record.get("runner"), record.get("model"),
                record.get("runtime_fingerprint"), record.get("task"),
                record.get("task_fingerprint", "unknown"),
            )
            screened.setdefault(key, []).append(record)
    grouped: dict[tuple, list[dict]] = {}
    for record in records:
        if record.get("purpose") != "confirmatory":
            continue
        required = {
            "skill", "runner", "model", "runtime_fingerprint", "task", "arm",
        }
        if required.issubset(record):
            key = (
                record["skill"], record.get("skill_fingerprint", "unknown"),
                record["runner"], record["model"], record["runtime_fingerprint"],
            )
            grouped.setdefault(key, []).append(record)

    summaries = []
    for key, group in sorted(grouped.items()):
        invalid_count = sum(not row.get("valid") for row in group)
        task_rows = []
        for (task, task_hash), pairs in sorted(_complete_pairs(group).items()):
            without_rows = [pair["without"] for pair in pairs]
            with_rows = [pair["with"] for pair in pairs]
            screen_rows = screened.get((*key, task, task_hash), [])
            baseline_rows = without_rows + screen_rows
            row = {
                "task": task, "task_fingerprint": task_hash,
                "samples": len(pairs),
                "without_score": _optional_mean(without_rows, "score"),
                "with_score": _optional_mean(with_rows, "score"),
                "without_quality": _optional_mean(without_rows, "quality_score"),
                "with_quality": _optional_mean(with_rows, "quality_score"),
                "without_pass": _optional_mean(without_rows, "pass"),
                "with_pass": _optional_mean(with_rows, "pass"),
                "without_timeouts": _optional_mean(without_rows, "budget_exhausted"),
                "with_timeouts": _optional_mean(with_rows, "budget_exhausted"),
                "screen_quality": _optional_mean(screen_rows, "quality_score"),
                "baseline_spread": _spread(baseline_rows, "quality_score"),
                "instability_threshold": with_rows[0]["instability_threshold"],
            }
            row["score_delta"] = row["with_score"] - row["without_score"]
            row["quality_delta"] = row["with_quality"] - row["without_quality"]
            row["efficiency"] = {}
            row["footprint"] = {}
            for field in EFFICIENCY_FIELDS + FOOTPRINT_FIELDS:
                without = _optional_mean(without_rows, field)
                with_value = _optional_mean(with_rows, field)
                target = "efficiency" if field in EFFICIENCY_FIELDS else "footprint"
                row[target][field] = {
                    "without": without, "with": with_value,
                    "change": _percent_change(with_value, without),
                }
            threshold = float(with_rows[0]["efficiency_effect"])
            changes = {
                name: row["efficiency"][name]["change"]
                for name in EFFICIENCY_DIRECTION_FIELDS
            }
            row["efficiency_label"] = _efficiency_label(changes, threshold)
            row["value"] = _value_label(row, with_rows, baseline_rows)
            task_rows.append(row)
        if task_rows:
            summaries.append({
                "skill": key[0], "skill_fingerprint": key[1],
                "runner": key[2], "model": key[3], "runtime_fingerprint": key[4],
                "invalid_count": invalid_count, "task_rows": task_rows,
                "verdict": _suite_verdict(task_rows, invalid_count),
                "treatment_runs": sum(row.get("arm") == "with" for row in group),
                "activation_proven": sum(
                    row.get("arm") == "with" and row.get("activation") is True
                    for row in group
                ),
                "activation_unknown": sum(
                    row.get("arm") == "with" and row.get("activation") == "unknown"
                    for row in group
                ),
            })
    return summaries


def _load_batch(batch: str, history_root: Path) -> tuple[dict, list[dict]]:
    batch_dir = history_root / batch
    manifest = json.loads((batch_dir / "manifest.json").read_text())
    if manifest.get("schema_version") != 2:
        raise ValueError(f"unsupported manifest schema for {batch}")
    records = [
        json.loads(line) for line in (batch_dir / "runs.jsonl").read_text().splitlines()
        if line.strip()
    ]
    if any(record.get("schema_version") != 2 for record in records):
        raise ValueError(f"unsupported run schema for {batch}")
    return manifest, records


def _number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _change(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.0%}"


def _pair(values: dict, decimals: int = 1) -> str:
    without, with_value = values["without"], values["with"]
    if without is None or with_value is None:
        return "n/a"
    return (
        f"{without:.{decimals}f}→{with_value:.{decimals}f} "
        f"({_change(values['change'])})"
    )


def build_report(batches: tuple[str, ...], history_root: Path) -> str:
    manifests, records = [], []
    for batch in batches:
        manifest, batch_records = _load_batch(batch, history_root)
        manifests.append(manifest)
        records.extend(batch_records)
    screening = summarize_screening(records)
    summaries = summarize_records(records)
    invalid_counts = Counter(
        (row.get("invalid_class") or "unknown", row.get("invalid_reason") or "")
        for row in records if not row.get("valid")
    )
    lines = [
        "# Native Skill Value Report", "",
        "Correctness is the gate. Skill-specific quality, operational efficiency,",
        "patch footprint, and reliability remain separate dimensions. Every verdict",
        "is limited to the named tasks and exact runtime fingerprint.", "",
        "## Run manifests", "",
        "| batch | purpose | skill | tasks | samples/arm | runners | invalid |",
        "|---|---|---|---:|---:|---|---:|",
    ]
    for manifest in manifests:
        batch_rows = [row for row in records if row["batch"] == manifest["batch"]]
        lines.append(
            f"| `{manifest['batch']}` | {manifest['purpose']} | "
            f"`{manifest['skill']}` | {len(manifest['tasks'])} | "
            f"{manifest['samples_per_arm']} | {', '.join(manifest['runners'])} | "
            f"{sum(not row.get('valid') for row in batch_rows)} |"
        )
    lines.extend(["", "## Frozen identities", ""])
    for manifest in manifests:
        fingerprints = manifest["fingerprints"]
        lines.append(f"- `{manifest['batch']}` skill: `{fingerprints['skill']}`")
        for name, value in sorted(fingerprints["tasks"].items()):
            lines.append(f"  - task `{name}`: `{value}`")
        for name, value in sorted(fingerprints["runtimes"].items()):
            lines.append(f"  - runtime `{name}`: `{value}`")
    if invalid_counts:
        lines.extend(["", "## Invalid records", ""])
        for (kind, reason), count in sorted(invalid_counts.items()):
            lines.append(f"- {kind}: {reason or 'unspecified'} — {count}")

    quality_by_task: dict[str, set[str]] = {}
    for row in records:
        checks = row.get("metrics", {}).get("quality_checks", {})
        if isinstance(checks, dict):
            quality_by_task.setdefault(row.get("task", "unknown"), set()).update(
                str(name) for name in checks
            )
    if quality_by_task:
        lines.extend(["", "## Task-specific quality measures", ""])
        for task, checks in sorted(quality_by_task.items()):
            rendered = ", ".join(f"`{name}`" for name in sorted(checks))
            lines.append(f"- `{task}`: {rendered}")

    if screening:
        lines.extend([
            "", "## Baseline screening", "",
            "Only the without-skill arm is used. Saturated and unstable tasks must",
            "not be promoted into a frozen comparison for that runtime.", "",
            "| runner | task | correctness | quality | spread | pass | status |",
            "|---|---|---:|---:|---:|---:|---|",
        ])
        for row in screening:
            spread = max(row["score_spread"] or 0, row["quality_spread"] or 0)
            lines.append(
                f"| {row['runner']} | {row['task']} | {_number(row['score'])} | "
                f"{_number(row['quality_score'])} | {spread:.2f} | "
                f"{_number(row['pass_rate'])} | **{row['status']}** |"
            )
        gate = screening_gate(screening)
        lines.extend(["", "### Confirmatory freeze gate", ""])
        lines.append(
            f"- Screened {gate['screened']} candidate tasks; eligible on every "
            f"screened harness: {', '.join(gate['eligible']) or 'none'}."
        )
        lines.append(f"- Gate status: **{gate['status']}**.")
        if gate["status"] == "blocked-candidate-cap-exhausted":
            lines.append(
                "- No with-skill comparison is authorized: fewer than three "
                "stable, non-ceiling tasks remain after the six-candidate cap."
            )

    for summary in summaries:
        lines.extend([
            "", f"## {summary['skill']} — {summary['runner']}", "",
            f"Model: `{summary['model']}`  ",
            f"Runtime fingerprint: `{summary['runtime_fingerprint']}`  ",
            f"Proven skill reads: {summary['activation_proven']}/"
            f"{summary['treatment_runs']} treatment runs; trace-unknown: "
            f"{summary['activation_unknown']}  ",
            f"Suite-bounded verdict: **{summary['verdict']}**", "",
            "### Outcome and skill-specific quality", "",
            "| task | correctness without→with | quality without→with | pass "
            "without→with | value |",
            "|---|---:|---:|---:|---|",
        ])
        for row in summary["task_rows"]:
            lines.append(
                f"| {row['task']} | {row['without_score']:.2f}→{row['with_score']:.2f} "
                f"({row['score_delta']:+.2f}) | {row['without_quality']:.2f}→"
                f"{row['with_quality']:.2f} ({row['quality_delta']:+.2f}) | "
                f"{row['without_pass']:.2f}→{row['with_pass']:.2f} | "
                f"**{row['value']}** |"
            )
        for row in summary["task_rows"]:
            if (row["screen_quality"] is not None
                    and row["baseline_spread"] > row["instability_threshold"]):
                lines.append(
                    f"- `{row['task']}` baseline quality shifted from "
                    f"{row['screen_quality']:.2f} in screening to "
                    f"{row['without_quality']:.2f} in confirmation; combined "
                    f"spread {row['baseline_spread']:.2f} is **unstable**."
                )
        lines.extend([
            "", "### Operational efficiency", "",
            "Negative changes use fewer resources. Tool calls and agent steps are",
            "native-runner counts and are comparable only within this runtime.", "",
            "| task | seconds | tokens | cached | cost | tools | steps | interpretation |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ])
        for row in summary["task_rows"]:
            values = row["efficiency"]
            lines.append(
                f"| {row['task']} | {_pair(values['duration_s'])} | "
                f"{_pair(values['total_tokens'], 0)} | "
                f"{_pair(values['cached_input_tokens'], 0)} | "
                f"{_pair(values['cost_usd'], 4)} | "
                f"{_pair(values['tool_calls'], 1)} | "
                f"{_pair(values['agent_steps'], 1)} | "
                f"**{row['efficiency_label']}** |"
            )
        lines.extend([
            "", "### Patch footprint and reliability", "",
            "| task | files without→with | diff +added/-deleted | final LOC "
            "without→with | timeouts without→with |",
            "|---|---:|---:|---:|---:|",
        ])
        for row in summary["task_rows"]:
            footprint = row["footprint"]
            without_diff = (
                f"+{_number(footprint['lines_added']['without'])}/"
                f"-{_number(footprint['lines_deleted']['without'])}"
            )
            with_diff = (
                f"+{_number(footprint['lines_added']['with'])}/"
                f"-{_number(footprint['lines_deleted']['with'])}"
            )
            lines.append(
                f"| {row['task']} | {_number(footprint['files_changed']['without'])}→"
                f"{_number(footprint['files_changed']['with'])} | "
                f"{without_diff}→{with_diff} | "
                f"{_number(footprint['final_loc']['without'])}→"
                f"{_number(footprint['final_loc']['with'])} | "
                f"{row['without_timeouts']:.2f}→{row['with_timeouts']:.2f} |"
            )

    lines.extend(["", "## Across tested harnesses", ""])
    if not summaries:
        lines.append("- No compatible valid paired strata were available.")
    else:
        for summary in summaries:
            lines.append(
                f"- `{summary['runner']}` / `{summary['model']}`: "
                f"**{summary['verdict']}**"
            )
        lines.append(
            "- These are parallel task-bounded verdicts, not a pooled portability claim."
        )
    lines.extend([
        "", "Activation is `unknown` unless the native trace proves a successful",
        "skill read. Availability alone is not treated as invocation.", "",
    ])
    return "\n".join(lines)
