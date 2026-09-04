# Async & Concurrency

Read this when writing asynchronous Python code, managing event loop lifecycles, using `asyncio`, coordinating threads or worker processes, handling task cancellation, or preventing blocking operations on the event loop.

## The Asyncio Concurrency Model

Python\x27s `asyncio` uses a single-threaded cooperative multitasking event loop. An `await` expression yields control back to the event loop. If an `async def` function executes synchronous blocking code, the entire event loop halts, starving all other concurrent coroutines.

### Concurrency Primitives Decision Rubric

| Concurrency Primitive | Use Case | GIL Interaction | Failure Boundary |
|---|---|---|---|
| **`asyncio.TaskGroup`** (Python 3.11+) | Concurrent I/O tasks with structured lifecycles | Single thread (cooperative) | If one child fails, all siblings are cancelled; raises `ExceptionGroup` |
| **`asyncio.to_thread`** / `ThreadPoolExecutor` | Unavoidable blocking synchronous I/O (legacy SDKs, disk files) | Threads run in CPython runtime, GIL released during C/system I/O | Individual thread exceptions propagate upon `await` |
| **`ProcessPoolExecutor`** | CPU-intensive computation (cryptography, image processing, heavy parsing) | Bypasses GIL completely via separate OS processes | Process crashes or returns unpicklable exceptions |

---

## Structured Concurrency with `asyncio.TaskGroup` (Python 3.11+)

TaskGroup examples require Python 3.11+. For a 3.10 target, retain its established lifecycle/cancellation approach rather than adding an unrequested compatibility layer. Threads primarily help blocking I/O; pure Python CPU work generally needs processes or native code that releases the GIL.

Structured concurrency guarantees that concurrent subtasks have a bounded lifetime tied to a lexical block. When the block exits, all tasks are completed, cancelled, or handled.

### Task Management Rules
1. **Ban Fire-and-Forget `asyncio.create_task()`**: Launching unmonitored tasks into the background causes:
   - Swallowed exceptions (lost until task GC).
   - Silent task garbage collection mid-execution.
   - Zombie coroutines lingering after parent requests finish.
2. **Use `asyncio.TaskGroup` on 3.11+**: Use `async with asyncio.TaskGroup() as tg:` to spawn child tasks.
3. **Handle `ExceptionGroup` with `except*`**: In Python 3.11+, catch multiple concurrent exceptions using `except* ExceptionType:`.

### ❌ ANTI-PATTERN: Unmonitored Fire-and-Forget Tasks

```python
# BAD: Unmonitored create_task, swallowed exceptions, no cancellation propagation
import asyncio

async def fetch_user_data(user_id: str) -> None:
    # If this raises an exception, it is unhandled until GC, corrupting state
    asyncio.create_task(send_analytics(user_id))
    asyncio.create_task(update_cache(user_id))

async def send_analytics(user_id: str) -> None:
    raise ConnectionError("Analytics service down")  # Silently lost!
```

### ✅ PRAGMATIC: Structured Concurrency with `TaskGroup`

```python
# GOOD: Clean structured concurrency with TaskGroup and ExceptionGroup handling
from __future__ import annotations
import asyncio
import logging

logger = logging.getLogger(__name__)

async def update_cache(user_id: str) -> None:
    await asyncio.sleep(0.05)

async def send_analytics(user_id: str) -> None:
    await asyncio.sleep(0.05)

async def fetch_user_data(user_id: str) -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(send_analytics(user_id))
            tg.create_task(update_cache(user_id))
    except* ConnectionError as eg:
        logger.warning("Non-fatal network error during analytics sync: %s", eg.exceptions)
```

---

## Avoiding Event Loop Blockages

Any call that blocks the thread for more than a few milliseconds without `await` is a bug in an `asyncio` service.

### Banned Blocking Operations in `async def`

| Category | ❌ Banned Blocking Call | ✅ Async / Non-Blocking Replacement |
|---|---|---|
| **Sleeping** | `time.sleep(n)` | `await asyncio.sleep(n)` |
| **HTTP Requests** | `requests.get(...)`, `urllib.request` | `await client.get(...)` (`httpx.AsyncClient`, `aiohttp`) |
| **File I/O** | Standard `open()`, `path.read_text()` | `await asyncio.to_thread(path.read_text)` or `aiofiles` |
| **Database** | Synchronous `psycopg2`, `sqlite3` | `asyncpg`, `aiosqlite`, SQLAlchemy async engine |
| **Heavy CPU** | `bcrypt.hashpw(...)`, multi-MB JSON | `await asyncio.to_thread(bcrypt.hashpw, ...)` or `ProcessPoolExecutor` |

### ❌ ANTI-PATTERN: Blocking I/O Inside Coroutine

```python
# BAD: Synchronous requests.get freezes the entire asyncio worker process
import time
import requests

async def process_webhook(url: str) -> dict:
    time.sleep(1.0)  # Freezes all concurrent requests for 1 second!
    response = requests.get(url, timeout=5.0)  # Blocking socket I/O
    return response.json()
```

### ✅ PRAGMATIC: Async Client or Explicit Thread Offload

```python
# GOOD: Using httpx.AsyncClient or offloading unavoidable sync libraries
from __future__ import annotations
import asyncio
import httpx

# Option 1: Native async HTTP client
async def process_webhook(client: httpx.AsyncClient, url: str) -> dict:
    await asyncio.sleep(1.0)  # Non-blocking yield
    response = await client.get(url, timeout=5.0)
    response.raise_for_status()
    return response.json()

# Option 2: Offloading unavoidable legacy synchronous blocking calls
def legacy_sync_crypto(data: bytes) -> bytes:
    import hashlib
    # CPU heavy computation
    return hashlib.pbkdf2_hmac("sha256", data, b"salt", 200_000)

async def compute_hash_safe(data: bytes) -> bytes:
    return await asyncio.to_thread(legacy_sync_crypto, data)
```

---

## Cancellation Safety & Resource Cleanup

In asyncio, a task can be cancelled at any `await` suspension point when `task.cancel()` is invoked or when a sibling task in a `TaskGroup` raises an exception.

### Cancellation Invariants
1. **Always Handle `asyncio.CancelledError`**: If caught, always re-raise `CancelledError` unless intentionally consuming the cancellation at the top-level orchestrator.
2. **Deterministic Cleanup with `finally:`**: Always place resource cleanup (closing file handles, releasing locks, rolling back transactions) inside `try ... finally:` or use async context managers (`async with`).
3. **Protect Critical Sections with `asyncio.shield()`**: For non-cancellable operations (e.g. committing a database transaction after external payment processing), wrap the operation with `asyncio.shield()`.

### Code Example: Cancellation Safety & Resource Release

```python
from __future__ import annotations
import asyncio
import logging

logger = logging.getLogger(__name__)

async def transfer_funds(source_id: str, dest_id: str, amount: float) -> None:
    lock = asyncio.Lock()
    await lock.acquire()
    try:
        await debit_account(source_id, amount)
        # Shield critical commit phase from cancellation
        await asyncio.shield(commit_transaction(source_id, dest_id, amount))
    except asyncio.CancelledError:
        logger.info("Transfer cancelled; executing rollback for source %s", source_id)
        await rollback_debit(source_id, amount)
        raise  # Mandatory: Re-raise CancelledError
    finally:
        lock.release()
```

---

## Bounded Concurrency with `asyncio.Semaphore`

Unbounded concurrent requests to downstream databases or APIs cause connection pool exhaustion, socket starvation, and rate-limit bans (HTTP 429).

```python
from __future__ import annotations
import asyncio
import httpx

async def fetch_item(client: httpx.AsyncClient, sem: asyncio.Semaphore, item_id: int) -> dict:
    async with sem:  # Limits concurrent outbound connections to 10
        response = await client.get(f"https://api.example.com/items/{item_id}")
        response.raise_for_status()
        return response.json()

async def fetch_all_items(item_ids: list[int]) -> list[dict]:
    sem = asyncio.Semaphore(10)  # Bounded concurrency limit
    async with httpx.AsyncClient() as client:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(fetch_item(client, sem, item_id)) for item_id in item_ids]
        return [task.result() for task in tasks]
```
