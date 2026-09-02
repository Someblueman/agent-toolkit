# Haskell GHC Profiling: Time, Heap, Eventlog, GC Stats & Core Inspection

Haskell programs run on the Glasgow Haskell Compiler (GHC) runtime system (RTS), which employs non-strict (lazy) evaluation by default, graph-reduction memory allocation, and a generational, copying garbage collector.

Because execution order does not mirror syntactic call structure, profiling Haskell requires understanding **thunk creation**, **cost-centre attribution**, **heap residency graphs**, and **GHC Core intermediate representations**.

---

## 1. Compilation for Profiling

To profile execution time, allocations, or heap residency, the program must be compiled with profiling instrumentation enabled.

### 1.1 Essential Compiler Flags

```bash
ghc -O2 -prof -fprof-auto -rtsopts -o my_haskell_app Main.hs
```

| Flag | Meaning & Purpose |
| :--- | :--- |
| `-prof` | Links the binary against the GHC profiling runtime system library. |
| `-fprof-auto` | Automatically inserts cost centres on all top-level and local function bindings. |
| `-fprof-cafs` | Inserts cost centres on Constant Applicative Forms (top-level values computed once). |
| `-rtsopts` | Permits passing runtime options (`+RTS ... -RTS`) on the command line. **Mandatory**; omitting causes runtime failure. |
| `-rtsopts=all` | Allows full control over RTS parameters without restrictions. |

### 1.2 Manual Set Cost Centre (SCC) Annotations

Automatic profiling (`-fprof-auto`) can introduce minor measurement overhead. For granular attribution without whole-program instrumentation, use manual `SCC` pragmas:

```haskell
module DataProcessor (processPipeline) where

processPipeline :: [DataRecord] -> AggregateResult
processPipeline input =
  let cleaned   = {-# SCC "stage_clean" #-} filter isValid input
      sorted    = {-# SCC "stage_sort" #-}  sortRecords cleaned
      aggregated= {-# SCC "stage_accum" #-} foldl' step initial sorted
  in aggregated
```

---

## 2. GHC Cost-Centre Time Profiling (`+RTS -p`)

Run the profiled executable with the `-p` RTS flag to generate a detailed cost-centre breakdown file (`<program>.prof`):

```bash
./my_haskell_app +RTS -p -RTS arg1 arg2
```

### 2.1 Anatomy of `<program>.prof`

```text
	Sat Aug 29 23:30 2026 Time and Allocation Profiling Report  (Final)

	   my_haskell_app +RTS -p -RTS

	total time  =        1.42 secs   (1420 ticks @ 1000 us, 10 cores)
	total alloc = 852,120,448 bytes  (excludes profiling overheads)

COST CENTRE          MODULE           SRC                       %time %alloc

sumLazy              Main             Main.hs:14:1-35            78.4   82.1
parseInput           Parser           Parser.hs:42:5-28          14.2   12.3
renderOutput         View             View.hs:102:1-18            4.1    3.2
MAIN                 MAIN             <built-in>                  3.3    2.4

                                                                      individual     inherited
COST CENTRE          MODULE           SRC                no.  entries  %time %alloc   %time %alloc

MAIN                 MAIN             <built-in>         102        0    0.0    0.0   100.0  100.0
 main                Main             Main.hs:22:1-15    205        1    0.0    0.0   100.0  100.0
  sumLazy            Main             Main.hs:14:1-35    206        1   78.4   82.1    78.4   82.1
  parseInput         Parser           Parser.hs:42:5-28  207        1   14.2   12.3    14.2   12.3
```

### 2.2 Metric Definitions

- **`total time`**: CPU time spent executing the program, sampled in timer ticks (typically 1 tick = 1 ms).
- **`total alloc`**: Aggregate total bytes allocated on the nursery heap over the run (measure of allocation churn).
- **`%time`**: Percentage of timer ticks sampled while this cost centre was at the top of the stack.
- **`%alloc`**: Percentage of nursery heap bytes allocated inside this cost centre.
- **`individual %time / %alloc`**: Resources attributed solely to this exact function body.
- **`inherited %time / %alloc`**: Cumulative resources attributed to this function and all sub-functions called under its cost centre.

*(Use the included script `analyze_ghc_prof.py` to automatically parse and rank cost centres from `.prof` files)*.

---

## 3. GHC Heap Profiling & Space Leak Diagnosis

Space leaks occur in Haskell when computations are deferred as unevaluated heap closures (**thunks**) rather than being reduced eagerly. When thousands of thunks accumulate, memory residency grows linearly ($O(N)$), triggering severe GC pause degradation.

### 3.1 Heap Profiling Modes

GHC supports multiple heap profiling dimensions:

```bash
# 1. Profile by Cost Centre (Which function is creating retained objects?)
./my_haskell_app +RTS -hc -p -RTS

# 2. Profile by Type Constructor (Which data types occupy heap memory?)
./my_haskell_app +RTS -hy -p -RTS

# 3. Profile by Closure / Constructor Name (e.g. (:), Just, Int, Thunks)
./my_haskell_app +RTS -hd -p -RTS

# 4. Profile by Module (Which module allocates retained objects?)
./my_haskell_app +RTS -hm -p -RTS

# 5. Profile by Biographical State (Lag, Drag, Void, Use)
./my_haskell_app +RTS -hb -p -RTS
```

### 3.2 Visualizing Heap Graphs with `hp2ps`

Heap profiling produces a `<program>.hp` sample file. Convert it into a PostScript graph:

```bash
# Convert .hp samples to .ps graph (-c produces color bands)
hp2ps -c my_haskell_app.hp

# View PostScript or convert to PDF
ps2pdf my_haskell_app.ps my_haskell_app_heap.pdf
```

```text
Heap Residency (MB)
  ▲
100│                  /╲  <── CLASSIC SPACE LEAK SHAPE:
 80│                 /  ╲     Linear growth (accumulating thunks)
 60│                /    ╲    followed by instantaneous collapse
 40│               /      ╲   when final result is evaluated.
 20│              /        ╲
  0└─────────────/──────────╲────────► Time (s)
```

**Diagnostic Rule**:
- **Healthy Profile**: A flat, bounded sawtooth curve (residency remains within constant upper bound).
- **Space Leak**: A monotonic upward ramp that climbs continuously until final evaluation.

---

## 4. GHC Garbage Collector Statistics (`+RTS -s`)

GC statistics provide instantaneous, zero-instrumentation health checks on memory throughput and collector efficiency.

```bash
# No profiling recompilation required! Works on any binary compiled with -rtsopts
./my_haskell_app +RTS -s -RTS
```

### 4.1 Sample GC Summary Output

```text
 1,248,392,160 bytes allocated in the heap
    24,180,416 bytes copied during GC
     6,412,880 bytes maximum residency (3 sample(s))
       120,480 bytes maximum slop
            16 MiB total memory in use (0 MiB lost due to fragmentation)

                                     Tot time (elapsed)  Avg pause  Max pause
  Gen  0      1192 colls,     0 par    0.042s   0.043s     0.0000s    0.0008s
  Gen  1         3 colls,     0 par    0.015s   0.016s     0.0051s    0.0082s

  INIT    time    0.001s  (  0.001s elapsed)
  MUT     time    0.840s  (  0.842s elapsed)
  GC      time    0.057s  (  0.059s elapsed)
  TOTAL   time    0.898s  (  0.902s elapsed)

  %GC     time       6.3%  (6.5% elapsed)

  Alloc rate    1,486,181,142 bytes per MUT second

  PRODUCTIVITY  93.5% of total user, 93.3% of total elapsed
```

### 4.2 Critical GC Health Metrics

1. **PRODUCTIVITY**:
   $$\text{Productivity} = \frac{\text{MUT time}}{\text{TOTAL time}} \times 100\%$$
   - **$> 85\%$**: **Healthy**. CPU is actively computing user code.
   - **$70\% - 85\%$**: **Marginal**. Noticeable allocation churn.
   - **$< 70\%$**: **Severe Memory Bottleneck**. CPU is spending $> 30\%$ of time copying and traversing heap objects in GC.
2. **Bytes copied during GC**:
   - High ratio of copied bytes indicates objects surviving nursery Gen 0 collection and being promoted into older generations.
3. **Maximum Residency**:
   - Represents the true live working set size of the program.

---

## 5. GHC Eventlog & Multicore Concurrency Profiling

For concurrent and parallel Haskell applications (`Control.Parallel.Strategies`, `Control.Concurrent.Async`), use high-resolution event logging.

### 5.1 Compilation and Execution
```bash
# Compile with eventlog support
ghc -O2 -eventlog -rtsopts -threaded -o my_concurrent_app Main.hs

# Run with eventlog tracing enabled (-N enables multicore runtime)
./my_concurrent_app +RTS -N4 -l -ls -RTS
# Generates: my_concurrent_app.eventlog
```

- `-l`: Standard runtime events (thread creation, GC pauses).
- `-ls`: Spark profiling (parallel sparks created, converted, fizzled, GC'd).
- `-la`: Allocation sampling events.

### 5.2 ThreadScope Visualization

Open the eventlog in `ThreadScope` to diagnose:
- **HEC (Haskell Execution Context) Utilization**: Are all CPU cores kept 100% busy?
- **Spark Fizzle Rate**: Sparks evaluated by the main thread before a worker thread claimed them (indicating excessive granularity).
- **GC Sync Stalls**: Time worker threads spend paused waiting for global GC synchronization.

---

## 6. GHC Core Optimization Inspection (`-ddump-simpl`)

GHC compiles Haskell source code down to **Core**, a strongly typed intermediate language based on System F with unboxed types and explicit strictness.

Inspecting Core verifies whether GHC has successfully:
- Unboxed numeric wrappers (`Int#`, `Double#`).
- Inlined tight loops.
- Performed worker-wrapper transformations (`-fworker-wrapper`).
- Fired rewrite rules (`{-# RULES #-}`).

### 6.1 Compiling with Core Dumps
```bash
ghc -O2 -ddump-simpl -dsuppress-all -dsuppress-uniques Main.hs > Main.simpl.core
```

*Note: Always pass `-dsuppress-all` and `-dsuppress-uniques`; otherwise GHC outputs internal variable unique suffixes (`x_s1a8`), obscuring the code.*

### 6.2 Diagnosing Boxed vs Unboxed Code in Core

#### Boxed / Un-optimized Loop (Bad - Heap Allocating)
```haskell
-- In Core: Calling boxed (+) constructor allocates 'I#' closure every iteration
$wloop :: Int -> Int -> Int
$wloop = \ (acc :: Int) (n :: Int) ->
  case n of {
    I# n# ->
      case n# of {
        __DEFAULT ->
          -- Allocates new boxed 'I#' heap closure for (acc + n)
          let { acc' = case acc of { I# a# -> I# (+# a# n#) } }
          in $wloop acc' (I# (-# n# 1#));
        0# -> acc
      }
  }
```

#### Unboxed / Optimized Worker Loop (Ideal - Zero Heap Allocation)
```haskell
-- In Core: Arguments are unboxed primitive 'Int#', values stored in CPU registers
$wloop :: Int# -> Int# -> Int#
$wloop = \ (acc# :: Int#) (n# :: Int#) ->
  case n# of {
    __DEFAULT -> $wloop (+# acc# n#) (-# n# 1#);
    0#        -> acc#
  }
```
If `$wloop` operates purely on `Int#` with primitive `+#` and `-#` instructions and zero `I#` constructor calls, the loop will compile directly to bare-metal CPU register arithmetic with zero memory allocation.
