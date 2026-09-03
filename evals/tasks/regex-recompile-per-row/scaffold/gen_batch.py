"""Generate a synthetic audit batch on stdout.

Usage: python3 gen_batch.py [n_rows] [seed]
"""
import random
import sys

WORDS = ("token rotated for device shard lease expired retry budget drained "
         "cache warm replica promoted queue drained ledger committed session "
         "refreshed scope narrowed probe attached snapshot sealed index rebuilt "
         "quota renewed throttle lifted backfill resumed shard migrated").split()
LEVELS = ["info", "warn", "error", "debug", "notice"]
SVCS = ["auth", "billing", "search", "ingest", "notify", "profile"]


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
    return rows


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 35000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    sys.stdout.write("\n".join(gen_rows(seed, n)) + "\n")
