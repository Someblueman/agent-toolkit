"""Authentication worker.

`authenticate(user_id)` returns a deterministic token for the user:
sha256 chained 30_000 times over the utf-8 bytes of user_id, hex-encoded,
first 16 chars. Concurrency semantics matter: see the task.
"""
import hashlib
import time


def _derive_token(user_id: str) -> str:
    h = user_id.encode("utf-8")
    for _ in range(30_000):
        h = hashlib.sha256(h).digest()
    return h.hex()[:16]


async def authenticate(user_id: str) -> str:
    # TODO(service): this endpoint is slow under load; ops wants 40 concurrent
    # logins to finish in under 3 seconds total (currently ~5s) AND the event
    # loop must stay responsive while logins are in flight. Returned tokens
    # must stay byte-identical.
    time.sleep(0.1)  # simulates a blocking call to the session store
    return _derive_token(user_id)
