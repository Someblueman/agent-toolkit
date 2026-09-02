# Compatibility Decision Matrix & Single-Path Execution

Use this reference when refactoring interfaces, updating data schemas, altering method signatures, or replacing legacy subsystems.

## 1. Core Rule: Single-Path Execution

When modifying existing code in an internal codebase, always execute a clean in-place replacement:
1. Update the signature or data structure directly.
2. Update all call sites across the repository in the same change wave.
3. Update existing tests to reflect the new contract.
4. Delete obsolete code paths, legacy decoders, and unused helpers immediately.

Do not introduce transitional states, fallback decoders, or compatibility wrappers unless the user has explicitly requested backwards compatibility.

## 2. Forbidden Anti-Patterns Catalog

### Anti-Pattern 1: Shim Multiplication
*Behavior*: Introducing a new function `process_v2` and rewriting `process` to call `process_v2` with default arguments, instead of updating all call sites to `process`.

```rust
// ❌ ANTI-PATTERN: Retaining legacy shim
pub fn calculate_tax(amount: f64) -> f64 {
    calculate_tax_v2(amount, Country::Default) // Shim wrapper
}

pub fn calculate_tax_v2(amount: f64, country: Country) -> f64 {
    // New implementation
}

// ✅ PRAGMATIC: In-place signature change & atomic call site update
pub fn calculate_tax(amount: f64, country: Country) -> f64 {
    // Direct implementation, all callers updated immediately
}
```

### Anti-Pattern 2: Dual-Format Fallback & Zombie Decoders
*Behavior*: Keeping obsolete JSON parsers, protobuf fields, or legacy deserializers alive "just in case" older formats are encountered in an internal, ephemeral system.

```typescript
// ❌ ANTI-PATTERN: Zombie decoder fallback
function parseConfig(raw: string): Config {
  try {
    return parseV2Config(raw);
  } catch {
    return parseLegacyV1Config(raw); // Zombie fallback
  }
}

// ✅ PRAGMATIC: Single-path parser
function parseConfig(raw: string): Config {
  return parseV2Config(raw);
}
```

### Anti-Pattern 3: Preemptive Deprecation Staging
*Behavior*: Marking methods `@deprecated` and planning multi-month phaseouts for code with zero external consumers outside the repository.

```python
# ❌ ANTI-PATTERN: Deprecation warning for internal code
import warnings

def get_user_data(user_id: str):
    warnings.warn("get_user_data is deprecated, use fetch_user", DeprecationWarning)
    return fetch_user(user_id)

# ✅ PRAGMATIC: Clean rename across repository
def fetch_user(user_id: str):
    # Direct implementation
```

### Anti-Pattern 4: Paranoid Dual-Writing
*Behavior*: Writing updates to both old and new database columns or cache keys simultaneously during single-step internal refactors.

### Anti-Pattern 5: Ghost Code Retention
*Behavior*: Commenting out old functions with `// legacy: keep for reference` or moving dead code into `legacy_utils.py`.

---

## 3. When Backwards Compatibility IS Required

Preserve backwards compatibility ONLY when:
1. The repository is a published library (e.g. crates.io, npm, PyPI) with external semver commitments.
2. The user explicitly prompts: "Ensure backwards compatibility with format X."
3. The data format is persisted in durable, long-term external storage that cannot be migrated in-place.

When compatibility is required:
- Confine the adapter to the boundary layer (e.g. deserialization entry point).
- Convert legacy data immediately to the canonical internal representation.
- Do not let legacy branches permeate core business logic.
