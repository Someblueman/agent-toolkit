"""Mechanical scorer for py-async-endpoint. Prints METRICS {...}; exit 0 = pass."""
import asyncio
import hashlib
import json
import sys
import time

PASS = True


def fail(msg: str):
    global PASS
    PASS = False
    print(f"FAIL: {msg}", file=sys.stderr)


def ref_token(user_id: str) -> str:
    h = user_id.encode("utf-8")
    for _ in range(30_000):
        h = hashlib.sha256(h).digest()
    return h.hex()[:16]


def main():
    try:
        import worker
    except Exception as e:
        fail(f"worker.py does not import: {e}")
        print("METRICS " + json.dumps({"pass": 0, "wall_time_s": None,
                                       "max_loop_stall_s": None}))
        return 1

    users = [f"user-{i}" for i in range(40)]
    expect = [ref_token(u) for u in users]
    tokens: list[str] = []
    stalls: list[float] = []

    async def heartbeat():
        last = time.perf_counter()
        while True:
            await asyncio.sleep(0.05)
            now = time.perf_counter()
            stalls.append(now - last)
            last = now

    async def login_all():
        tokens.extend(await asyncio.gather(*(worker.authenticate(u) for u in users)))

    async def run():
        hb = asyncio.ensure_future(heartbeat())
        try:
            await asyncio.wait_for(login_all(), timeout=60)
            await asyncio.sleep(0.15)  # let heartbeat record any final stall gap
        finally:
            hb.cancel()

    t0 = time.perf_counter()
    try:
        asyncio.run(run())
    except Exception as e:
        fail(f"authenticate raised under concurrency: {e}")
        print("METRICS " + json.dumps({"pass": 0, "wall_time_s": None,
                                       "max_loop_stall_s": None}))
        return 1
    wall = time.perf_counter() - t0

    if tokens != expect:
        fail("returned tokens differ from the documented derivation")
    if wall >= 3.0:
        fail(f"40 concurrent calls took {wall:.2f}s (need < 3.0s)")
    max_stall = max(stalls) if stalls else 0.0
    if max_stall >= 0.5:
        fail(f"event loop stalled {max_stall:.2f}s (heartbeat gap >= 0.5s)")

    print("METRICS " + json.dumps({
        "pass": int(PASS),
        "wall_time_s": round(wall, 3),
        "max_loop_stall_s": round(max_stall, 3),
    }))
    return 0 if PASS else 1


if __name__ == "__main__":
    sys.exit(main())
