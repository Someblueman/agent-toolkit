# Types & Data Contracts

Read this when designing type-safe architectures, defining schemas, parsing untrusted data, working with static typecheckers (`mypy`, `pyright`), designing domain error hierarchies, or handling serialization edge cases in Python 3.10+.

## Python 3.10+ Static Typing Foundations

Always include `from __future__ import annotations` as the first line of every Python module. This defers type evaluation, prevents circular import issues with type annotations, and eliminates runtime evaluation overhead for complex type signatures.

### Modern Type Syntax Checklist

| Feature | Python 3.10+ Idiom | Legacy / Banned Syntax |
|---|---|---|
| **Union Types** | `int | str`, `str | None` | `Union[int, str]`, `Optional[str]` |
| **Generic Collections** | `list[str]`, `dict[str, int]`, `set[int]`, `tuple[int, ...]` | `typing.List`, `typing.Dict`, `typing.Set`, `typing.Tuple` |
| **Callable Signatures** | `collections.abc.Callable[[int, str], bool]` | `typing.Callable[[int, str], bool]` |
| **Self Referencing** | `def clone(self) -> Self:` (`typing.Self`) | `def clone(self: T) -> T:` (verbose TypeVar) |
| **Type Narrowing** | `def is_valid(x: object) -> TypeIs[str]:` (`typing.TypeIs`) | Brittle runtime `isinstance` checks without type narrowing |
| **Exhaustiveness** | `assert_never(val)` (`typing.Never`, `typing.assert_never`) | `raise NotImplementedError("unhandled")` |

---

## Trust Boundary Transitions

Codebases fail when untrusted data (HTTP request payloads, query params, CLI flags, external API responses, message queue bodies) is passed into core domain logic as raw `dict[str, Any]` objects.

### The Trust Boundary Flow

```text
+-----------------------+     Validation Boundary     +---------------------------+
| Untrusted Wire Data   |  ========================>  | Typed Domain Entity       |
| (JSON / Dict / Bytes) |   Pydantic v2 / msgspec     | @dataclass(slots=True)    |
+-----------------------+                             +---------------------------+
```

### Trust Boundary Rules
1. **Never leak raw dicts past the boundary**: Parse and validate untrusted data at the perimeter (HTTP handler, CLI parser, queue listener).
2. **Enforce Strictness at the Edge**: In Pydantic v2, configure `model_config = ConfigDict(strict=True, extra="forbid")` to reject unknown fields and avoid unintended type coercion (e.g. converting string `"123"` to integer `123` silently).
3. **Monomorphic Internal Types**: Internal services and domain algorithms receive typed domain models (`@dataclass(slots=True)`), never Pydantic models or raw dictionaries.

### ❌ ANTI-PATTERN: Raw Dict Passing & Brittle Subscripting

```python
# BAD: Raw dictionary passing across service layers
def handle_http_request(request_body: dict[str, object]) -> None:
    process_order(request_body)

def process_order(data: dict[str, object]) -> None:
    # Brittle subscripting, no type safety, KeyError runtime crashes
    user_id = str(data["user_id"])
    amount = float(data["amount"])  # Floating point precision risk
    execute_charge(user_id, amount)
```

### ✅ PRAGMATIC: Strict Perimeter Validation & Clean Typed Domain Entity

```python
# GOOD: Validated at perimeter into strict Pydantic model, then converted to typed domain entity
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

# 1. Perimeter Schema
class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: UUID
    amount: Decimal = Field(gt=Decimal("0.00"), decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)

# 2. Core Domain Entity
@dataclass(slots=True, kw_only=True)
class Order:
    user_id: UUID
    amount: Decimal
    currency: str

# 3. Perimeter Handler
def handle_http_request(payload: bytes) -> None:
    # Validates input strictly at boundary
    req = CreateOrderRequest.model_validate_json(payload)
    order = Order(user_id=req.user_id, amount=req.amount, currency=req.currency)
    process_order(order)

# 4. Pure Domain Logic
def process_order(order: Order) -> None:
    execute_charge(order.user_id, order.amount, order.currency)
```

---

## Rich Domain Types & Serialization Edge Cases

Use specific, rich types rather than generic primitives to make invalid states unrepresentable.

### Domain Type Discipline

1. **Datetimes & Timezones**:
   - Always use timezone-aware `datetime.datetime` with `datetime.timezone.utc`.
   - Never call `datetime.now()` without a timezone parameter (naive datetimes cause catastrophic time drift and parsing bugs).
   - *Idiom*: `datetime.now(timezone.utc)`.
2. **Monetary & Exact Arithmetic**:
   - Always use `decimal.Decimal` for currency and financial calculations.
   - Never use `float` (IEEE 754 floats introduce rounding errors like `0.1 + 0.2 == 0.30000000000000004`).
3. **Identifiers**:
   - Use `uuid.UUID` for unique identifiers to prevent string injection and malformed IDs.
4. **Domain Enums**:
   - Use `enum.StrEnum` (Python 3.11+) or `enum.Enum` for constrained sets of domain states.

### Exhaustive Pattern Matching

Use Python 3.10+ `match/case` with `typing.assert_never` to enforce compile-time exhaustive checking when handling domain enums or union variants.

```python
from __future__ import annotations
from enum import StrEnum
from typing import assert_never

class OrderStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

def get_next_action(status: OrderStatus) -> str:
    match status:
        case OrderStatus.PENDING:
            return "send_payment_link"
        case OrderStatus.PROCESSING:
            return "poll_payment_gateway"
        case OrderStatus.COMPLETED:
            return "send_receipt"
        case OrderStatus.FAILED:
            return "notify_failure"
        case _ as unreachable:
            assert_never(unreachable)  # Mypy/Pyright fails if any variant is unhandled
```

---

## Explicit Domain Error Hierarchies

A well-structured exception hierarchy allows callers to catch and handle specific operational failures without catching unrelated programming bugs.

### Exception Design Rules
1. **Inherit from `Exception`**: Never inherit domain exceptions from `BaseException` (which catches `KeyboardInterrupt` and `SystemExit`).
2. **Domain-Specific Base Class**: Define a common base class for each module or application (e.g. `DomainError` or `AppError`).
3. **Preserve Root Causes**: Always use `raise CustomError(...) from original_error` to maintain the full traceback chain.
4. **Ban Swallowing Exceptions**: Never use bare `except:` or `except Exception: pass`.

### ❌ ANTI-PATTERN: Swallowing Exceptions & Unstructured Errors

```python
# BAD: Swallowing exceptions, bare exceptions, loss of context
def fetch_user_balance(user_id: str) -> float:
    try:
        data = db.query("SELECT balance FROM users WHERE id = " + user_id)
        return float(data[0])
    except:  # Swallows syntax errors, KeyboardInterrupt, memory errors
        return 0.0
```

### ✅ PRAGMATIC: Structured Exception Hierarchy with Cause Chaining

```python
# GOOD: Explicit hierarchy with preserved exception chaining
from __future__ import annotations
from decimal import Decimal
from uuid import UUID

class AppError(Exception):
    pass

class ResourceNotFoundError(AppError):
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(f"{resource} with id '{identifier}' was not found.")
        self.resource = resource
        self.identifier = identifier

class DatabaseQueryError(AppError):
    pass

def fetch_user_balance(user_id: UUID) -> Decimal:
    try:
        record = db.find_user(user_id)
        if record is None:
            raise ResourceNotFoundError("User", str(user_id))
        return record.balance
    except DatabaseDriverException as err:
        raise DatabaseQueryError(f"Failed to query balance for user {user_id}") from err
```
