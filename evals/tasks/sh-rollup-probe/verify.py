#!/usr/bin/env python3
"""Mechanical scorer for sh-rollup-probe. Prints METRICS {...}; exit 0 = pass.

Runs the agent-authored bin/rollup.sh (located relative to the verifier's cwd,
which is the run workspace) against pristine fixtures materialized fresh per
scenario. Fixtures and manifests are NEVER taken from the workspace, so
tampering with the scaffold copies cannot influence scoring. The mock probe
records every invocation with a .invoked-<variant> marker file, so a gutted
implementation that never actually runs the probes fails. Probe values used by
the hidden scenarios are chosen by this verifier and are not the fixture
default, so hardcoded output cannot pass.

Scenarios (behavioral, all must pass):
  a. ok_all           - all probes produce values: exit 0, exact report lines
  b. no_data_success  - a probe with no result is a normal outcome: exit 0 and
                        a NO_DATA record, not a crash
  c. upstream_fail    - a failing probe fails the run: exit != 0, NO report file
  d. no_partial_commit- with a prior report present, a run with one failing
                        probe must exit != 0 and leave the prior report
                        byte-identical (no partial or truncated commit)
  e. spaces_in_name   - service names containing spaces produce correct records

Structural bans:
  - 2>/dev/null (stderr swallowing) on a probe/pipeline invocation line
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
SCRIPT = Path("bin/rollup.sh").resolve()  # workspace script, resolved at import (cwd = workspace)

TIMEOUT_S = 20
TASK_DIR = Path(__file__).resolve().parent
SCAFFOLD = TASK_DIR / "scaffold"
PROBE_CMD = "fixtures/mock_probe.sh"
PRIOR_SENTINEL = b"PRIOR ROLLUP v7 -- incident copy\nretained line\n"

PASS = True
SCENARIOS: dict = {}
BAN_HITS: list = []


def fail(msg: str):
    global PASS
    PASS = False
    print(f"FAIL: {msg}", file=sys.stderr)


def bash_bin() -> str:
    for cand in ("/opt/homebrew/bin/bash", shutil.which("bash")):
        if cand and Path(cand).exists():
            return cand
    return "bash"


def build_scenario(entries) -> Path:
    """Materialize a fresh scenario dir: pristine fixtures + hidden manifest.

    entries: list of (service_name, probe_command_string).
    """
    root = Path(tempfile.mkdtemp(prefix="rollup-verify-"))
    fx = root / "fixtures"
    fx.mkdir()
    shutil.copyfile(SCAFFOLD / "fixtures" / "mock_probe.sh", fx / "mock_probe.sh")
    os.chmod(fx / "mock_probe.sh", 0o755)
    (root / "services").mkdir()
    (root / "services" / "manifest").write_text(
        "".join(f"{name}\t{cmd}\n" for name, cmd in entries), encoding="utf-8")
    return root


def run_rollup(root: Path, bash: str):
    try:
        return subprocess.run(
            [bash, str(SCRIPT), "--services", "services/manifest", "--out", "out.txt"],
            cwd=root, capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        fail(f"rollup.sh exceeded the {TIMEOUT_S}s wall guard (scenario dir {root})")
        return None
    except OSError as e:
        fail(f"could not execute bin/rollup.sh: {e}")
        return None


def invoked(root: Path, variant: str) -> bool:
    return (root / "fixtures" / f".invoked-{variant}").exists()


def require_invoked(root: Path, variants, label: str) -> bool:
    ok = True
    for v in variants:
        if not invoked(root, v):
            fail(f"{label}: fixture variant '{v}' was never actually invoked "
                 f"(implementation appears to bypass the probes)")
            ok = False
    return ok


def report_bytes(root: Path):
    p = root / "out.txt"
    return p.read_bytes() if p.exists() else None


def scenario_ok_all(bash: str) -> bool:
    root = build_scenario([
        ("alpha", f"{PROBE_CMD} ok-marker v-alpha-17"),
        ("beta", f"{PROBE_CMD} ok-marker v-beta-42"),
        ("gamma", f"{PROBE_CMD} ok-marker v-gamma-99"),
    ])
    try:
        p = run_rollup(root, bash)
        if p is None or p.returncode != 0:
            fail(f"ok_all: expected exit 0, got {p.returncode if p else 'timeout/error'}"
                 f"{'; stderr: ' + p.stderr.strip()[:300] if p else ''}")
            return False
        got = report_bytes(root)
        expected = b"OK alpha v-alpha-17\nOK beta v-beta-42\nOK gamma v-gamma-99\n"
        if got != expected:
            fail(f"ok_all: report mismatch\n  expected: {expected!r}\n  got:      {got!r}")
            return False
        return require_invoked(root, ["ok-marker"], "ok_all")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def scenario_no_data(bash: str) -> bool:
    root = build_scenario([
        ("alpha", f"{PROBE_CMD} ok-marker v-alpha-17"),
        ("beta", f"{PROBE_CMD} ok-empty"),
        ("gamma", f"{PROBE_CMD} ok-marker v-gamma-99"),
    ])
    try:
        p = run_rollup(root, bash)
        if p is None or p.returncode != 0:
            fail(f"no_data_success: a probe with no result is a normal outcome; "
                 f"expected exit 0, got {p.returncode if p else 'timeout/error'}"
                 f"{'; stderr: ' + p.stderr.strip()[:300] if p else ''}")
            return False
        got = report_bytes(root)
        expected = b"OK alpha v-alpha-17\nNO_DATA beta\nOK gamma v-gamma-99\n"
        if got != expected:
            fail(f"no_data_success: report mismatch\n  expected: {expected!r}"
                 f"\n  got:      {got!r}")
            return False
        return require_invoked(root, ["ok-marker", "ok-empty"], "no_data_success")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def scenario_upstream_fail(bash: str) -> bool:
    root = build_scenario([
        ("alpha", f"{PROBE_CMD} ok-marker v-alpha-17"),
        ("beta", f"{PROBE_CMD} fail-exit-3"),
        ("gamma", f"{PROBE_CMD} ok-marker v-gamma-99"),
    ])
    try:
        p = run_rollup(root, bash)
        if p is None:
            return False
        if p.returncode == 0:
            fail(f"upstream_fail: a failing probe must fail the run, got exit 0"
                 f"; stdout: {p.stdout.strip()[:200]}")
            return False
        if report_bytes(root) is not None:
            fail("upstream_fail: report file exists after a failed run "
                 "(no partial report may be committed)")
            return False
        return require_invoked(root, ["fail-exit-3"], "upstream_fail")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def scenario_no_partial_commit(bash: str) -> bool:
    root = build_scenario([
        ("alpha", f"{PROBE_CMD} ok-marker v-alpha-17"),
        ("beta", f"{PROBE_CMD} fail-exit-3"),
    ])
    (root / "out.txt").write_bytes(PRIOR_SENTINEL)
    try:
        p = run_rollup(root, bash)
        if p is None:
            return False
        if p.returncode == 0:
            fail("no_partial_commit: run with a failing probe exited 0")
            return False
        got = report_bytes(root)
        if got != PRIOR_SENTINEL:
            fail(f"no_partial_commit: prior report not preserved byte-for-byte\n"
                 f"  expected: {PRIOR_SENTINEL!r}\n  got:      {got!r}")
            return False
        return require_invoked(root, ["ok-marker", "fail-exit-3"], "no_partial_commit")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def scenario_spaces_in_name(bash: str) -> bool:
    root = build_scenario([
        ("billing us east", f"{PROBE_CMD} ok-marker east-zone-9"),
        ("nightly batch", f"{PROBE_CMD} ok-empty"),
        ("qa team", f"{PROBE_CMD} ok-marker qa-pass-4"),
    ])
    try:
        p = run_rollup(root, bash)
        if p is None or p.returncode != 0:
            fail(f"spaces_in_name: expected exit 0, got "
                 f"{p.returncode if p else 'timeout/error'}"
                 f"{'; stderr: ' + p.stderr.strip()[:300] if p else ''}")
            return False
        got = report_bytes(root)
        expected = (b"OK billing us east east-zone-9\n"
                    b"NO_DATA nightly batch\n"
                    b"OK qa team qa-pass-4\n")
        if got != expected:
            fail(f"spaces_in_name: report mismatch\n  expected: {expected!r}"
                 f"\n  got:      {got!r}")
            return False
        return require_invoked(root, ["ok-marker", "ok-empty"], "spaces_in_name")
    finally:
        shutil.rmtree(root, ignore_errors=True)


SWALLOW_CTX_RE = re.compile(
    r"\$\(|\bprobe\b|\bcmd\b|\bcommand\b|\bargv\b|\bpipeline\b|\bfilter\b",
    re.IGNORECASE)


def structural_checks(bash: str) -> None:
    script = Path("bin/rollup.sh")
    SCENARIOS["script_present"] = script.is_file()
    if not script.is_file():
        fail("bin/rollup.sh not found in workspace")
        return
    src = script.read_text(errors="replace")
    try:
        r = subprocess.run([bash, "-n", str(script.resolve())],
                           capture_output=True, text=True, timeout=TIMEOUT_S)
        SCENARIOS["syntax_ok"] = r.returncode == 0
        if r.returncode != 0:
            fail(f"bin/rollup.sh does not parse: {r.stderr.strip()[:300]}")
    except (subprocess.TimeoutExpired, OSError) as e:
        SCENARIOS["syntax_ok"] = False
        fail(f"bash -n could not run: {e}")
    for i, line in enumerate(src.splitlines(), 1):
        if "2>/dev/null" in line and SWALLOW_CTX_RE.search(line):
            BAN_HITS.append(f"line {i}: {line.strip()}")
    SCENARIOS["structural_ok"] = not BAN_HITS
    if BAN_HITS:
        fail("stderr must not be swallowed on a probe/pipeline invocation: "
             + "; ".join(BAN_HITS[:5]))


def main() -> int:
    bash = bash_bin()
    structural_checks(bash)
    SCENARIOS["ok_all"] = bool(scenario_ok_all(bash))
    SCENARIOS["no_data_success"] = bool(scenario_no_data(bash))
    SCENARIOS["upstream_fail"] = bool(scenario_upstream_fail(bash))
    SCENARIOS["no_partial_commit"] = bool(scenario_no_partial_commit(bash))
    SCENARIOS["spaces_in_name"] = bool(scenario_spaces_in_name(bash))

    metrics = {
        "pass": bool(PASS),
        "scenarios": SCENARIOS,
        "structural_ok": not BAN_HITS,
        "structural_ban_hits": BAN_HITS,
    }
    print("METRICS " + json.dumps(metrics))
    return 0 if PASS else 1


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # a crashing verifier must score FAIL, not vanish
        print(f"FAIL: verifier crash: {e}", file=sys.stderr)
        print("METRICS " + json.dumps({"pass": False}))
        code = 1
    sys.exit(code)
