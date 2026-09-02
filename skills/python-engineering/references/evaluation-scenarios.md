# Skill Maintenance Evaluation Scenarios

These are behavioral regression test cases for maintainers of the Python engineering skill, not instructions to load for ordinary Python work. Run a representative subset through an independent agent in disposable workspaces after substantial edits. Judge decisions and artifacts, not exact wording.

## 1. Premature Protocol Abstraction & Mock Proliferation (Rule of Three)

**Request:** Refactor a concrete `UserRepository` class in a FastAPI application by extracting a `typing.Protocol`, converting the endpoint dependencies to accept the Protocol, and creating a `MockUserRepository` using `unittest.mock.MagicMock` to unit test 2 business logic functions.

**Accept when the response:**
- Enforces the Rule of Three for abstractions.
- Rejects speculative Protocol extraction when only one concrete repository exists in the repository.
- Avoids complex `MagicMock` setups that mock out internal method calls.
- Implements testing against the concrete repository directly or with a lightweight in-memory fake (`@dataclass InMemoryUserRepository`).

**Reject when it:**
- Encourages extracting single-implementation Protocols solely for mocking.
- Introduces speculative generic interfaces or multi-tier class hierarchies.
- Writes brittle mock assertion assertions (`mock.assert_called_once_with(...)`) that tie tests to internal implementation details.

---

## 2. Single-Path Refactoring vs Deprecated Forwarding Shims

**Request:** Refactor an internal domain function `calculate_tax(subtotal, rate)` to `calculate_total_with_tax(subtotal, tax_rate, currency="USD")`. The developer asks to keep `calculate_tax` as a forwarding wrapper that calls `warnings.warn(DeprecationWarning)` and parses legacy dictionary inputs with fallback keys `if "old_rate" in kwargs:`.

**Accept when the response:**
- Enforces single-path execution and clean in-place replacement.
- Rejects the `warnings.warn(DeprecationWarning)` forwarding wrapper in internal application code.
- Rejects zombie fallback dictionary key decoders.
- Atomically updates all internal call sites and unit tests in the same change wave.
- Deletes dead or commented-out code completely.

**Reject when it:**
- Retains legacy forwarding shim functions in internal application modules.
- Preserves dual-format serialization decoders without an external backward-compatibility requirement.
- Leaves ghost code, commented-out blocks, or `_legacy.py` files.

---

## 3. Async Event Loop Blockage & Concurrency Offloading

**Request:** Review a high-throughput FastAPI endpoint that executes `time.sleep(0.5)`, calls `requests.get("https://auth.internal/verify")`, and hashes passwords with `bcrypt.hashpw()` directly inside `async def authenticate_user(...)`.

**Accept when the response:**
- Correctly identifies that `time.sleep`, `requests.get`, and CPU-heavy `bcrypt.hashpw` block the single-threaded asyncio event loop.
- Replaces `time.sleep` with `await asyncio.sleep`.
- Replaces `requests.get` with `await client.get(...)` using `httpx.AsyncClient`.
- Offloads the CPU-heavy `bcrypt.hashpw` operation via `await asyncio.to_thread(bcrypt.hashpw, ...)`.

**Reject when it:**
- Fails to identify that synchronous I/O freezes the event loop for all concurrent requests.
- Suggests wrapping `requests.get` in `asyncio.create_task` (which still blocks the thread).
- Leaves blocking operations on the primary asyncio loop thread.

---

## 4. Trust Boundary Validation vs Raw Dict Passing

**Request:** Review a webhook ingestion service where JSON payloads received via HTTP POST are passed directly as `dict[str, Any]` across 4 service layers, subscripted with `payload["event"]["user"]["id"]`.

**Accept when the response:**
- Identifies the danger of untrusted raw dictionary passing across internal boundaries.
- Introduces strict Pydantic v2 `BaseModel` (with `model_config = ConfigDict(strict=True, extra="forbid")`) or `msgspec.Struct` validation at the perimeter.
- Converts validated input into strongly typed domain models (`@dataclass(slots=True)`) before passing to internal domain services.
- Eliminates brittle dictionary subscripting and potential `KeyError` crashes.

**Reject when it:**
- Suggests adding more `dict.get("key", default)` checks throughout downstream service layers.
- Allows raw untrusted dictionaries to traverse core domain logic.
- Uses loose validation without forbidding unknown fields or enforcing strict type coercion.

---

## 5. Memory Layout Optimization with `__slots__`

**Request:** Diagnose an out-of-memory (OOM) crash in a batch processing service that instantiates 10,000,000 instances of a standard Python class `class SensorReading:` holding 4 numeric fields.

**Accept when the response:**
- Explains CPython memory layout: standard class instances create `__dict__` and `__weakref__` (~152 bytes/instance), causing massive RAM overhead and GC pressure.
- Refactors the class to `@dataclass(slots=True)` (reducing memory to ~48 bytes/instance, ~70% reduction).
- Suggests NumPy or Polars columnar structures if the workload is purely numerical/tabular.
- Demonstrates memory measurement using `tracemalloc` before and after.

**Reject when it:**
- Suggests increasing OS swap or machine RAM without addressing the data layout inefficiency.
- Recommends manual `__slots__` tuple boilerplate when `@dataclass(slots=True)` is available.
- Fails to explain why `__slots__` reduces per-instance memory in CPython.

---

## 6. Fast-Path Test Invocation (Tier 1 vs Tier 2)

**Request:** A developer fixed a 1-line typo in `src/myapp/auth/token.py`. They ask what verification commands to execute before committing.

**Accept when the response:**
- Recommends targeted Tier 1 Fast-Path verification:
  - Single test function or file filter: `uv run pytest tests/unit/test_token.py -k "test_token_validation"`
  - Targeted type check: `uv run mypy src/myapp/auth/token.py`
  - Targeted lint/format check: `uv run ruff check src/myapp/auth/token.py && uv run ruff format --check src/myapp/auth/token.py`
- Avoids running slow, whole-workspace integration suites for a localized 1-line edit.

**Reject when it:**
- Suggests running heavy whole-workspace integration test suites or unneeded broad benchmarks for a localized single-file fix.
- Fails to provide copy-pasteable Fast-Path pytest filter flags (`-k`, specific file path).

---

## 7. Small Struct Builder Anti-Pattern (< 5 fields)

**Request:** A developer creates a 60-line `DatabaseConfigBuilder` class with `.with_host()`, `.with_port()`, `.with_username()`, and `.build()` methods to construct a 3-field `DatabaseConfig` object.

**Accept when the response:**
- Enforces the ban on small builder patterns for structs with fewer than 5 fields (< 5 fields).
- Replaces the verbose builder class with `@dataclass(slots=True, kw_only=True)` with default parameter values.
- Demonstrates direct instantiation at call sites with keyword arguments.

**Reject when it:**
- Praises the builder pattern as "clean enterprise architecture" for simple data classes.
- Retains both the builder class and the dataclass.

---

## 8. Structured Concurrency vs Unmonitored Fire-and-Forget Tasks

**Request:** An asynchronous background worker uses `asyncio.create_task(process_job(job_id))` in a loop without storing task references or handling task failures.

**Accept when the response:**
- Identifies the failure modes of unmonitored `create_task`: lost exceptions, mid-flight garbage collection, and lack of cancellation propagation.
- Refactors the worker to use `async with asyncio.TaskGroup() as tg:` with `tg.create_task()`.
- Implements proper `ExceptionGroup` handling (`except*`) and bounded concurrency using `asyncio.Semaphore`.

**Reject when it:**
- Approves fire-and-forget tasks without tracking lifecycles.
- Recommends `asyncio.gather(*tasks, return_exceptions=True)` without addressing structured cancellation boundaries.
