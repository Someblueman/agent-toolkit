# API Design & Anti-Patterns

Read this when designing Python modules, classes, functions, public interfaces, domain models, or refactoring existing Python codebases. Python excels when code is direct, readable, and concrete. Avoid importing enterprise OOP design patterns from Java or C++ that introduce accidental complexity, unnecessary indirection, and maintenance friction.

## Establish the Concrete Contract First

- **Concrete-First Design**: Start with concrete functions and data structures. Group related functions into modules rather than creating artificial "Service" or "Manager" classes that only contain static or stateless methods.
- **Flat Module Hierarchies**: Prefer shallow, cohesive directory layouts (e.g. `package/auth.py`, `package/storage.py`) over deeply nested directory trees (`package/services/impl/auth/v1/auth_service_impl.py`).
- **Pure Functions Over Class Wrappers**: If a class has only an `__init__` and a single method (e.g. `execute()` or `run()`), replace the entire class with a standalone top-level function.
- **Single-Path Execution & Atomic In-Place Refactoring**: Refactor internal code in place and atomically update all call sites, internal usages, and tests in the same change wave. Do not preserve backwards compatibility unless the repository or user explicitly requires it.

### Forbidden Legacy Retention Anti-Patterns

| Anti-Pattern | Description | Remediation |
|---|---|---|
| **Shim Multiplication** | Retaining deprecated functions as pass-through forwarding wrappers around new implementations (`def old_fn(*a, **kw): warnings.warn(...); return new_fn(*a, **kw)`). | Atomically update all call sites to call `new_fn()` and delete `old_fn()`. |
| **Dual-Format Decoders & Zombie Keys** | Retaining obsolete dictionary keys or payload fallbacks (`if "legacy_id" in data: id = data["legacy_id"]`). | Enforce the single canonical schema. Reject legacy payloads or transform once at the external boundary. |
| **Preemptive Deprecation Staging** | Adding `@deprecated` decorators, warning filters, or feature flags for internal single-agent refactors. | Execute immediate clean in-place replacement across the entire codebase. |
| **Ghost Code Retention** | Commenting out old functions/classes or parking dead implementations in `_legacy.py` or `_deprecated.py`. | Delete dead code completely. Version control preserves history. |
| **Paranoid Dual-Writing** | Writing to both old and new database fields, cache keys, or dictionary structures simultaneously during internal refactoring. | Migrate to the new target structure directly in one atomic change wave. |

---

## Concrete-First Design for Classes, Protocols, and ABCs

Abstract Base Classes (`abc.ABC`) and static protocols (`typing.Protocol`) define structural interfaces. In Python, structural subtyping (duck typing) means you rarely need to declare an interface upfront.

### Choosing a boundary

Prefer concrete classes and functions. Introduce a Protocol or ABC when it expresses a useful current contract, not to reach a numeric quota or generate elaborate mocks. Keep test doubles focused on behavior at that boundary.

### ❌ ANTI-PATTERN: Speculative Single-Implementation Protocol & Mock Sprawl

```python
# BAD: Extracting a Protocol when only ONE production implementation exists, solely for mocking
from typing import Protocol
from unittest.mock import MagicMock

class UserNotifierProtocol(Protocol):
    def send_notification(self, user_id: str, message: str) -> bool: ...

class EmailUserNotifier:
    def __init__(self, smtp_host: str) -> None:
        self.smtp_host = smtp_host

    def send_notification(self, user_id: str, message: str) -> bool:
        # Production SMTP logic...
        return True

class UserService:
    def __init__(self, notifier: UserNotifierProtocol) -> None:
        self.notifier = notifier

    def register_user(self, user_id: str) -> None:
        self.notifier.send_notification(user_id, "Welcome!")

# Test code with mock bloat:
def test_user_service():
    mock_notifier = MagicMock(spec=UserNotifierProtocol)
    mock_notifier.send_notification.return_value = True
    service = UserService(mock_notifier)
    service.register_user("u123")
    mock_notifier.send_notification.assert_called_once_with("u123", "Welcome!")
```

### ✅ PRAGMATIC: Concrete Direct Implementation with Simple In-Memory Fake

```python
# GOOD: Concrete implementation first; simple fake or direct testing
from __future__ import annotations
from dataclasses import dataclass, field

class EmailUserNotifier:
    def __init__(self, smtp_host: str = "localhost") -> None:
        self.smtp_host = smtp_host

    def send_notification(self, user_id: str, message: str) -> bool:
        # Production SMTP logic...
        return True

@dataclass(slots=True)
class InMemoryNotifier:
    sent_messages: list[tuple[str, str]] = field(default_factory=list)

    def send_notification(self, user_id: str, message: str) -> bool:
        self.sent_messages.append((user_id, message))
        return True

class UserService:
    def __init__(self, notifier: EmailUserNotifier | InMemoryNotifier) -> None:
        self.notifier = notifier

    def register_user(self, user_id: str) -> None:
        self.notifier.send_notification(user_id, "Welcome!")

def test_user_service_registration() -> None:
    fake_notifier = InMemoryNotifier()
    service = UserService(fake_notifier)
    service.register_user("u123")
    assert fake_notifier.sent_messages == [("u123", "Welcome!")]
```

---

## Construction choices

The Builder Pattern is a design pattern from languages lacking named keyword arguments and default values (e.g. older Java). In Python, keyword arguments, keyword-only parameters, and dataclasses render small builder classes completely redundant.

### Struct Construction Rules
- Choose direct construction, constructors or builders according to validation needs and call-site clarity, not field count.

### ❌ ANTI-PATTERN: Verbose Builder for Simple Data Container

```python
# BAD: 50 lines of boilerplate builder for 3 fields
class ServerConfig:
    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

class ServerConfigBuilder:
    def __init__(self) -> None:
        self._host: str = "127.0.0.1"
        self._port: int = 8000
        self._timeout: float = 30.0

    def with_host(self, host: str) -> ServerConfigBuilder:
        self._host = host
        return self

    def with_port(self, port: int) -> ServerConfigBuilder:
        self._port = port
        return self

    def with_timeout(self, timeout: float) -> ServerConfigBuilder:
        self._timeout = timeout
        return self

    def build(self) -> ServerConfig:
        return ServerConfig(self._host, self._port, self._timeout)

# Call site:
config = (
    ServerConfigBuilder()
    .with_host("0.0.0.0")
    .with_port(9000)
    .with_timeout(60.0)
    .build()
)
```

### ✅ PRAGMATIC: Modern Dataclass with Slots and Keyword-Only Defaults

```python
# GOOD: Clean, concise, self-documenting dataclass
from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True, kw_only=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    timeout: float = 30.0

# Call site:
config = ServerConfig(host="0.0.0.0", port=9000, timeout=60.0)
```

---

## Banning Metaclasses & Dynamic Attribute Injections

Metaclasses (`class Foo(type):`) and runtime attribute mutations (`setattr(self, k, v)`, `__getattr__` dispatch magic) obscure code structure, defeat static typecheckers (mypy, pyright), prevent IDE code navigation, and degrade runtime performance.

### Guidelines
1. **Ban Custom Metaclasses**: In application code, never inherit from `type`. If class registration or inspection is required, use `__init_subclass__` (PEP 487) or a simple class decorator.
2. **Ban Dynamic Attribute Injection**: Do not inject attributes onto object instances using `setattr(self, ...)`. Explicitly declare all attributes in class definitions with type annotations.
3. **Ban Magic `__getattr__` Proxying**: Avoid generic `__getattr__` delegators that forward arbitrary calls unless building an explicit, well-tested RPC client stub.

### ❌ ANTI-PATTERN: Metaclass and Dynamic `setattr` Magic

```python
# BAD: Obscure metaclass and dynamic attribute assignment
class DynamicModelMeta(type):
    registry = {}
    def __new__(mcs, name, bases, attrs):
        cls = super().__new__(mcs, name, bases, attrs)
        mcs.registry[name] = cls
        return cls

class DynamicRecord(metaclass=DynamicModelMeta):
    def __init__(self, **kwargs) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)  # Defeats static analysis and slots
```

### ✅ PRAGMATIC: `__init_subclass__` and Explicit Typed Fields

```python
# GOOD: Standard __init_subclass__ with explicit typed fields
from __future__ import annotations
from dataclasses import dataclass
from typing import ClassVar

class PluginBase:
    _registry: ClassVar[dict[str, type[PluginBase]]] = {}

    def __init_subclass__(cls, plugin_name: str, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls._registry[plugin_name] = cls

@dataclass(slots=True)
class AuthPlugin(PluginBase, plugin_name="auth"):
    api_key: str
    realm: str = "default"
```

---

## Data Modeling Hierarchy: Dataclass vs TypedDict vs Pydantic v2

Choosing the appropriate data modeling tool prevents performance penalties and type bloat.

### Decision Rubric

| Data Structure | Primary Use Case | Performance Cost | Validation | Immutability Option |
|---|---|---|---|---|
| `@dataclass(slots=True)` | Internal domain models, algorithm state, entities | Lowest (~48 bytes/instance, C-speed attr access) | Static typing only | `frozen=True` |
| `TypedDict` | Typing raw dictionary shapes, API JSON inputs/outputs without instantiation | Zero runtime cost (pure type annotation) | Static typing only | N/A (mutable dict) |
| `Pydantic v2 BaseModel` | Untrusted external boundaries (HTTP requests, CLI args, config files) | Moderate (Rust `pydantic-core` validation) | Strict runtime parsing & coercion | `model_config = ConfigDict(frozen=True)` |
| `msgspec.Struct` | High-throughput JSON/MessagePack ingestion hot paths | Ultra-low (C-extension parsing, 10-20x faster than json) | Fast schema validation | `frozen=True` |

### Code Examples: Choosing the Right Data Model

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import TypedDict
from pydantic import BaseModel, ConfigDict, Field
import msgspec

# 1. TypedDict: For raw dictionary shapes without instantiation
class RawUserPayload(TypedDict):
    user_id: str
    email: str
    is_active: bool

# 2. Pydantic v2: For untrusted HTTP boundary validation
class CreateUserRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user_id: str = Field(min_length=3, max_length=64)
    email: str
    is_active: bool = True

# 3. msgspec.Struct: For ultra-high throughput JSON parsing in hot paths
class EventRecord(msgspec.Struct, frozen=True):
    event_id: str
    timestamp: float
    payload: bytes

# 4. @dataclass(slots=True): For internal application domain entities
@dataclass(slots=True, kw_only=True)
class UserAccount:
    user_id: str
    email: str
    is_active: bool = True
    login_count: int = 0
```
