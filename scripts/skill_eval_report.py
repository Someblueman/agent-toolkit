"""Stats + report generation for skill-eval (see skill_eval.py).

Imports the harness module for TASKS/RESULTS/load_batch_recs; skill_eval
imports this module lazily inside main(), so there is no import cycle.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import skill_eval as se

RESULTS = se.RESULTS


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def metric_of(task: str) -> str | None:
    return se.TASKS.get(task, (None, None, False))[1]


def aggregate(recs: list[dict]) -> dict:
    groups: dict[tuple, list] = {}
    for rec in recs:
        if not rec.get("valid") or rec["task"] not in se.TASKS:
            continue  # infra-invalid runs never enter the statistics
        groups.setdefault((rec["task"], rec["runner"], rec["arm"]), []).append(rec)
    agg = {}
    for (task, runner, arm), group in groups.items():
        n = len(group)
        passes = sum(r["pass"] for r in group)
        lo, hi = wilson(passes / n, n)
        vals = [r["metrics"].get(metric_of(task)) for r in group]
        vals = [v for v in vals if isinstance(v, (int, float))]
        agg[(task, runner, arm)] = {
            "n": n, "passes": passes,
            "pass_rate": round(passes / n, 3),
            "ci95": [round(lo, 3), round(hi, 3)],
            "metric_mean": round(sum(vals) / len(vals), 3) if vals else None,
    }
    return agg


def verdict(b: dict, w: dict | None) -> str:
    if not w:
        return "single arm only"
    if b.get("n") == 0 or w.get("n") == 0:
        return "no valid runs in one arm (infra failures) - not scorable"
    if b["ci95"][0] > w["ci95"][1] or w["ci95"][0] > b["ci95"][1]:
        return "separated at this N"
    gap = abs(w["pass_rate"] - b["pass_rate"])
    if b["pass_rate"] == 1.0 and w["pass_rate"] == 1.0:
        return "saturated: both arms at ceiling; add a harder task, more N won't help"
    if b["pass_rate"] == 0.0 and w["pass_rate"] == 0.0:
        return "universal fail: both arms at floor; task does not discriminate (fix task validity first)"
    need = 3 / max(gap, 0.01) ** 2
    if need > 100:
        return f"overlapping; >100/arm needed to resolve gap {gap:.2f} (not practical)"
    return f"overlapping; est. n~{int(need)}/arm to resolve gap {gap:.2f}"


def calibration_notes(agg: dict) -> str:
    out = (
        "Wilson CI half-width ~1.96*sqrt(p(1-p)/n); separating two arms at a\n"
        "true pass-rate gap g needs roughly n ~ 3/g^2 samples per arm\n"
        "(g=0.3 -> ~33; g=0.5 -> ~12). Current N per arm and verdicts:\n\n"
        "| task | runner | N per arm | verdict |\n|---|---|---|---|"
    )
    for t, r in sorted({(k[0], k[1]) for k in agg}):
        b = agg.get((t, r, "without"))
        w = agg.get((t, r, "with"))
        if b is None and w is None:
            continue  # no valid rows for this task/runner at all
        if b is None:
            b = {"n": 0, "pass_rate": w["pass_rate"], "ci95": [0.0, 1.0]}
        if w is None:
            w = {"n": 0, "pass_rate": b["pass_rate"], "ci95": [0.0, 1.0]}
        out += f"\n| {t} | {r} | {b['n']} | {verdict(b, w)} |"
    out += ("\n\nIncrease `--samples`, rerun `run` then `report`, until the "
            "arms' CIs\nreliably separate (or reliably don't) for the "
            "conclusion you need.")
    return out


def batch_series(batch: str) -> str:
    mpath = RESULTS / batch / "manifest.json"
    if mpath.exists():
        try:
            return json.loads(mpath.read_text()).get("series", "v0")
        except Exception:
            pass
    return "v0"


def all_batches(series: str | None = None) -> list[str]:
    if not RESULTS.exists():
        return []
    names = sorted(p.name for p in RESULTS.iterdir() if p.is_dir())
    if series is None:
        return names
    return [b for b in names if batch_series(b) == series]

def load_batch_recs(batch: str) -> list[dict]:
    recs = []
    for f in sorted((RESULTS / batch).glob("*/*/*/*.json")):
        try:
            recs.append(json.loads(f.read_text()))
        except json.JSONDecodeError:
            pass
    return recs


def build_report(batches: list[str]) -> str:
    """Build the report from the given batches, oldest to newest.

    Batches pool per task only when BOTH the runner config (models, runner
    versions, arms, samples) AND the task's content fingerprint (skill +
    prompt + verifier + scaffold) match. Any skill or eval edit resets
    pooling for that task. Skill labels come from the most recent batch
    supplying the task.
    """
    by_task: dict[str, list[dict]] = {}
    task_batch: dict[str, str] = {}
    task_compat: dict[str, tuple] = {}
    manifests: dict[str, dict] = {}
    for batch in batches:  # oldest -> newest
        batch_recs = load_batch_recs(batch)
        mpath = RESULTS / batch / "manifest.json"
        if mpath.exists():
            manifests[batch] = json.loads(mpath.read_text())
        m = manifests.get(batch, {})
        compat = (tuple(sorted((m.get("models") or {}).items())),
                  tuple(sorted((m.get("runner_versions") or {}).items())),
                  tuple(m.get("arms") or ()), m.get("samples"))
        for task in {r["task"] for r in batch_recs}:
            recs_t = [r for r in batch_recs if r["task"] == task]
            fp = (m.get("fingerprints") or {}).get(task)
            compat_t = compat + (fp, m.get("harness"))
            if task in by_task and task_compat[task] == compat_t:
                by_task[task] = by_task[task] + recs_t  # same protocol+config+content: pool
            else:
                by_task[task] = recs_t  # protocol, config, or content changed: latest wins
            task_batch[task] = batch
            task_compat[task] = compat_t
    recs = [r for task_recs in by_task.values() for r in task_recs]
    agg = aggregate(recs)
    invalid = [r for r in recs if not r.get("valid")]
    lines = ["# Skill Effectiveness Report",
             "",
             f"Batches: {', '.join(f'`{b}`' for b in batches)}"
             f"  |  Generated: {utcnow()}"]
    for batch, m in manifests.items():
        lines.append(f"- `{batch}`: samples/arm={m.get('samples')}, "
                     f"models={m.get('models')}, "
                     f"versions={m.get('runner_versions')}")
    lines += ["",
              "Each cell: pass rate [95% Wilson CI] over scored (valid) runs.",
              "`metric` is the task's mechanical metric (mean over runs with a",
              "value). `delta` = with-skill minus without-skill; for",
              "lower-is-better metrics a negative delta is an improvement.",
              ""]
    if invalid:
        reasons = sorted({r.get("invalid_reason", "infra failure")
                          for r in invalid if r.get("invalid_reason")})
        lines += [f"**{len(invalid)} run(s) excluded from scoring** "
                  "(infra failures, isolation leaks, or post-run invalidation):"]
        lines += [f"- {reason}" for reason in reasons]
        lines += ["See raw JSON under `evals/results/`.", ""]
    for task in sorted({k[0] for k in agg}):
        m = manifests.get(task_batch.get(task, ""), {})
        skill = m.get("task_skills", {}).get(task) or se.TASKS.get(task, ("?",))[0]
        lines += [f"## {task}", "", f"Skill: `{skill}`", "",
                  "| runner | without | with | delta (pass rate) | "
                  "metric w/o | metric with |",
                  "|---|---|---|---|---|---|"]
        for runner in sorted({k[1] for k in agg if k[0] == task}):
            b = agg.get((task, runner, "without"))
            w = agg.get((task, runner, "with"))
            if not b and not w:
                continue

            def cell(a):
                if not a:
                    return "-"
                return f"{a['pass_rate']} [{a['ci95'][0]},{a['ci95'][1]}] (n={a['n']})"

            delta = ""
            if b and w:
                d = w["pass_rate"] - b["pass_rate"]
                separated = w["ci95"][0] > b["ci95"][1] or b["ci95"][0] > w["ci95"][1]
                delta = f"{d:+.3f}" + (" *" if separated else "")
            lines.append(f"| {runner} | {cell(b)} | {cell(w)} | {delta} | "
                         f"{'-' if not b or b['metric_mean'] is None else b['metric_mean']} | "
                         f"{'-' if not w or w['metric_mean'] is None else w['metric_mean']} |")
        lines.append("")
    lines += ["`*` = non-overlapping 95% CIs (distinguishable at this N).", "",
              "## Sample-size calibration", "", calibration_notes(agg), ""]
    return "\n".join(lines)
