# Anti-Bloat Heuristics, TDD Calibration, and Lean Architecture

Use this reference to maintain quantitative line budgets, modularize god-files, calibrate test volume, avoid over-abstraction, and build lean, maintainable systems.

---

## 1. Quantitative Line Budgets & Hard Constraints

| Constraint | Limit | Action on Breach |
|---|---|---|
| **File Length Ceiling** | **500 LOC** per file (source, tests, scripts) | Execute the God-File Decomposition Protocol; modularize into submodules |
| **Rust Inline Test Budget** | **150 LOC** per inline `mod tests` block | Extract into dedicated test files under `tests/` or sibling modules |
| **Standalone Smoke Scripts** | **Zero tolerance** (`*smoke*` scripts/paths) | Replace with targeted domain unit tests; delete throwaway runners |

---

## 2. God-File Decomposition Protocol

When modifying a file that exceeds or would exceed 500 LOC, do NOT append additional code. Modularly decompose it using this 4-step protocol:

```text
[God File (> 500 LOC)]
       │
       ├─► 1. Cluster Analysis: Identify domain responsibilities & data struct groupings
       ├─► 2. Submodule Extraction: Move cohesive clusters into focused sibling files
       ├─► 3. Facade Re-Export: Re-export types from original entry point to preserve call sites
       └─► 4. Verification: Run targeted unit tests and verify all files are <= 500 LOC
```

### Step 1: Cluster Analysis
Identify cohesive groupings of types, handlers, and helpers within the god-file:
- Core data models / AST / structs (`types.rs` / `models.py`)
- Parsing / serialization logic (`parser.rs` / `deserializer.py`)
- Core transformation / domain execution (`engine.rs` / `evaluator.py`)
- Formatting / output generation (`formatter.rs` / `renderer.py`)

### Step 2: Submodule Extraction
Create focused submodule files in a subfolder or sibling files, moving the corresponding structs, impl blocks, and helper functions. Ensure each new file is well within the 500 LOC limit.

### Step 3: Facade Re-Export (Zero-Churn Call Sites)
Maintain backwards compatibility with existing internal call sites by re-exporting all moved symbols from the parent module or package entry point:

**Rust (`mod.rs` or parent file):**
```rust
pub mod models;
pub mod parser;
pub mod engine;

// Facade re-export: existing callers continue using `crate::my_module::MyStruct`
pub use models::*;
pub use parser::*;
pub use engine::*;
```

**Python (`__init__.py` or module entry):**
```python
from .models import Item, Config
from .parser import parse_input
from .engine import execute_pipeline

__all__ = ["Item", "Config", "parse_input", "execute_pipeline"]
```

**TypeScript (`index.ts`):**
```typescript
export * from './models';
export * from './parser';
export * from './engine';
```

### Step 4: Verification
1. Run targeted unit tests (`pytest`, `cargo test`, `npm test`) to ensure zero behavioral regression.
2. Run `scripts/check_anti_bloat.py` to confirm all files remain <= 500 LOC.

---

## 3. High-Signal Unit Testing Rubric

### Why Standalone Smoke Tests Are Banned
Throwaway smoke scripts (e.g. `scripts/test-smoke.mjs`, `smoke.py`, ephemeral `/tmp/*-smoke` directories, or subprocess-spawning integration scripts):
- Hide the root cause of failures behind opaque exit codes.
- Introduce environmental flakiness and high execution latency.
- Provide a false sense of security without asserting domain invariants or failure boundaries.

### High-Signal Testing Alternatives

Replace shallow smoke runners with targeted, in-memory unit tests:

| Testing Need | ❌ Banned Smoke Approach | ✅ High-Signal Alternative |
|---|---|---|
| **CLI & Option Parsing** | Spawning subshell to run `python cli.py --arg val` | Direct function call `parse_args(["--arg", "val"])` with assertion on parsed config |
| **State Transitions** | Running full binary against live temp DB | In-memory domain test asserting `state.apply(event)` produces expected state enum |
| **Error Handling** | Checking if process crashes on invalid JSON | Direct unit test passing invalid bytes to `parse()` asserting `Err(ParseError::InvalidHeader)` |
| **Roundtrip Serialization** | Writing to disk and checking exit code 0 | In-memory roundtrip `deserialize(serialize(&data)) == data` |

---

## 4. Lean Fixture Principles

Prohibit sprawling 50-line inline mock dictionaries and ceremonial test setup. Use minimal valid builders and factory functions:

### 1. Minimal Valid Factory Pattern
Construct valid minimal entities with sane defaults, allowing tests to override only the fields relevant to the specific assertion:

```python
# ✅ PRAGMATIC: Minimal valid factory with keyword overrides
def make_user(**overrides) -> User:
    defaults = {
        "id": "u_1",
        "email": "test@example.com",
        "is_active": True,
        "role": "member",
    }
    return User(**{**defaults, **overrides})

# In test: only state the field under test
def test_inactive_user_cannot_login():
    user = make_user(is_active=False)
    assert not can_login(user)
```

```rust
// ✅ PRAGMATIC: Minimal test helper in Rust
#[cfg(test)]
fn sample_request(path: &str) -> Request {
    Request {
        path: path.to_string(),
        method: Method::Get,
        headers: Default::default(),
        body: vec![],
    }
}
```

### 2. Table-Driven Boundary Tests
Use compact parameterized input/expected tuples rather than copy-pasting 10 separate test functions:

```python
import pytest

@pytest.mark.parametrize("raw_input,expected_error", [
    ("", "EmptyInput"),
    (" ", "EmptyInput"),
    ("a" * 501, "InputTooLong"),
    ("invalid@syntax", "MalformedSyntax"),
])
def test_validation_boundaries(raw_input, expected_error):
    result = validate(raw_input)
    assert result.error == expected_error
```

---

## 5. TDD Calibration: The 3-Step Test Rubric

Always write tests first when adding behavior or fixing bugs, keeping test volume calibrated to requirement scope:

1. **Step 1: Write the Reproduction / Primary Test**:
   - Write exactly ONE focused test capturing the specific requirement or reproducing the defect.
   - Run the test to confirm failure (Red).
2. **Step 2: Implement Minimal Fix**:
   - Write the simplest concrete code to satisfy the test (Green).
3. **Step 3: Add Direct Boundary Test (If Needed)**:
   - Add 1-2 direct edge/error boundary tests (e.g. empty input, threshold boundary).
   - Refactor cleanly without adding speculative features (Refactor).

### Banned Testing Anti-Patterns:
- ❌ **Combinatorial Matrix Bloat**: Generating 30+ permutations of non-critical parameters.
- ❌ **Smoke Test Sprawl**: Adding 15 smoke tests asserting trivial properties already checked by unit tests.
- ❌ **Mock-Everything Syndrome**: Deeply mocking internal structs instead of testing pure concrete logic.

---

## 6. Anti-Abstraction Mandate & Heuristics

### Heuristic 1: The Rule of Three
Do NOT extract a trait, abstract interface, or generic type parameter unless you have **at least 3 distinct concrete implementations** in the current codebase.

```rust
// ❌ ANTI-PATTERN: Speculative trait for single implementation
pub trait DataFetcher {
    fn fetch(&self, id: u64) -> Result<Data, Error>;
}
pub struct HttpDataFetcher;
impl DataFetcher for HttpDataFetcher { ... }

// ✅ PRAGMATIC: Direct concrete struct
pub struct HttpDataFetcher;
impl HttpDataFetcher {
    pub fn fetch(&self, id: u64) -> Result<Data, Error> { ... }
}
```

### Heuristic 2: Constructor Simplicity
Use direct struct initialization or a simple `new()` constructor. Ban Builder patterns for structs with fewer than 5 fields.

```rust
// ❌ ANTI-PATTERN: Builder for 2-3 fields
pub struct ClientBuilder { timeout: Option<u64>, retries: Option<u32> }

// ✅ PRAGMATIC: Direct constructor
pub struct Client {
    pub timeout_ms: u64,
    pub retries: u32,
}

impl Client {
    pub fn new(timeout_ms: u64, retries: u32) -> Self {
        Self { timeout_ms, retries }
    }
}
```

### Heuristic 3: Flat Architecture vs Multi-Layer Indirection
Avoid artificial layering where each layer merely forwards calls to the next.

```text
❌ Bloated: Controller -> Service -> Manager -> Repository -> DataAccessor
✅ Pragmatic: RouteHandler -> DomainStore
```
