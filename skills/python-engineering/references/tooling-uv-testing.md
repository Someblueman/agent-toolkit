# Tooling, uv, & Testing

Read this when configuring Python project dependencies with `uv`, setting up `pyproject.toml`, configuring `ruff` and `mypy`/`pyright`, writing fast high-signal `pytest` test suites, or running Tier 1 Fast-Path test commands.

## The Modern `uv` Toolchain

`uv` is the standard fast Python package and project manager. It replaces `pip`, `pip-tools`, `poetry`, `pipenv`, and `virtualenv` with a single unified, deterministic CLI written in Rust.

### Daily `uv` Command Recipes

| Task | Command | Description |
|---|---|---|
| **Run Command in venv** | `uv run <command>` | Runs executable in managed virtual environment (auto-creates venv if needed) |
| **Add Dependency** | `uv add fastapi httpx` | Adds packages to `pyproject.toml` and updates `uv.lock` |
| **Add Dev Dependency** | `uv add --dev pytest ruff mypy` | Adds development / testing dependencies |
| **Sync Environment** | `uv sync` | Deterministically syncs venv to match `uv.lock` |
| **Upgrade Lockfile** | `uv lock --upgrade` | Upgrades all dependencies within version constraints |
| **Ephemeral Tool Run** | `uvx ruff check .` | Runs a tool without installing it into the local project venv |

---

## Centralized `pyproject.toml` Blueprint

Use a single `pyproject.toml` file to configure metadata, dependencies, linters, typecheckers, and test runners.

```toml
[project]
name = "my-service"
version = "0.1.0"
description = "High performance Python backend service"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27.0",
    "pydantic>=2.7.0",
]

[dependency-groups]
dev = [
    "mypy>=1.10.0",
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.4.0",
]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = [
    "E",     # pycodestyle errors
    "W",     # pycodestyle warnings
    "F",     # Pyflakes
    "I",     # isort
    "B",     # flake8-bugbear
    "UP",    # pyupgrade (modernize syntax)
    "SIM",   # flake8-simplify
    "ASYNC", # flake8-async
    "TCH",   # flake8-type-checking
]
ignore = ["E501"]  # Line length handled by formatter

[tool.mypy]
python_version = "3.11"
strict = true
disallow_untyped_defs = true
warn_unused_ignores = true
warn_redundant_casts = true
warn_return_any = true

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "integration: Integration tests requiring external services",
    "slow: Benchmarks and long-running tests",
]
```

---

## Fast-Path Verification Recipes

Calibrate verification effort strictly to the scope of your changes.

### Tier 1: Fast-Path Commands (Targeted Edits & Minor Bug Fixes)

```bash
# 1. Run a single targeted test function
uv run pytest tests/unit/test_auth.py -k "test_login_success"

# 2. Run tests in a single file
uv run pytest tests/unit/test_auth.py

# 3. Fail fast on first test failure
uv run pytest tests/ -x

# 4. Re-run only the tests that failed in the previous run
uv run pytest --lf

# 5. Run previously failed tests first, then remaining tests
uv run pytest --ff

# 6. Skip slow/integration test suites
uv run pytest -m "not integration and not slow"

# 7. Targeted typecheck on single modified file
uv run mypy src/package/auth.py

# 8. Targeted lint and format check on single modified file
uv run ruff check src/package/auth.py && uv run ruff format --check src/package/auth.py
```

### Tier 2: Full Verification (Architectural Changes, Schema Migrations, Release Gates)

```bash
# 1. Full workspace test suite with coverage
uv run pytest --cov=src --cov-report=term-missing

# 2. Full workspace strict static type check
uv run mypy src/

# 3. Full workspace lint and format check
uv run ruff check src/ && uv run ruff format --check src/
```

---

## Pragmatic Testing: Anti-Mock Sprawl & Table-Driven Tests

### Testing Principles
1. **Test Behavior, Not Implementation**: Verify inputs and return values/side-effects. Do not assert on private internal method call counts.
2. **Anti-Mock Sprawl**: Avoid deep `unittest.mock.patch()` chains that mock out the entire universe. Use simple concrete in-memory doubles or test real concrete classes.
3. **Table-Driven Parametrization**: Use `@pytest.mark.parametrize` to test multiple edge cases with clean, readable data tables.

### ❌ ANTI-PATTERN: Brittle Mock Spaghetti

```python
# BAD: 5 mock layers testing internal implementation details rather than behavior
from unittest.mock import patch, MagicMock

def test_calculate_discount():
    with patch("myapp.service.UserRepository") as mock_user_repo:
        with patch("myapp.service.PricingEngine") as mock_pricing:
            mock_user = MagicMock()
            mock_user.is_vip = True
            mock_user_repo.return_value.get_user.return_value = mock_user
            mock_pricing.return_value.get_rate.return_value = 0.8
            
            # Brittle test tightly coupled to exact internal call sequences
            discount = apply_discount("u123", 100.0)
            assert discount == 80.0
            mock_pricing.return_value.get_rate.assert_called_once()
```

### ✅ PRAGMATIC: Table-Driven Parametrized Tests with Concrete Logic

```python
# GOOD: Clean table-driven test testing pure domain behavior
from __future__ import annotations
from decimal import Decimal
import pytest

@pytest.mark.parametrize(
    ("is_vip", "cart_total", "expected_total"),
    [
        (False, Decimal("100.00"), Decimal("100.00")),
        (True, Decimal("100.00"), Decimal("80.00")),     # 20% VIP discount
        (True, Decimal("0.00"), Decimal("0.00")),         # Zero amount boundary
        (False, Decimal("500.00"), Decimal("450.00")),   # 10% bulk discount
    ],
)
def test_calculate_discount_behavior(
    is_vip: bool,
    cart_total: Decimal,
    expected_total: Decimal,
) -> None:
    result = calculate_final_price(is_vip=is_vip, total=cart_total)
    assert result == expected_total
```
