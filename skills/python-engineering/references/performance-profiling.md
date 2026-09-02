# Performance & Profiling

Read this when optimizing Python CPU throughput, reducing memory footprint, analyzing GIL contention, profiling production services, or debugging memory leaks. Never optimize without first establishing a reproducible baseline profile.

## Optimization Hierarchy & The 80/20 Rule

```text
1. Algorithmic Complexity (O(n^2) -> O(n log n) or O(1) hash maps)
   |
2. Data Layout & Memory Access (__slots__, contiguous NumPy/Polars arrays)
   |
3. Execution Model (asyncio for I/O, ProcessPoolExecutor for CPU)
   |
4. CPython Bytecode Tuning (local variables, built-in caching)
   |
5. Native Extensions (PyO3/Rust, Cython, C extensions)
```

---

## CPython Memory Optimization & `__slots__`

Standard CPython class instances store attributes in a dynamic `__dict__` dictionary and maintain a `__weakref__` pointer, consuming ~152 bytes per instance plus dictionary resizing overhead. When creating millions of records, this causes severe memory bloat and garbage collection pressure.

### Memory Comparison

| Class Type | Memory Per Instance | Attribute Lookup Overhead | Dynamic Attributes |
|---|---|---|---|
| Standard `class Item:` | ~152 bytes + `__dict__` heap | Hash table lookup (`LOAD_ATTR`) | Yes |
| `@dataclass` (default) | ~152 bytes + `__dict__` heap | Hash table lookup (`LOAD_ATTR`) | Yes |
| `@dataclass(slots=True)` | **~48 bytes** | Direct C struct offset lookup | No (Fixed schema) |
| `namedtuple` | ~56 bytes | Tuple index lookup | No |

### ❌ ANTI-PATTERN: Millions of Standard Objects Exhausting RAM

```python
# BAD: 10,000,000 objects consume ~1.8 GB RAM due to __dict__ overhead
class DataPoint:
    def __init__(self, timestamp: float, value: float, tag: str) -> None:
        self.timestamp = timestamp
        self.value = value
        self.tag = tag

# Creating 10M records triggers OOM or heavy GC latency
records = [DataPoint(float(i), float(i * 2), "sensor-A") for i in range(10_000_000)]
```

### ✅ PRAGMATIC: Slotted Dataclass or Vectorized Polars DataFrame

```python
# GOOD: Slotted dataclass reduces memory by ~70% (down to ~500 MB)
from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class DataPoint:
    timestamp: float
    value: float
    tag: str

# For purely numerical/tabular workloads, use Polars for zero-copy column memory (<100 MB)
import polars as pl

df = pl.DataFrame({
    "timestamp": [float(i) for i in range(10_000_000)],
    "value": [float(i * 2) for i in range(10_000_000)],
    "tag": ["sensor-A"] * 10_000_000,
})
```

---

## Bytecode & Tight Loop Tuning

In CPU-bound loops running millions of iterations, CPython opcode dispatch overhead dominates execution time.

### Key Micro-Optimizations
1. **Local Variable Lookup (`LOAD_FAST`)**: Local variables in functions are accessed via array indexing in C (`LOAD_FAST`), whereas module-level globals and builtins require dictionary lookups (`LOAD_GLOBAL`).
2. **Method Lookup Hoisting**: Hoist bound method lookups outside the loop (`append = result.append`).
3. **List Comprehensions Over `.append()`**: List comprehensions are executed directly in optimized C bytecode (`LIST_APPEND`), outperforming repeated Python function calls.

```python
from __future__ import annotations

# FAST: Local variable binding, list comprehension
def compute_squares(numbers: list[int]) -> list[int]:
    # List comprehension uses LIST_APPEND opcode directly
    return [n * n for n in numbers if n % 2 == 0]
```

---

## The Profiling Playbook

Never guess what is slow. Use the appropriate profiling tool based on your objective.

### Profiling Tools Selection Matrix

| Profiler | Overhead | Resolution | Use Case |
|---|---|---|---|
| **`cProfile`** | High (2-3x slowdown) | Function-level call counts & cumulative time | Deterministic offline analysis of test scripts |
| **`py-spy`** | Negligible (<5% overhead) | Call stack sampling, flamegraphs | Production services, live PID inspection |
| **`line_profiler`** | High (5-10x slowdown) | Line-by-line execution time and hit counts | Deep bottleneck analysis within a single hot function |
| **`tracemalloc`** | Moderate | Memory allocation byte counts and line origins | Tracking memory leaks and object retention |

### 1. Deterministic Function Profiling with `cProfile`

```bash
# Run cProfile and sort output by cumulative execution time
uv run python -m cProfile -s cumulative src/main.py > profile.txt
```

Analyze the output to identify top cumulative time consumers (`cumtime`) versus internal execution time (`tottime`).

### 2. Sampling & Flamegraphs with `py-spy`

`py-spy` samples the CPython runtime stack out-of-process without modifying application code:

```bash
# Generate a flamegraph SVG from a running process
py-spy record -o flamegraph.svg --pid <PID>

# Record during a CLI script execution
py-spy record -o flamegraph.svg -- python src/main.py

# Live top-like monitor
py-spy top --pid <PID>
```

### 3. Memory Profiling with `tracemalloc`

Use `tracemalloc` to capture memory snapshots before and after a workload to detect leaks:

```python
from __future__ import annotations
import tracemalloc

def diagnose_memory_leak() -> None:
    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()

    # Execute suspicious workload...
    run_batch_job()

    snapshot2 = tracemalloc.take_snapshot()
    top_stats = snapshot2.compare_to(snapshot1, "lineno")

    print("[Top 5 Memory Differences]")
    for stat in top_stats[:5]:
        print(stat)

    current, peak = tracemalloc.get_traced_memory()
    print(f"Current: {current / 1024 / 1024:.2f} MB, Peak: {peak / 1024 / 1024:.2f} MB")
    tracemalloc.stop()
```

---

## Multi-Core Parallelism & GIL Boundaries

Because the CPython Global Interpreter Lock (GIL) serializes bytecode execution on a single OS thread, pure Python CPU-bound tasks do not speed up with `threading.Thread`.

### Scaling Strategy
- **I/O Bound**: Use `asyncio` or `concurrent.futures.ThreadPoolExecutor`. The GIL is automatically released during underlying socket I/O.
- **CPU Bound (Pure Python)**: Use `concurrent.futures.ProcessPoolExecutor` to distribute work across separate OS processes with independent GILs.
- **CPU Bound (Vectorized/Native)**: Use NumPy, Polars, or PyO3 Rust extensions which release the GIL (`Py_BEGIN_ALLOW_THREADS`) during native execution.

```python
from __future__ import annotations
import concurrent.futures
import math

def compute_heavy_chunk(chunk: list[float]) -> float:
    return sum(math.sin(x) * math.cos(x) for x in chunk)

def process_parallel_chunks(data: list[float], chunk_size: int = 100_000) -> float:
    chunks = [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = executor.map(compute_heavy_chunk, chunks)
    return sum(results)
```
