#!/usr/bin/env python3
"""Mechanical scorer for regex-recompile-per-row. Prints METRICS {...} as the
last stdout line; exit 0 = pass.

Run with cwd = the run workspace (a copy of scaffold/ containing the agent's
edited main.py). This file is never copied into the workspace.
"""
import ast
import json
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SPEEDUP_REQUIRED = 3.0
WARMUP = 3
SAMPLES_CANDIDATE = 7
SAMPLES_BASELINE = 5
N_TIMING = 35000
SEED_TIMING = 20260903
N_CORRECTNESS = 3000
CORRECTNESS_SEEDS = (101, 202, 303, 404, 505)

WORDS = ("token rotated for device shard lease expired retry budget drained "
         "cache warm replica promoted queue drained ledger committed session "
         "refreshed scope narrowed probe attached snapshot sealed index rebuilt "
         "quota renewed throttle lifted backfill resumed shard migrated").split()
LEVELS = ["info", "warn", "error", "debug", "notice"]
SVCS = ["auth", "billing", "search", "ingest", "notify", "profile"]

# Constructs the pipeline must never use: stdin/stdout only, no file I/O,
# no environment-dependent behavior, no escaping the process.
BANNED_SUBSTRINGS = (
    "os.environ", "getenv", "open(", "Path(", "write_text", "write_bytes",
    "popen", "subprocess", "socket", "urllib", "eval(", "exec(", "__import__",
)

# Pristine original, embedded so agents cannot tamper with the benchmark.
PRISTINE_SRC = r'''"""Audit-log normalizer.

Reads audit rows on stdin (one per line), extracts the structured fields of
each row, and writes one normalized row per input row on stdout.
"""
import re
import sys


def rolling_hash(text):
    """Order-sensitive content digest used for tamper detection."""
    h = 0x811C9DC5
    for tok in text.split(" "):
        for ch in tok:
            h ^= ord(ch)
            h = (h * 0x01000193) & 0xFFFFFFFF
            h ^= h >> 7
            h = (h * 0x85EBCA6B) & 0xFFFFFFFF
            h ^= h >> 3
            h = (h * 0x27220A95) & 0xFFFFFFFF
            h ^= h >> 11
            h ^= h >> 3
        h = (h + 0x9E3779B9) & 0xFFFFFFFF
    return h


def extract_fields(row):
    # Each row carries its own span id; the field scan for that row is
    # anchored on the row's span value.
    i = row.index("span=")
    span = row[i + 5 : i + 13]
    pat = re.compile(
        rf"^lvl=(?P<lvl>[a-z]+) svc=(?P<svc>[a-z-]+) trace=[0-9a-f]{{32}} span={span}"
        rf" seq=(?P<seq>\d+) dev=(?P<dev>d-\d+) msg=\"(?P<msg>[^\"]*)\"$"
    )
    m = pat.match(row)
    if m is None:
        return None
    return m


def normalize(row):
    m = extract_fields(row)
    if m is None:
        return None
    digest = rolling_hash(m.group("msg"))
    return "{}|{}|{}|{}|{:08x}".format(
        m.group("seq"), m.group("lvl"), m.group("svc"), m.group("dev"), digest
    )


def main():
    out = []
    for row in sys.stdin.buffer.read().decode().splitlines():
        line = normalize(row)
        if line is not None:
            out.append(line)
    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


if __name__ == "__main__":
    main()
'''


def fail(msg):
    global PASS
    PASS = False
    print(f"FAIL: {msg}", file=sys.stderr)


PASS = True


def gen_rows(seed, n):
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        lvl = rng.choice(LEVELS)
        svc = rng.choice(SVCS)
        trace = "%032x" % rng.getrandbits(128)
        span = "%08x" % rng.getrandbits(32)
        seq = "%06d" % rng.randrange(1000000)
        dev = "d-%d" % rng.randrange(1000, 10000)
        msg = " ".join(rng.choice(WORDS) for _ in range(rng.randrange(4, 9)))
        rows.append(
            f"lvl={lvl} svc={svc} trace={trace} span={span} seq={seq}"
            f" dev={dev} msg=\"{msg}\""
        )
        if len(rows) % 50 == 0:
            rows[-1] = _malformed(rng, rows[-1])
    return rows


def _malformed(rng, good_row):
    """A row the pipeline must cleanly skip (no output line, no crash)."""
    kind = rng.randrange(6)
    if kind == 0:  # seq contains letters
        return _repl(good_row, "seq=", "12a45")
    if kind == 1:  # uppercase level
        return good_row.replace("lvl=", "lvl=INFO_", 1)
    if kind == 2:  # span too short
        i = good_row.index("span=")
        return good_row[: i + 5] + good_row[i + 5 : i + 12] + good_row[i + 13 :]
    if kind == 3:  # span too long
        i = good_row.index("span=")
        return good_row[: i + 13] + "f" + good_row[i + 13 :]
    if kind == 4:  # trailing extra field after the quoted message
        return good_row + " extra=1"
    # svc with an underscore
    return good_row.replace("svc=", "svc=auth_", 1)


def _repl(row, key, value):
    i = row.index(key)
    j = row.index(" ", i)
    return row[: i] + key + value + row[j:]


def rolling_hash_ref(text):
    h = 0x811C9DC5
    for tok in text.split(" "):
        for ch in tok:
            h ^= ord(ch)
            h = (h * 0x01000193) & 0xFFFFFFFF
            h ^= h >> 7
            h = (h * 0x85EBCA6B) & 0xFFFFFFFF
            h ^= h >> 3
            h = (h * 0x27220A95) & 0xFFFFFFFF
            h ^= h >> 11
            h ^= h >> 3
        h = (h + 0x9E3779B9) & 0xFFFFFFFF
    return h


_LOWER = set("abcdefghijklmnopqrstuvwxyz")
_SVC = set("abcdefghijklmnopqrstuvwxyz-")
_HEX = set("0123456789abcdef")
_DIGITS = set("0123456789")


def _all_in(s, alphabet):
    return all(c in alphabet for c in s)


def golden_line(row):
    """Independent golden transform: split-based parse, no regex."""
    head, sep, tail = row.partition(' msg="')
    if not sep or not tail.endswith('"') or '"' in tail[:-1]:
        return None
    msg = tail[:-1]
    parts = head.split(" ")
    if len(parts) != 6:
        return None
    kv = []
    for p in parts:
        k, s, v = p.partition("=")
        if not s:
            return None
        kv.append((k, v))
    (k0, lvl), (k1, svc), (k2, trace), (k3, span), (k4, seq), (k5, dev) = kv
    if (k0, k1, k2, k3, k4, k5) != ("lvl", "svc", "trace", "span", "seq", "dev"):
        return None
    if not _all_in(lvl, _LOWER) or not _all_in(svc, _SVC):
        return None
    if len(trace) != 32 or not _all_in(trace, _HEX):
        return None
    if len(span) != 8 or not _all_in(span, _HEX):
        return None
    if not seq or not _all_in(seq, _DIGITS):
        return None
    if not dev.startswith("d-") or len(dev) < 3 or not _all_in(dev[2:], _DIGITS):
        return None
    digest = rolling_hash_ref(msg)
    return "{}|{}|{}|{}|{:08x}".format(seq, lvl, svc, dev, digest)


def golden_output(text):
    out = []
    for row in text.splitlines():
        line = golden_line(row)
        if line is not None:
            out.append(line)
    return ("\n".join(out) + ("\n" if out else "")).encode()


def _run(cwd, input_bytes, timeout=60):
    return subprocess.run(
        [sys.executable, "main.py"], input=input_bytes,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=str(cwd), timeout=timeout,
    )


def _median_time(cwd, input_bytes, warmup, samples, golden_bytes):
    times = []
    for i in range(warmup + samples):
        t0 = time.perf_counter()
        proc = _run(cwd, input_bytes)
        dt = time.perf_counter() - t0
        if proc.returncode != 0:
            fail(f"pipeline exited {proc.returncode}: {proc.stderr[-300:]!r}")
            return None
        if proc.stdout != golden_bytes:
            fail("stdout differs from the contract during the timed runs")
            return None
        if i >= warmup:
            times.append(dt)
    times.sort()
    return times[len(times) // 2]


def _static_checks(src):
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        fail(f"main.py does not parse: {e}")
        return
    defs = set()
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.add(node.name)
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                calls.add(f.id)
            elif isinstance(f, ast.Attribute):
                calls.add(f.attr)
    for name in ("extract_fields", "rolling_hash"):
        if name not in defs:
            fail(f"required function {name}() was removed")
        if name not in calls:
            fail(f"required function {name}() is no longer called")
    for b in BANNED_SUBSTRINGS:
        if b in src:
            fail(f"banned construct {b!r} (stdin/stdout only, no file or env access)")


def main():
    global PASS
    ws = Path.cwd()
    main_py = ws / "main.py"
    if not main_py.exists():
        fail("main.py not found in the workspace")
        print("METRICS " + json.dumps({"pass": False, "speedup": None}))
        return 1
    _static_checks(main_py.read_text())

    # --- correctness inputs (fixed seeds, mixed well-formed + skippable rows)
    data_by_seed = {}
    golden_by_seed = {}
    for seed in CORRECTNESS_SEEDS:
        data = ("\n".join(gen_rows(seed, N_CORRECTNESS)) + "\n").encode()
        data_by_seed[seed] = data
        golden_by_seed[seed] = golden_output(data.decode())

    # --- embedded pristine baseline sanity vs the independent golden
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "main.py").write_text(PRISTINE_SRC)
        for seed in CORRECTNESS_SEEDS:
            proc = _run(td, data_by_seed[seed])
            if proc.returncode != 0 or proc.stdout != golden_by_seed[seed]:
                fail(f"embedded pristine baseline disagrees with the contract "
                     f"(seed {seed})")
                break

    # --- candidate behavioral identity
    outs = set()
    if PASS:
        for seed in CORRECTNESS_SEEDS:
            proc = _run(ws, data_by_seed[seed])
            if proc.returncode != 0:
                fail(f"pipeline exited {proc.returncode} on seed {seed}: "
                     f"{proc.stderr[-300:]!r}")
                break
            if proc.stdout != golden_by_seed[seed]:
                fail(f"stdout is not byte-identical to the contract (seed {seed})")
                break
            outs.add(proc.stdout)
        if PASS and len(outs) < len(CORRECTNESS_SEEDS):
            fail("output identical across different inputs (hardcoded?)")

    # --- timing: relative ratio, candidate vs embedded pristine baseline
    t_base = t_cand = None
    if PASS:
        t_rows = gen_rows(SEED_TIMING, N_TIMING)
        t_data = ("\n".join(t_rows) + "\n").encode()
        t_golden = golden_output(t_data.decode())
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "main.py").write_text(PRISTINE_SRC)
            t_base = _median_time(td, t_data, WARMUP, SAMPLES_BASELINE, t_golden)
        t_cand = _median_time(ws, t_data, WARMUP, SAMPLES_CANDIDATE, t_golden)
        if t_base is None or t_cand is None:
            PASS = False
            t_base = t_base if t_base is not None else 0.0
            t_cand = t_cand if t_cand is not None else 0.0

    speedup = (t_base / t_cand) if (t_cand and t_base) else None
    if speedup is not None and speedup < SPEEDUP_REQUIRED:
        fail(f"speedup {speedup:.2f}x < required {SPEEDUP_REQUIRED}x "
             f"(baseline {t_base:.3f}s, candidate {t_cand:.3f}s)")

    print("METRICS " + json.dumps({
        "pass": bool(PASS),
        "speedup": round(speedup, 2) if speedup is not None else None,
        "baseline_s": round(t_base, 3) if t_base else None,
        "candidate_s": round(t_cand, 3) if t_cand else None,
    }))
    return 0 if PASS else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # never die without METRICS
        print(f"FAIL: verifier error: {e!r}", file=sys.stderr)
        print("METRICS " + json.dumps({"pass": False, "speedup": None}))
        sys.exit(1)
