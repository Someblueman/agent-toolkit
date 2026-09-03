#!/usr/bin/env python3
"""skill-eval: deterministic A/B measurement of skill effectiveness.

For each (task, runner, arm):
  1. Fresh workspace = task scaffold.
  2. Prompt = task.md, prepended with the task's SKILL.md for the "with" arm.
  3. Runner CLI executes headless in an ISOLATED config home (no skills, no
     user config) so the "without" arm cannot auto-load shared skills.
  4. The hidden verifier scores the workspace mechanically; it never enters
     the agent-visible workspace.

Every `run` invocation is a BATCH with an id + manifest (models, runner
versions). Reports are built from explicit batches (default: latest batch
per task), never a pool of mixed batches within one task's arms. Runs that
fail for infrastructure reasons (runner/auth/timeout, isolation leak, no
verify output) are excluded from scoring and reported separately.

Commands:
  run    [--tasks t1,t2] [--runners codex,opencode,omp]
         [--arms with,without] [--samples N] [--concurrency K] [--batch ID]
  probe                model-level isolation check (once per runner/session)
  report [--batch a,b] rebuild evals/REPORT.md (default: latest per task)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVALS = REPO / "evals"
RESULTS = EVALS / "results"
RUN_TIMEOUT = 900

# task-id -> (skill dir name, metric name or None, lower_is_better)
TASKS = {
    # v1 series - discriminating tasks (v0 tasks py-async-endpoint,
    # tax-refactor, hot-path-optimize are retired: saturated both arms;
    # see evals/archive/REPORT-v0-calibration.md)
    "msg-clean-cutover": ("pragmatic-engineering", None, True),
    "event-sink-concrete": ("pragmatic-engineering", "banned_token_count", True),
    "sh-rollup-probe": ("shell-engineering", None, True),
    "fanout-cancel-batch": ("python-engineering", "wall_time_s", True),
    "regex-recompile-per-row": ("profiling-software-performance", "speedup", False),
    "soa-layout-rewrite": ("hardware-aware-optimization", "speedup", False),
    "go-error-chain": ("go-engineering", None, True),
}
RUNNERS = ("codex", "opencode", "omp")
# Pinned models (resolved, not runner defaults) so model drift cannot be
# attributed to skill effects. Persisted in each batch manifest.
MODELS = {"codex": "gpt-5.6-sol", "opencode": "opencode/big-pickle",
          "omp": "openai-codex/gpt-5.6-sol"}


def task_fingerprint(task: str) -> str:
    """Content fingerprint of everything that defines a task's measurement:
    the mapped skill's SKILL.md, task.md, verify.py, and the scaffold tree.
    Any edit to any of these changes the fingerprint and resets report
    pooling, so pre/post-edit runs can never be mixed."""
    import hashlib
    tdir = EVALS / "tasks" / task
    h = hashlib.sha256()
    h.update((REPO / "skills" / TASKS[task][0] / "SKILL.md").read_bytes())
    files = [tdir / "task.md", tdir / "verify.py"]
    files += sorted(p for p in (tdir / "scaffold").rglob("*") if p.is_file())
    for f in files:
        h.update(str(f.relative_to(tdir)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16]
def harness_fingerprint() -> str:
    """Fingerprint of the run protocol itself (both harness modules).

    Adapter changes (flags, isolation, model pinning) alter measurement
    conditions even when recorded models/versions match, so batches never
    pool across harness revisions."""
    import hashlib
    h = hashlib.sha256()
    for f in sorted((REPO / "scripts").glob("skill_eval*.py")):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16]




def log(msg: str):
    print(f"[skill-eval] {msg}", flush=True)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")




def write_manifest(batch: str, tasks, runners, arms, samples, concurrency) -> None:
    (RESULTS / batch).mkdir(parents=True, exist_ok=True)
    (RESULTS / batch / "manifest.json").write_text(json.dumps({
        "batch": batch, "started_at": utcnow(),
        "tasks": tasks, "runners": runners, "arms": arms,
        "samples": samples, "concurrency": concurrency,
        "runner_versions": {r: runner_version(r) for r in runners},
        "models": {r: MODELS[r] for r in runners},
        "task_skills": {t: TASKS[t][0] for t in tasks},
        "series": "v1",
        "fingerprints": {t: task_fingerprint(t) for t in tasks},
        "harness": harness_fingerprint(),
    }, indent=2))


# ---------------------------------------------------------------- isolation

def isolated_codex_home(base: Path) -> Path:
    """Empty CODEX_HOME: no skills, no AGENTS.md, no config.toml."""
    home = base / "codex-home"
    home.mkdir(parents=True)
    src = Path.home() / ".codex" / "auth.json"
    if src.exists():
        shutil.copy2(src, home / "auth.json")
    return home


def isolated_omp_home(base: Path) -> Path:
    """Fake HOME for omp: ~/.omp without skills, no ~/.codex/AGENTS.md."""
    home = base / "omp-home"
    (home / ".omp").mkdir(parents=True)
    agent = home / ".omp" / "agent"
    shutil.copytree(Path.home() / ".omp" / "agent", agent,
                    ignore=shutil.ignore_patterns("skills", "sessions",
                                                  "history.db*",
                                                  "terminal-sessions"))
    (home / ".codex").mkdir()  # exists but empty: no global AGENTS.md
    return home


def isolated_opencode_dirs(base: Path) -> tuple[Path, Path]:
    """Isolated XDG_CONFIG_HOME / XDG_DATA_HOME (auth copied file-to-file).

    OpenCode resolves its dirs as $XDG_CONFIG_HOME/opencode and
    $XDG_DATA_HOME/opencode, so files nest under opencode/. It also
    discovers global skills from ~/.claude/skills, hence the fake HOME.
    Config stays EMPTY: opencode/* plan models are built-in, and copying
    the user's opencode.json would reintroduce plugins/agent config.
    """
    cfg = base / "oc-config"
    data = base / "oc-data"
    (cfg / "opencode").mkdir(parents=True)
    (data / "opencode").mkdir(parents=True)
    src = Path.home() / ".local" / "share" / "opencode" / "auth.json"
    if src.exists():
        shutil.copy2(src, data / "opencode" / "auth.json")
    return cfg, data


def runner_env(runner: str, base: Path) -> dict:
    env = os.environ.copy()
    if runner == "codex":
        env["CODEX_HOME"] = str(isolated_codex_home(base))
    elif runner == "opencode":
        cfg, data = isolated_opencode_dirs(base)
        env["XDG_CONFIG_HOME"] = str(cfg)
        env["XDG_DATA_HOME"] = str(data)
        (base / "oc-home").mkdir()
        env["HOME"] = str(base / "oc-home")
    elif runner == "omp":
        env["HOME"] = str(isolated_omp_home(base))
    return env


def isolation_check(runner: str, base: Path, skill: str) -> dict:
    """Check that the *target* skill is not discoverable in this run config.

    Existence of runner-generated files (e.g. Codex's own config.toml or
    built-in skill dirs) is NOT a leak; only the target skill's presence is.
    """
    leaks: list[str] = []
    if runner == "codex":
        home = base / "codex-home"
        if (home / "skills" / skill).exists():
            leaks.append(f"codex-home/skills/{skill}")
        agents = home / "AGENTS.md"
        if agents.exists() and skill in agents.read_text(errors="ignore"):
            leaks.append(str(agents))
    elif runner == "opencode":
        cfg = base / "oc-config" / "opencode"
        for p in (cfg / "skill" / skill, cfg / "skills" / skill,
                  cfg / "agent", cfg / "command", cfg / "AGENTS.md",
                  base / "oc-home" / ".claude" / "skills" / skill):
            if p.exists():
                leaks.append(str(p))
    elif runner == "omp":
        omp_home = base / "omp-home"
        for p in (omp_home / ".omp" / "agent" / "skills" / skill,
                  omp_home / ".codex" / "AGENTS.md"):
            if p.exists():
                leaks.append(str(p))
    return {"runner": runner, "skill": skill, "leaks": leaks}


# ---------------------------------------------------------------- adapters

def build_cmd(runner: str, run_dir: Path, prompt: str) -> list[str]:
    """Headless invocation, skills disabled, model pinned via MODELS."""
    if runner == "codex":
        return ["codex", "exec", "--skip-git-repo-check", "--ephemeral",
                "--ignore-user-config", "--ignore-rules",
                "-C", str(run_dir), "-s", "workspace-write",
                "-m", MODELS["codex"], "-"]
    if runner == "opencode":
        return ["opencode", "run", "--pure", "--auto", "--dir", str(run_dir),
                "--model", MODELS["opencode"], prompt]
    if runner == "omp":
        return ["omp", "-p", "--cwd", str(run_dir), "--no-skills", "--no-rules",
                "--no-extensions", "--no-lsp", "--no-pty", "--auto-approve",
                "--no-session", "--max-time", "840",
                "--model", MODELS["omp"], prompt]
    raise ValueError(runner)


def run_agent(runner: str, run_dir: Path, prompt: str, base: Path) -> dict:
    argv = build_cmd(runner, run_dir, prompt)
    t0 = time.monotonic()
    try:
        proc = subprocess.run(argv, cwd=str(run_dir), env=runner_env(runner, base),
                              input=prompt, capture_output=True, text=True,
                              timeout=RUN_TIMEOUT)
        ok = proc.returncode == 0
        err = proc.stderr[-2000:]
        out = proc.stdout[-1500:]
    except subprocess.TimeoutExpired:
        ok, err, out = False, f"timeout after {RUN_TIMEOUT}s", ""
    return {"runner_ok": ok, "duration_s": round(time.monotonic() - t0, 1),
            "stderr": err, "stdout_tail": out}


# ---------------------------------------------------------------- scoring

def verify(run_dir: Path, verifier: Path) -> dict:
    """Run the hidden verifier with cwd=workspace; it lives outside it.

    PYTHONPATH includes the workspace so the verifier can import agent-edited
    modules while the verifier file itself stays invisible to the agent.
    """
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(run_dir) + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run([sys.executable, str(verifier)], cwd=str(run_dir),
                              env=env, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return {"scored": False, "pass": 0, "metrics": {},
                "verify_stderr": "verify timeout"}
    metrics = {}
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith("METRICS "):
            metrics = json.loads(line[len("METRICS "):])
            break
    scored = bool(metrics)  # a run is only scored if the verifier emitted data
    return {"scored": scored, "pass": int(scored and proc.returncode == 0),
            "metrics": metrics,
            "verify_stderr": proc.stderr[-1000:] if proc.returncode else ""}


def one_run(batch: str, task: str, runner: str, arm: str, i: int,
            skill_txt: str) -> dict:
    tdir = EVALS / "tasks" / task
    with tempfile.TemporaryDirectory(prefix="skilleanon-") as tmp:
        base = Path(tmp)
        run_dir = base / "workspace"
        shutil.copytree(tdir / "scaffold", run_dir)
        task_md = (tdir / "task.md").read_text()
        prompt = (f"# Skill instructions\n\n{skill_txt}\n\n# Task\n\n{task_md}"
                  if arm == "with" else task_md)
        prompt += ("\n\nWork directly in the current directory. Make the change, "
                   "then stop. Do not ask questions.\n")
        result = run_agent(runner, run_dir, prompt, base)
        result.update(verify(run_dir, tdir / "verify.py"))
        result["isolation"] = isolation_check(runner, base, TASKS[task][0])
    # valid = infra worked AND no isolation leak; only valid runs are scored
    valid = bool(result["runner_ok"] and result["scored"]
                 and not result["isolation"]["leaks"])
    rec = {"batch": batch, "task": task, "runner": runner, "arm": arm,
           "sample": i, "started_at": utcnow(), "valid": valid, **result}
    out = RESULTS / batch / task / runner / arm
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    (out / f"{stamp}_{i:03d}.json").write_text(json.dumps(rec, indent=2))
    tag = "VALID PASS" if valid and rec["pass"] else \
          "VALID FAIL" if valid else "INFRA-INVALID"
    log(f"{task} {runner} {arm} #{i}: {tag} ({rec.get('duration_s')}s)")
    return rec


def skill_text(skill: str) -> str:
    return (REPO / "skills" / skill / "SKILL.md").read_text()


def runner_version(runner: str) -> str | None:
    argv = {"codex": ["codex", "--version"],
            "opencode": ["opencode", "--version"],
            "omp": ["omp", "--version"]}[runner]
    try:
        return subprocess.run(argv, capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except Exception:
        return None




def run_batch(tasks, runners, arms, samples, concurrency, batch) -> list[dict]:
    write_manifest(batch, tasks, runners, arms, samples, concurrency)
    jobs = [(t, r, a, i) for t in tasks for r in runners for a in arms
            for i in range(1, samples + 1)]
    recs = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = {pool.submit(one_run, batch, t, r, a, i,
                            skill_text(TASKS[t][0])): (t, r, a, i)
                for t, r, a, i in jobs}
        for fut in as_completed(futs):
            try:
                recs.append(fut.result())
            except Exception as e:
                log(f"ERROR {futs[fut]}: {e}")
    return recs


def probe_runner(runner: str) -> dict:
    """Model-level check: ask the isolated agent what instructions it sees."""
    with tempfile.TemporaryDirectory(prefix="skilleanon-probe-") as tmp:
        base = Path(tmp)
        run_dir = base / "workspace"
        run_dir.mkdir()
        prompt = ("Before doing anything: list the names of any skills, custom "
                  "instructions, or AGENTS.md content currently loaded in your "
                  "context. If none, reply exactly NONE. Then stop.")
        res = run_agent(runner, run_dir, prompt, base)
        res["runner"] = runner
        return res


# ---------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser(prog="skill-eval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--tasks", default="all")
    r.add_argument("--runners", default="all")
    r.add_argument("--arms", default="with,without")
    r.add_argument("--samples", type=int, default=5)
    r.add_argument("--concurrency", type=int, default=6)
    r.add_argument("--batch", default=None,
                   help="batch id; defaults to <UTC timestamp>_<uuid4hex4>")
    rp = sub.add_parser("report")
    rp.add_argument("--batch", default=None,
                    help="comma-separated batch ids, oldest first; "
                         "default: all series-v1 batches, latest wins per task")
    sub.add_parser("probe")
    args = ap.parse_args()

    if args.cmd == "probe":
        out = {}
        for runner in RUNNERS:
            res = probe_runner(runner)
            out[runner] = {"ok": res["runner_ok"],
                           "reply_tail": (res.get("stdout_tail") or "")[-1200:]}
            log(f"probe {runner}: ok={res['runner_ok']}")
        (RESULTS / "isolation").mkdir(parents=True, exist_ok=True)
        (RESULTS / "isolation" / "probe.json").write_text(json.dumps(out, indent=2))
        for runner, o in out.items():
            print(f"--- {runner} ---\n{o['reply_tail']}\n", file=sys.stderr)
        return 0

    if args.cmd == "report":
        from skill_eval_report import all_batches, build_report
        batches = (args.batch.split(",") if args.batch else all_batches("v1"))
        (EVALS / "REPORT.md").write_text(build_report(batches))
        log(f"wrote evals/REPORT.md from batches {batches}")
        return 0

    batch = args.batch or \
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:4]}"
    tasks = list(TASKS) if args.tasks == "all" else args.tasks.split(",")
    runners = list(RUNNERS) if args.runners == "all" else args.runners.split(",")
    for t in tasks:
        if t not in TASKS:
            ap.error(f"unknown task {t}")
    run_batch(tasks, runners, args.arms.split(","), args.samples,
              args.concurrency, batch)
    from skill_eval_report import all_batches, build_report
    batches = all_batches("v1")
    (EVALS / "REPORT.md").write_text(build_report(batches))
    log(f"wrote evals/REPORT.md from batches {batches}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
