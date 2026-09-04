---
name: python-engineering
description: Implement, review, debug, and optimize Python codebases (Python 3.10+). Use for Python architecture, FastAPI/Flask/Django APIs, asyncio and structured concurrency, Pydantic v2/msgspec/dataclasses, uv workflows, pytest test recipes, strict static typing (mypy/pyright), performance profiling (cProfile/py-spy), and CPython optimization. Do not use for non-Python work.
---

# Python Engineering

Produce the smallest correct Python change or the focused review the user requested. Preserve project policy, make costs and invariants visible, and support completion claims with proportionate evidence.

## Start with the repository

1. Read applicable repository instructions and inspect worktree/branch status, the current diff, relevant `pyproject.toml`, `uv.lock`, or `requirements.txt` files, CI configuration, and nearby code or tests. Preserve unrelated and pre-existing changes. Cap pre-flight inspection to 3-5 directly relevant files.
2. Identify whether the request is implementation, diagnosis, review, API design, performance work, or project tooling. A review or diagnosis does not authorize edits.
3. Existing repository choices win. Do not change Python versions, dependencies, linters, type-checking strictness, or formatting configurations unless the request requires it.
4. For a new Python module or project, target Python 3.10+ baseline (utilizing PEP 604 union syntax `X | Y`, `from __future__ import annotations`, and Python 3.11 `asyncio.TaskGroup` where available).
5. Read only the references routed below that match the task.

## Cross-cutting rules

- **Concrete-First Architecture**: Write concrete functions, modules, and classes first. Prefer flat module hierarchies and pure functions over multi-layered class hierarchies (`BaseManager -> AbstractUserManager -> ConcreteUserManager -> CachedUserManager`).
- Prefer concrete code; introduce an abstraction when it simplifies a current requirement or expresses a necessary boundary or invariant.
- **Anti-Mock Sprawl**: Never extract single-implementation Protocols or abstract classes solely to generate test doubles with `unittest.mock.MagicMock`. Test concrete classes directly or use simple concrete in-memory doubles.
- Choose direct construction, constructors or builders according to validation needs and call-site clarity, not field count.
- **Single-Path Execution & Atomic In-Place Refactoring**: When modifying functions, methods, or models, cleanly update all call sites, internal usages, and tests in the same change wave. Forbid legacy retention anti-patterns:
  - *Shim Multiplication*: Keeping deprecated functions as pass-through forwarding wrappers (`def old_fn(*args): warnings.warn(...); return new_fn(*args)`).
  - *Dual-Format Fallbacks & Zombie Decoders*: Retaining obsolete dictionary key fallbacks (`if "old_key" in data: ...`) or dual serializers without explicit requirement.
  - *Ghost Code*: Commenting out old implementations or parking dead code in `_legacy.py` files.
  - *Preemptive Deprecation Staging*: Adding `@deprecated` decorators or staged migration scaffolding when an immediate clean replacement is feasible.
- **Trust Boundary Validation**: Validate all untrusted input (HTTP requests, CLI args, environment variables, message queues, JSON payloads) at network and process boundaries using the repository's existing validators or focused explicit checks. Pydantic/msgspec can help complex boundaries but are not mandatory dependencies. Internally, use clear typed domain values.
- **Async Concurrency Discipline**: Never block the asyncio event loop with synchronous I/O, synchronous database drivers, or `time.sleep()`. Use `await asyncio.sleep()`, async network clients (`httpx.AsyncClient`), or offload unavoidable blocking I/O via `await asyncio.to_thread()`. Use `asyncio.TaskGroup` on Python 3.11+ for structured concurrency; on 3.10 use the repository's established task ownership and cancellation pattern; ban unmonitored fire-and-forget `asyncio.create_task()`.
- **Explicit Error Hierarchies**: Introduce domain exceptions when callers need to distinguish them; standard exceptions often suffice. Preserve causal context when wrapping errors using `raise DomainError(...) from err`. Never swallow exceptions with bare `except:` or `except Exception: pass`.
- **Modern Static Typing**: Follow the project's annotation-evaluation conventions. Use native union types (`str | None`, `int | float`), generic builtins (`list[T]`, `dict[K, V]`), and `typing.Self` on 3.11+ (existing TypeVar or typing_extensions on 3.10) for method chaining.

## Verification

Discover and follow the repository's own commands first. Match validation scope to the change and widen it when risk warrants:

1. **Tier 1 (Fast-Path)**: For bug fixes, localized refactors, minor features, internal helpers, documentation, or config edits, run targeted commands on the affected module:
   - Targeted unit test filter: `uv run pytest tests/unit/test_module.py -k "test_target_name"`
   - Targeted test file: `uv run pytest tests/unit/test_module.py`
   - Fast failure: `uv run pytest tests/ -x --ff`
   - Targeted typecheck: `uv run mypy src/package/module.py` (or `uv run pyright src/package/module.py`)
   - Targeted lint/format: `uv run ruff check src/package/module.py && uv run ruff format --check src/package/module.py`
2. **Tier 2 (Full Verification)**: For core architectural modifications, public API contracts, data schema migrations, or release gates, run full workspace verification:
   - Full workspace test suite: `uv run pytest --cov=src`
   - Full workspace typecheck: `uv run mypy src/` (or `uv run pyright`)
   - Strict workspace lint: `uv run ruff check src/ && uv run ruff format --check src/`
3. Do not hide a pre-existing failure by changing unrelated code. Report the exact command, whether it passed, and any baseline or environmental blocker.

## References

- API design, anti-OOP bloat, Concrete-First Design for Protocols, banning builders, dataclasses vs TypedDict vs Pydantic: read [references/api-design-antipatterns.md](references/api-design-antipatterns.md).
- Python 3.10+ static typing, trust boundary validation (Pydantic v2 / msgspec), wire schemas, serialization edge cases, and error hierarchies: read [references/types-data-contracts.md](references/types-data-contracts.md).
- `asyncio` task lifecycles, structured concurrency (`TaskGroup`), thread pools (`ThreadPoolExecutor` / `asyncio.to_thread`), multiprocessing, and cancellation safety: read [references/async-concurrency.md](references/async-concurrency.md).
- CPython runtime optimization, memory layout (`__slots__`, NumPy/Polars), GIL boundaries, and profiling (`cProfile`, `py-spy`, `line_profiler`): read [references/performance-profiling.md](references/performance-profiling.md).
- Modern `uv` workflows (`pyproject.toml`, `uv run`), `ruff` linting/formatting, strict `mypy`/`pyright`, and Fast-Path `pytest` test filtering recipes: read [references/tooling-uv-testing.md](references/tooling-uv-testing.md).

When several areas interact, read the smallest combination that covers the decision. Do not load every reference for a routine edit.
