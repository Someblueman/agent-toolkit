"""Mechanical scorer for soa-layout-rewrite. Prints METRICS {...}; exit 0 = pass.

Strategy: the submitted particle_step.c is compiled with the exact same
flags as a pristine baseline embedded below (agents cannot touch the
baseline). Behavioral identity is asserted bit-for-bit on two fresh
deterministic datasets, the fixed harness region is checked byte-for-byte,
and the reported time per step is compared against the baseline
(median-of-7 runs, each with in-binary warmup).
"""
import hashlib
import json
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

THRESHOLD = 3.0            # required speedup vs pristine baseline
TIMED_RUNS = 7             # median-of-N, after warmup
DATASETS = [               # (n, seed): fresh deterministic data at verify time
    (2_000_000, 911),
    (150_000, 424242),
]
CFLAGS = ["cc", "-O3"]     # identical for baseline and submission; no -ffast-math
HARNESS_BEGIN = "/* ==== harness begin (do not modify) ==== */"
HARNESS_END = "/* ==== harness end ==== */"

PASS = True

# Pristine original, embedded so agents cannot tamper with the benchmark.
BASELINE_SRC = '/* Field simulation kernel.\n *\n * A world holds N particles; each particle carries a field value `x` that\n * evolves over time. One call to step() advances the field once. The fixed\n * harness in this file initializes the world from a deterministic seed,\n * runs warmup + timed steps, and prints a checksum of the field plus the\n * measured time per step:\n *\n *   cc -O3 particle_step.c && ./a.out [n] [seed]\n *\n * Improve the implementation so the reported time per step drops as much\n * as possible while every printed value stays bit-identical on any input.\n *\n * The region between HARNESS BEGIN and HARNESS END is checked byte-for-byte\n * by the scorer and must not change.\n */\n#include <stdio.h>\n#include <stdlib.h>\n#include <stdint.h>\n#include <time.h>\n\n/* One particle in the field. */\nstruct Particle {\n    float x;       /* field value */\n    float vx;      /* rate of change of the field */\n    float y;\n    float vy;\n    float z;\n    float vz;\n    float mass;\n    float charge;\n};\n\nenum { F_X, F_VX, F_Y, F_VY, F_Z, F_VZ, F_MASS, F_CHARGE };\n\n/* The world owns all particle state for the run. */\nstruct World {\n    size_t n;\n    struct Particle *p;\n};\n\nstruct World *world_create(size_t n);\nvoid world_destroy(struct World *w);\nvoid world_set(struct World *w, size_t i, int field, double v);\ndouble world_get_x(const struct World *w, size_t i);\nvoid step(struct World *w, float dt);\n\n/* ===================== implementation ===================== */\n\nstruct World *world_create(size_t n) {\n    struct World *w = malloc(sizeof *w);\n    if (!w) abort();\n    w->n = n;\n    w->p = calloc(n, sizeof *w->p);\n    if (!w->p) abort();\n    return w;\n}\n\nvoid world_destroy(struct World *w) {\n    free(w->p);\n    free(w);\n}\n\nvoid world_set(struct World *w, size_t i, int field, double v) {\n    struct Particle *p = &w->p[i];\n    switch (field) {\n    case F_X:     p->x = (float)v; break;\n    case F_VX:    p->vx = (float)v; break;\n    case F_Y:     p->y = (float)v; break;\n    case F_VY:    p->vy = (float)v; break;\n    case F_Z:     p->z = (float)v; break;\n    case F_VZ:    p->vz = (float)v; break;\n    case F_MASS:  p->mass = (float)v; break;\n    case F_CHARGE: p->charge = (float)v; break;\n    }\n}\n\ndouble world_get_x(const struct World *w, size_t i) {\n    return (double)w->p[i].x;\n}\n\nvoid step(struct World *w, float dt) {\n    const size_t n = w->n;\n    for (size_t i = 0; i < n; i++) {\n        w->p[i].x += w->p[i].vx * dt;\n    }\n}\n\n/* ==== harness begin (do not modify) ==== */\n#undef step\n#undef world_create\n#undef world_destroy\n#undef world_set\n#undef world_get_x\n#undef clock_gettime\n#undef printf\n#undef mix64\n\nstatic uint64_t mix64(uint64_t k) {\n    k += 0x9E3779B97F4A7C15ULL;\n    k = (k ^ (k >> 30)) * 0xBF58476D1CE4E5B9ULL;\n    k = (k ^ (k >> 27)) * 0x94D049BB133111EBULL;\n    return k ^ (k >> 31);\n}\n\n#define REPS 20\n\nint main(int argc, char **argv) {\n    size_t n = argc > 1 ? strtoull(argv[1], NULL, 10) : 2000000;\n    uint64_t seed = argc > 2 ? strtoull(argv[2], NULL, 10) : 7;\n\n    struct World *w = world_create(n);\n    for (size_t i = 0; i < n; i++) {\n        for (int f = 0; f < 8; f++) {\n            uint64_t r = mix64(seed + (uint64_t)i * 1000003ULL + (uint64_t)f * 7919ULL);\n            world_set(w, i, f, (double)(r >> 11) * (1.0 / 9007199254740992.0));\n        }\n    }\n\n    const float dt = 0.0075f;\n    for (int r = 0; r < 2; r++) step(w, dt); /* warmup */\n\n    struct timespec t0, t1;\n    clock_gettime(CLOCK_MONOTONIC, &t0);\n    for (int r = 0; r < REPS; r++) step(w, dt);\n    clock_gettime(CLOCK_MONOTONIC, &t1);\n\n    double checksum = 0.0;\n    for (size_t i = 0; i < n; i++) checksum += world_get_x(w, i);\n\n    double ns = (double)(t1.tv_sec - t0.tv_sec) * 1e9\n              + (double)(t1.tv_nsec - t0.tv_nsec);\n    printf("checksum %.17g\\n", checksum);\n    printf("time_per_step_ms %.6f\\n", ns / 1e6 / REPS);\n    world_destroy(w);\n    return 0;\n}\n/* ==== harness end ==== */\n'


def fail(msg: str):
    global PASS
    PASS = False
    print(f"FAIL: {msg}", file=sys.stderr)


def extract_harness(src: str):
    b = src.find(HARNESS_BEGIN)
    e = src.find(HARNESS_END)
    if b == -1 or e == -1 or e < b:
        return None
    return src[b:e + len(HARNESS_END)]


def compile_src(src: str, out: Path, workdir: Path):
    src_path = workdir / (out.name + ".c")
    src_path.write_text(src)
    r = subprocess.run(CFLAGS + ["-o", str(out), str(src_path)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        fail(f"compile failed for {out.name}:\n{r.stderr.strip()[:2000]}")
        return False
    return True


def run_bin(binary: Path, n: int, seed: int):
    try:
        r = subprocess.run([str(binary), str(n), str(seed)],
                           capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        fail(f"{binary.name} timed out")
        return None
    if r.returncode != 0:
        fail(f"{binary.name} exited {r.returncode}: {r.stderr.strip()[:500]}")
        return None
    m_ck = re.search(r"^checksum (.+)$", r.stdout, re.M)
    m_t = re.search(r"^time_per_step_ms (.+)$", r.stdout, re.M)
    if not m_ck or not m_t:
        fail(f"{binary.name} produced unparseable output:\n{r.stdout[:500]}")
        return None
    return {"checksum": m_ck.group(1), "ms": float(m_t.group(1))}


def main():
    src_path = Path("particle_step.c")
    if not src_path.exists():
        fail("particle_step.c not found in the workspace")
        print("METRICS " + json.dumps({"pass": 0, "speedup": None}))
        return 1
    submitted = src_path.read_text()

    baseline_harness = extract_harness(BASELINE_SRC)
    submitted_harness = extract_harness(submitted)
    if baseline_harness is None or submitted_harness is None:
        fail("harness region markers missing")
    elif hashlib.sha256(baseline_harness.encode()).hexdigest() != \
            hashlib.sha256(submitted_harness.encode()).hexdigest():
        fail("the fixed harness region was modified")

    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td)
        bin_base = workdir / "baseline"
        bin_opt = workdir / "optimized"
        ok_base = compile_src(BASELINE_SRC, bin_base, workdir)
        ok_opt = compile_src(submitted, bin_opt, workdir)
        if not (ok_base and ok_opt):
            print("METRICS " + json.dumps({"pass": 0, "speedup": None}))
            return 1

        # Behavioral identity on fresh deterministic data (all datasets).
        ref_ck = {}
        for n, seed in DATASETS:
            rb = run_bin(bin_base, n, seed)
            ro = run_bin(bin_opt, n, seed)
            if rb is None or ro is None:
                print("METRICS " + json.dumps({"pass": 0, "speedup": None}))
                return 1
            ref_ck[(n, seed)] = rb["checksum"]
            if rb["checksum"] != ro["checksum"]:
                fail(f"checksum differs from baseline on dataset n={n} seed={seed}: "
                     f"baseline {rb['checksum']} vs submitted {ro['checksum']}")

        # Timing: median-of-7 per step, warmup happens inside each binary.
        t_base, t_opt = [], []
        for _ in range(TIMED_RUNS):
            n, seed = DATASETS[0]
            rb = run_bin(bin_base, n, seed)
            ro = run_bin(bin_opt, n, seed)
            if rb is None or ro is None:
                print("METRICS " + json.dumps({"pass": 0, "speedup": None}))
                return 1
            # Every timed run must still reproduce the reference checksum.
            if rb["checksum"] != ref_ck[(n, seed)] or ro["checksum"] != ref_ck[(n, seed)]:
                fail("checksum changed between runs; results are not deterministic")
            t_base.append(rb["ms"])
            t_opt.append(ro["ms"])

    med_base = statistics.median(t_base)
    med_opt = statistics.median(t_opt)
    if med_opt <= 0:
        fail("reported time per step is not positive")

    # Physical sanity floor: a correct step must at minimum read vx and
    # write x for every particle (8 bytes/particle). Anything materially
    # below this stream rate on a dataset that exceeds last-level cache
    # means the work was not actually performed inside the timed step.
    floor_ms = max(0.03, DATASETS[0][0] * 8 / 300e9 * 1e3)
    if med_opt < floor_ms:
        fail(f"reported time per step {med_opt:.4f} ms is below the physical "
             f"minimum ({floor_ms:.4f} ms) for moving the required data")

    speedup = med_base / med_opt if med_opt > 0 else 0.0
    if speedup < THRESHOLD:
        fail(f"speedup {speedup:.2f}x < required {THRESHOLD}x "
             f"(baseline {med_base:.4f} ms, submitted {med_opt:.4f} ms)")

    print("METRICS " + json.dumps({
        "pass": int(PASS),
        "speedup": round(speedup, 2),
        "baseline_ms": round(med_base, 4),
        "optimized_ms": round(med_opt, 4),
    }))
    return 0 if PASS else 1


if __name__ == "__main__":
    sys.exit(main())
