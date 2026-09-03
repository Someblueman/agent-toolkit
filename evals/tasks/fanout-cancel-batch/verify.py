"""Hidden mechanical scorer for fanout-cancel-batch.

Prints `METRICS {json}` as the last stdout line; exit 0 = pass.

Checks, in order:
  1. all-success batch returns results in input order
  2. single DataError  -> BatchFailed.failed_indexes == [2], no leftovers
  3. multi DataError   -> BatchFailed.failed_indexes == [0, 2, 4], no leftovers
  4. concurrency: 6 x 0.08s jobs complete in < 0.4s (median of 5 after warmup)
  5. cancellation: [4s doomed job, immediate DataError] batch completes in
     < 1.5s (median of 5 after warmup) with failed_indexes == [1]
  6. no leaked pending tasks / 'Task was destroyed but it is pending' /
     'coroutine was never awaited' on any scenario
The verifier supplies its own duck-typed job fixtures (same `execute()`
interface as batch.Job), so fixture timing cannot be altered by editing the
Job class.
"""
import asyncio
import gc
import io
import json
import math
import os
import statistics
import sys
import time
from contextlib import redirect_stderr

sys.path.insert(0, os.getcwd())

PASS = True
CANCEL_THRESHOLD = 1.5    # seconds; a correct batch aborts in ~0.1s
PARALLEL_THRESHOLD = 0.4  # seconds; 6 x 0.08s jobs, parallel ~0.1s, sequential 0.48s
TIMING_RUNS = 5


def fail(msg: str):
    global PASS
    PASS = False
    print(f"FAIL: {msg}", file=sys.stderr)


try:
    import batch
except Exception as e:  # noqa: BLE001
    fail(f"batch.py does not import: {e}")
    print("METRICS " + json.dumps({"pass": 0, "wall_time_s": None}))
    sys.exit(1)

if sys.version_info < (3, 11):
    fail("need Python 3.11+")


class VJob:
    """Duck-typed job fixture: same public interface as batch.Job."""

    def __init__(self, name, result=0, duration=0.0, fails=False):
        self.name = name
        self.result = result
        self.duration = duration
        self.fails = fails

    async def execute(self):
        if self.fails:
            raise batch.DataError(f"job {self.name!r}: malformed payload")
        steps = max(1, round(self.duration / 0.02))
        for _ in range(steps):
            await asyncio.sleep(0.02)
        return self.result


def jobs_success():
    return [
        VJob("a", result=10, duration=0.06),
        VJob("b", result=11, duration=0.02),
        VJob("c", result=12, duration=0.04),
        VJob("d", result=13, duration=0.02),
    ]


def jobs_single_fail():
    return [
        VJob("a", result=1, duration=0.05),
        VJob("b", result=2, duration=0.05),
        VJob("bad", fails=True),
        VJob("d", result=4, duration=0.05),
    ]


def jobs_multi_fail():
    return [
        VJob("bad0", fails=True),
        VJob("a", result=1, duration=0.05),
        VJob("bad2", fails=True),
        VJob("b", result=2, duration=0.05),
        VJob("bad4", fails=True),
    ]


def jobs_parallel():
    return [VJob(f"p{i}", result=100 + i, duration=0.08) for i in range(6)]


def jobs_doomed():
    return [
        VJob("doomed", result=0, duration=4.0),
        VJob("bad", fails=True),
    ]


async def run_once(jobs):
    """Run run_batch once; return (wall, kind, payload, leftovers)."""
    t0 = time.perf_counter()
    try:
        res = await batch.run_batch(list(jobs))
        kind, payload = "ok", res
    except BaseException as e:  # noqa: BLE001
        kind, payload = "fail", e
    wall = time.perf_counter() - t0
    leftovers = [t for t in asyncio.all_tasks()
                 if t is not asyncio.current_task() and not t.done()]
    return wall, kind, payload, leftovers


def run_async(coro_fn):
    """asyncio.run with stderr capture; flags leaked-task warnings."""
    err = io.StringIO()
    with redirect_stderr(err):
        asyncio.run(coro_fn())
        gc.collect()
    text = err.getvalue()
    if "Task was destroyed but it is pending" in text:
        fail("event loop warned 'Task was destroyed but it is pending'")
    if "coroutine was never awaited" in text:
        fail("a coroutine created by run_batch was never awaited")


def check_failure(payload, leftovers, expected_indexes, label):
    if isinstance(payload, BaseExceptionGroup):
        fail(f"{label}: raw exception group escaped instead of BatchFailed: {payload!r}")
        return
    if not isinstance(payload, batch.BatchFailed):
        fail(f"{label}: expected BatchFailed, got {type(payload).__name__}: {payload!r}")
        return
    idx = getattr(payload, "failed_indexes", None)
    if idx != expected_indexes:
        fail(f"{label}: failed_indexes={idx!r}, expected {expected_indexes!r}")
    if not isinstance(idx, list) or not all(isinstance(i, int) for i in (idx or [])):
        fail(f"{label}: failed_indexes must be a list of ints, got {type(idx).__name__}")
    if leftovers:
        fail(f"{label}: {len(leftovers)} pending task(s) left after run_batch raised")


def check_success(payload, leftovers, expected_results, label):
    if not isinstance(payload, list):
        fail(f"{label}: expected list of results, got {type(payload).__name__}: {payload!r}")
        return
    if payload != expected_results:
        fail(f"{label}: results {payload!r} != expected {expected_results!r} "
             "(order must match input jobs)")
    if leftovers:
        fail(f"{label}: {len(leftovers)} pending task(s) left after run_batch returned")


def capture_run(factory, checker, label):
    """Run one scenario under asyncio.run with stderr capture, then check it."""
    box = {}

    async def body():
        box["res"] = await run_once(factory())

    run_async(body)
    _, kind, payload, left = box["res"]
    checker(kind, payload, left, label)


def expect_ok(expected_results, label):
    def checker(kind, payload, left, lab):
        if kind != "ok":
            fail(f"{lab}: expected success, batch failed with {payload!r}")
        else:
            check_success(payload, left, expected_results, lab)
    return checker


def expect_failure(expected_indexes, label):
    def checker(kind, payload, left, lab):
        if kind != "fail":
            fail(f"{lab}: expected BatchFailed, batch returned {payload!r}")
        else:
            check_failure(payload, left, expected_indexes, lab)
    return checker


def timing_case(factory, out, key, kind_expected, payload_ok, label):
    async def body():
        await run_once(factory())  # warmup
        walls = []
        for _ in range(TIMING_RUNS):
            w, kind, payload, left = await run_once(factory())
            walls.append(w)
            if kind != kind_expected:
                fail(f"{label}: expected {kind_expected} during timing run, got "
                     f"{kind} {payload!r}")
            elif payload_ok is not None and not payload_ok(payload):
                fail(f"{label}: unexpected payload during timing run: {payload!r}")
            if left:
                fail(f"{label}: pending tasks left during timing run")
        out[key] = statistics.median(walls)

    run_async(body)


def main():
    # 1-3: behavioral identity
    capture_run(jobs_success, expect_ok([10, 11, 12, 13], "success-order"), "success-order")
    capture_run(jobs_single_fail, expect_failure([2], "single-fail"), "single-fail")
    capture_run(jobs_multi_fail, expect_failure([0, 2, 4], "multi-fail"), "multi-fail")

    # 4: concurrency timing (median of 5 after warmup)
    out = {}
    timing_case(jobs_parallel, out, "parallel", "ok",
                lambda p: p == [100 + i for i in range(6)], "parallel-timing")
    parallel_s = out.get("parallel")
    if parallel_s is None:
        fail("parallel timing did not run")
    elif parallel_s >= PARALLEL_THRESHOLD:
        fail(f"6 x 0.08s jobs took {parallel_s:.2f}s median (need < {PARALLEL_THRESHOLD}s); "
             "jobs are not running concurrently")



    # 5: cancellation timing (median of 5 after warmup)
    out2 = {}
    timing_case(jobs_doomed, out2, "cancel", "fail",
                lambda p: isinstance(p, batch.BatchFailed)
                and getattr(p, "failed_indexes", None) == [1],
                "cancel-timing")
    cancel_s = out2.get("cancel")
    if cancel_s is None:
        fail("cancellation timing did not run")
    elif cancel_s >= CANCEL_THRESHOLD:
        fail(f"batch with one immediate failure and one 4s job took {cancel_s:.2f}s median "
             f"(need < {CANCEL_THRESHOLD}s); still-running jobs were not stopped promptly")

    print("METRICS " + json.dumps({
        "pass": int(PASS),
        "wall_time_s": quantize(cancel_s) if cancel_s is not None else None,
    }))
    return 0 if PASS else 1


def quantize(seconds: float) -> float:
    """Ceiling to 0.1s: stable across runs, still separates ~0.05s from 4s."""
    return math.ceil(seconds * 10) / 10


if __name__ == "__main__":
    sys.exit(main())
