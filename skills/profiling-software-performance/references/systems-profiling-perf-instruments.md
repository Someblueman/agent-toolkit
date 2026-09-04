# Systems Profiling: Linux perf, PMU Hardware Counters, macOS Instruments & Flamegraphs

Systems-level profiling inspects program execution directly at the hardware-software boundary. By sampling CPU instruction execution, capturing call stacks, and reading Performance Monitoring Unit (PMU) hardware counters, engineers can pinpoint whether code is compute-bound, memory-latency-bound, cache-bandwidth-bound, or stalled on OS kernel events.

---

## 1. Linux `perf` Profiling Architecture

Linux `perf` (part of `linux-tools`) interfaces with kernel subsystem tracepoints, kprobes, uprobes, and hardware PMU counters.

### 1.1 PMU Hardware Performance Counters

Hardware counters are dedicated registers inside the CPU core that count architectural events with zero runtime software overhead.

```text
┌─────────────────────────────────────────────────────────────┐
│                       CPU Core                              │
│  ┌──────────────────┐  ┌────────────────┐  ┌─────────────┐  │
│  │ Execution Units  │  │ Branch Predict │  │  L1 D-Cache │  │
│  └─────────┬────────┘  └───────┬────────┘  └──────┬──────┘  │
│            │ (cycles, instrs)  │ (misses)         │ (misses)│
│            ▼                   ▼                  ▼         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         PMU Hardware Performance Counters             │  │
│  └─────────────────────────────┬─────────────────────────┘  │
└────────────────────────────────┼────────────────────────────┘
                                 ▼
                     Linux Kernel perf Subsystem
```

#### Essential PMU Events Table
| PMU Event Name | Hardware Meaning | Target Ratio / Healthy Baseline |
| :--- | :--- | :--- |
| `cycles` | Unhalted core clock cycles consumed | Baseline reference |
| `instructions` | Total retired architectural instructions | Combined with cycles for IPC |
| `L1-dcache-loads` | Level-1 data cache read attempts | Memory access intensity |
| `L1-dcache-load-misses` | Accesses missing L1 (must fetch from L2/L3) | Interpret on the actual CPU/workload |
| `LLC-loads` / `LLC-load-misses` | Last Level Cache (L3) accesses and misses (DRAM trip) | Interpret on the actual CPU/workload |
| `branch-instructions` | Direct, indirect, conditional branch instructions | Control flow density |
| `branch-misses` | Branch target/direction mispredictions (pipeline flush) | Interpret on the actual CPU/workload |
| `context-switches` | Process/thread preemptions and yields | Target: Low in compute loops |
| `page-faults` | Virtual memory page mapping allocations/faults | Target: Near zero after warmup |

---

### 1.2 `perf stat` Diagnostics & Metric Formulas

Run a quick high-level PMU diagnosis to classify the execution bottleneck:

```bash
perf stat -e cycles,instructions,cache-references,cache-misses,\
L1-dcache-loads,L1-dcache-load-misses,LLC-loads,LLC-load-misses,\
branch-instructions,branch-misses,context-switches,page-faults \
-- ./target_binary arg1 arg2
```

#### Diagnostic Formula Cheat Sheet

Interpret IPC, cache misses and branch misses together with CPU-specific event definitions, sampling coverage and the workload. A low IPC can reflect memory latency, dependency chains, contention or other stalls; high IPC does not establish vectorization or a compute bottleneck. Cache miss rates alone do not establish bandwidth saturation. Compare relevant counters before and after a measured change rather than applying universal numeric gates.

## 2. Flamegraph Workflows

Flamegraphs visualize hierarchical call stacks where:
- The **X-axis** represents population percentage (width = total time on CPU).
- The **Y-axis** represents call stack depth (top-most box = leaf function running on CPU).
- Colors are typically warm (randomly varied for visual stack distinction).

```text
┌─────────────────────────────────────────────────────────────┐
│                    compute_inner_kernel (65%)               │
├──────────────────────────────────────────────┬──────────────┤
│             process_dataset (85%)            │ io_flush (8%)│
├──────────────────────────────────────────────┴──────────────┤
│                        main (98%)                           │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 On-CPU Flamegraphs (Linux)

```bash
# 1. Record samples with call stacks
perf record -F 997 -g -- ./my_app

# 2. Extract stack traces
perf script > out.perf

# 3. Collapse stacks and render SVG
stackcollapse-perf.pl out.perf > out.folded
flamegraph.pl out.folded > flamegraph_on_cpu.svg
```

*(Note: Use the included script `generate_flamegraph.sh` for an all-in-one automated pipeline)*.

---

### 2.2 Off-CPU Profiling (Lock Contention, Blocking I/O)

When a program is slow but CPU utilization is low ($< 10\%$), the application is stalled off-CPU (waiting on mutexes, conditional variables, disk I/O, or network sockets).

Using eBPF / `bcc-tools`:
```bash
# Record off-CPU stack traces for PID for 10 seconds
sudo offcputime-bpfcc -df -p <PID> 10 > out.offcpu.folded

# Generate off-CPU flamegraph (colors typically inverted to cool blue/green)
flamegraph.pl --color=io --title="Off-CPU Time Flame Graph" out.offcpu.folded > offcpu_flame.svg
```

---

## 3. macOS Systems Profiling (`xctrace` / Instruments / CLI)

macOS Darwin uses the DTrace and Instruments subsystems rather than Linux `perf`.

### 3.1 Non-Interactive Profiling with `xctrace` CLI

`xctrace` records Instruments sessions headlessly from the terminal, generating `.trace` bundles.

#### Recording Common Templates
```bash
# 1. Time Profiler (CPU Call Stacks)
xcrun xctrace record --template 'Time Profiler' --time-limit 5s --launch -- ./my_app

# 2. Allocations & Leaks (Heap Memory Profiling)
xcrun xctrace record --template 'Allocations' --time-limit 10s --launch -- ./my_app

# 3. CPU Counters (PMU Hardware Events)
xcrun xctrace record --template 'CPU Counters' --time-limit 5s --launch -- ./my_app

# 4. System Trace (Thread Scheduling & Syscalls)
xcrun xctrace record --template 'System Trace' --time-limit 3s --launch -- ./my_app
```

#### Exporting & Querying Trace Data
```bash
# Export trace package to XML/JSON for automated script analysis
xcrun xctrace export --input *.trace --output trace_report.xml
```

---

### 3.2 macOS Native CLI Profiling Utilities

For fast, zero-configuration command-line diagnosis on macOS:

| Tool | Invocation | Purpose |
| :--- | :--- | :--- |
| **`sample`** | `sample <PID> 5 10 -file out.txt` | Samples target process for 5 seconds at 10ms intervals, outputting top call stacks. |
| **`spindump`** | `sudo spindump -file spin.txt` | System-wide capture of unresponsive or high-CPU threads and kernel stacks. |
| **`leaks`** | `leaks --atExit -- ./my_app` | Intercepts malloc calls and detects unreferenced heap buffers at exit. |
| **`heap`** | `heap <PID>` | Inspects live heap memory breakdown by class / allocation size. |
| **`vmmap`** | `vmmap -resident <PID>` | Analyzes virtual memory map, dirty memory pages, and mapped libraries. |
| **`dtruss`** | `sudo dtruss -p <PID>` | DTrace-based system call tracer (macOS equivalent to Linux `strace`). |

#### Example: Quick Process Stack Sampling
```bash
# Launch program in background and sample for 3 seconds
./my_app &
APP_PID=$!
sample $APP_PID 3 5 -file sample_output.txt
wait $APP_PID
cat sample_output.txt | head -n 40
```

---

## 4. Systems Profiling Decision Tree

```text
                    [ High Latency / Low Throughput ]
                                    │
                                    ▼
                         Check CPU Utilization
                                    │
                ┌───────────────────┴───────────────────┐
                ▼                                       ▼
        CPU Util ~ 100%                         CPU Util < 50%
          (On-CPU)                                (Off-CPU)
                │                                       │
                ▼                                       ▼
    Run PMU stat (IPC check)               Trace System Events
         Stall evidence:                              │
         ├─ High L1 Miss: Data Locality / SoA    ├─ Mutex Contention (Lock-free / SPSC)
         ├─ High LLC Miss: DRAM Bandwidth        ├─ Disk I/O Wait (mmap / Async I/O)
         └─ High Branch Miss: Branchless / CMOV  └─ Network Socket Wait (Epoll / Kqueue)
         Compute evidence:
         └─ Algorithm Complexity (O(N^2) -> O(N))
            or SIMD Vectorization Opportunity
```
