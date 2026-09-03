"""Mechanical scorer for hot-path-optimize. Prints METRICS {...}; exit 0 = pass."""
import json
import sys
import time
from pathlib import Path

import gen_data

THRESHOLD = 20.0  # required speedup vs pristine baseline
PASS = True

# Pristine original, embedded so agents cannot tamper with the benchmark.
BASELINE_SRC = '''def first_unique_lines(lines):
    out = []
    for line in lines:
        if line not in out:
            out.append(line)
    return out
'''


def fail(msg: str):
    global PASS
    PASS = False
    print(f"FAIL: {msg}", file=sys.stderr)


def timed(fn, lines) -> float:
    t0 = time.perf_counter()
    fn(lines)
    return time.perf_counter() - t0


def main():
    try:
        import dedupe
    except Exception as e:
        fail(f"dedupe.py does not import: {e}")
        print("METRICS " + json.dumps({"pass": 0, "speedup": None}))
        return 1

    Path("data.txt").write_text("\n".join(gen_data.generate()) + "\n")
    lines = Path("data.txt").read_text().splitlines()
    reference = list(dict.fromkeys(lines))

    ns = {}
    exec(BASELINE_SRC, ns)
    baseline_fn = ns["first_unique_lines"]

    times = sorted(timed(dedupe.first_unique_lines, lines) for _ in range(5))
    t_new = times[2]  # median of 5: robust to scheduler noise
    t_base = timed(baseline_fn, lines)
    got = dedupe.first_unique_lines(lines)

    if got != reference:
        fail("output differs from the reference (first-seen order, dupes dropped)")
    speedup = t_base / t_new if t_new > 0 else float("inf")
    if speedup < THRESHOLD:
        fail(f"speedup {speedup:.1f}x < required {THRESHOLD}x "
             f"(baseline {t_base:.2f}s, new {t_new:.4f}s)")

    print("METRICS " + json.dumps({
        "pass": int(PASS),
        "speedup": round(speedup, 1),
        "baseline_s": round(t_base, 2),
        "optimized_s": round(t_new, 4),
    }))
    return 0 if PASS else 1


if __name__ == "__main__":
    sys.exit(main())
