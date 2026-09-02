# Rigorous Benchmarking and Noise Reduction Playbook

Measuring software performance without controlling for environmental noise yields deceptive, non-reproducible data. Modern operating systems and multi-core architectures introduce significant variance through dynamic frequency scaling, task scheduling migrations, cache perturbations, memory bus contention, and background system services.

This guide provides the protocols required to establish a noise-controlled benchmarking environment and apply statistical analysis to performance measurements.

---

## 1. Sources of Benchmarking Variance

| Source | Mechanism | Potential Variance Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Dynamic Frequency Scaling** | Intel Turbo Boost, AMD Core Performance Boost, Apple Silicon DVFS dynamically change CPU clock rates based on power and thermal headroom. | $\pm 15\% \text{ to } \pm 35\%$ | Lock CPU frequency governor to `performance` or fix frequency to base clock; disable Turbo Boost during tests. |
| **OS Thread Migration** | Kernel scheduler moves threads across physical CPU cores, invalidating L1/L2 caches and NUMA local memory nodes. | $\pm 10\% \text{ to } \pm 25\%$ | Pin process and worker threads to dedicated physical cores using CPU affinity masks (`taskset`, `pthread_setaffinity_np`). |
| **Cold Caches & TLB Misses** | Initial benchmark executions suffer from compulsory cache misses and page table walks. | $\pm 20\% \text{ to } \pm 100\%$ | Execute dedicated warmup iterations ($W \ge 5$) to populate L1/L2/L3 caches and TLB before recording timestamps. |
| **Address Space Randomization (ASLR)** | Kernel randomizes stack, heap, and code segment virtual memory addresses across process executions, altering cache set conflicts. | $\pm 2\% \text{ to } \pm 8\%$ | Run multiple independent process invocations ($N \ge 30$) to sample across different address layouts, or disable ASLR during local isolated testing. |
| **Context Switches & Interrupts** | Background daemons, timer interrupts, and hardware IRQs preempt benchmark execution. | $\pm 5\% \text{ to } \pm 30\%$ | Isolate dedicated cores (`isolcpus`), elevate scheduling priority (`chrt -f 99`), and terminate non-essential daemons. |
| **Memory Bus Contention** | Concurrent processes or sibling hardware threads (SMT/HyperThreading) saturate shared memory controllers and L3 cache. | $\pm 10\% \text{ to } \pm 40\%$ | Disable SMT/HyperThreading in BIOS or isolate benchmark to distinct physical cores; ensure machine is idle. |

---

## 2. Environment Stabilization Protocols

### 2.1 Linux Environment Setup

#### Step 1: CPU Frequency Governor & Turbo Boost Control
```bash
# Set CPU scaling governor to performance on all logical cores
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo "performance" | sudo tee "$cpu" > /dev/null
done

# Disable Intel Turbo Boost (if Intel CPU)
if [ -f /sys/devices/system/cpu/intel_pstate/no_turbo ]; then
    echo "1" | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo > /dev/null
fi

# Disable AMD Core Performance Boost (if AMD CPU)
if [ -f /sys/devices/system/cpu/cpufreq/boost ]; then
    echo "0" | sudo tee /sys/devices/system/cpu/cpufreq/boost > /dev/null
fi
```

#### Step 2: CPU Affinity & Core Isolation
Pin execution to a specific physical core (e.g., Core 2) to eliminate cache thrashing from thread migrations:
```bash
# Pin to physical core 2 with real-time FIFO priority
sudo chrt -f 99 taskset -c 2 ./benchmark_executable
```

To permanently isolate cores from the OS scheduler on Linux, boot with the kernel parameter:
```text
isolcpus=2,3 nohz_full=2,3 rcu_nocbs=2,3
```

#### Step 3: ASLR Control (Optional / Isolated Lab Environments)
```bash
# Temporarily disable virtual address randomization for deterministic cache set placement
sudo sysctl -w kernel.randomize_va_space=0

# Re-enable ASLR after benchmarking (Security Critical!)
sudo sysctl -w kernel.randomize_va_space=2
```

---

### 2.2 macOS Environment Setup

macOS does not provide direct user-space interfaces for disabling dynamic frequency scaling or arbitrary core pinning, but noise can be minimized:

1. **Prevent Thermal Throttling**: Keep the machine plugged into AC power; ensure ambient cooling; monitor thermal throttling with `powermetrics`:
   ```bash
   sudo powermetrics --samplers thermal,cpu_power -n 1
   ```
2. **Assign Quality of Service (QoS)**: Use `taskpolicy` to run benchmarks on Performance cores (P-cores) with high throughput priority:
   ```bash
   taskpolicy -c throughput ./benchmark_executable
   ```
3. **Disable Background Indexing & Updates**: Temporarily stop Spotlight indexing and close UI-heavy applications:
   ```bash
   sudo mdutil -a -i off
   # Remember to re-enable: sudo mdutil -a -i on
   ```

---

## 3. Benchmark Harness Engineering

### 3.1 The Warmup Protocol

Never record benchmark timings from a cold start. A correct harness separates execution into three distinct phases:

```text
[ Process Startup & Allocation ] 
          │
          ▼
[ Warmup Phase (W >= 5 iterations) ] ──> Caches populated, JIT compiled, memory paged
          │
          ▼
[ Measurement Phase (N >= 30 iterations) ] ──> High-resolution timestamps recorded
          │
          ▼
[ Statistical Aggregation & Verification ]
```

#### C/C++ Warmup Implementation Pattern
```c
#include <time.h>
#include <stdint.h>
#include <stdio.h>

static inline uint64_t get_time_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

// Prevent compiler from optimizing away computation
static inline void do_not_optimize(void *p) {
    __asm__ volatile("" : : "g"(p) : "memory");
}

void run_benchmark_suite(void (*bench_func)(void*), void *data, int warmups, int iterations) {
    // 1. Warmup Phase (untimed)
    for (int w = 0; w < warmups; w++) {
        bench_func(data);
        do_not_optimize(data);
    }

    // 2. Measurement Phase
    uint64_t samples[iterations];
    for (int i = 0; i < iterations; i++) {
        uint64_t start = get_time_ns();
        bench_func(data);
        do_not_optimize(data);
        uint64_t end = get_time_ns();
        samples[i] = end - start;
    }
    
    // 3. Process statistical distributions...
}
```

### 3.2 Compiler Optimization Barriers

Compilers can optimize away benchmark computation if results are unused, or hoist loop-invariant code out of measurement loops. Always use compiler memory barriers:

- **C / C++**: `__asm__ volatile("" : : "r,m"(val) : "memory");`
- **Rust**: `std::hint::black_box(&val);`
- **Go**: Assign to package-level exported sink variable `var Sink any; Sink = val`
- **Java / JVM**: Use JMH (Java Microbenchmark Harness) `Blackhole.consume(val)`

---

## 4. Statistical Rigor and Analysis

Never report a single "average" execution time. Timing distributions are bounded on the left by physical hardware limits (instruction latency, cache bandwidth) and unbounded on the right by system interruptions (OS interrupts, GC pauses, page faults). Consequently, benchmark distributions are typically right-skewed.

### 4.1 Required Statistical Metrics

| Metric | Formula / Definition | Purpose |
| :--- | :--- | :--- |
| **Sample Size ($N$)** | $N \ge 30$ | Ensures Central Limit Theorem applicability and statistical significance. |
| **Median ($p50$)** | Middle value of sorted samples ($x_{(N+1)/2}$) | Primary measure of central tendency; robust against severe right-side outliers. |
| **Mean ($\mu$)** | $\mu = \frac{1}{N}\sum_{i=1}^N x_i$ | Arithmetic average; sensitive to outliers. |
| **Standard Deviation ($\sigma$)** | $\sigma = \sqrt{\frac{1}{N-1}\sum_{i=1}^N (x_i - \mu)^2}$ | Measure of dispersion and execution stability. |
| **Coefficient of Variation ($\text{CV}\%$)** | $\text{CV}\% = \frac{\sigma}{\mu} \times 100\%$ | Normalized relative noise index. Must be $< 5\%$ for benchmark validity. |
| **Interquartile Range ($\text{IQR}$)** | $\text{IQR} = Q_3 - Q_1 = p75 - p25$ | Non-parametric dispersion measure representing spread of middle 50% of data. |
| **Tail Latency ($p95, p99$)** | 95th and 99th percentiles | Critical for SLA evaluation and identifying garbage collection or paging stalls. |
| **95% Confidence Interval ($\text{CI}_{95\%}$)** | $\bar{x} \pm t_{0.025, N-1} \cdot \frac{s}{\sqrt{N}}$ | Range containing true population mean with 95% confidence. |

### 4.2 Outlier Classification via Tukey's Fences

To objectively identify system interruption anomalies without discarding genuine software tail latency:
$$\text{Lower Bound} = Q_1 - 1.5 \times \text{IQR}$$
$$\text{Upper Bound} = Q_3 + 1.5 \times \text{IQR}$$
$$\text{Extreme Outlier Upper Bound} = Q_3 + 3.0 \times \text{IQR}$$

Measurements exceeding $Q_3 + 3.0 \times \text{IQR}$ almost always represent OS context switches, page faults, or thermal throttling rather than algorithmic latency.

### 4.3 Variance Sanity Thresholds

Before drawing conclusions about code changes, evaluate benchmark stability:
- **$\text{CV} \le 2.0\%$**: **Excellent**. Highly reproducible baseline.
- **$2.0\% < \text{CV} \le 5.0\%$**: **Acceptable**. Suitable for detecting performance deltas $\ge 10\%$.
- **$\text{CV} > 5.0\%$**: **Unstable/Noisy**. Do not proceed with optimization comparisons. Check background processes, thermal state, or increase sample size $N$.

---

## 5. Amdahl's Law and Optimization Scoping

Before spending effort optimizing a sub-component, calculate the theoretical maximum speedup using **Amdahl's Law**:

$$S_{\text{latency}} = \frac{1}{(1 - p) + \frac{p}{s}}$$

Where:
- $p$: Fraction of total execution time consumed by the target component ($0 \le p \le 1$).
- $s$: Speedup factor achieved on the target component ($s > 1$).
- $S_{\text{latency}}$: Overall end-to-end program speedup.

### Practical Implications
If profiling indicates a function consumes $15\%$ ($p = 0.15$) of runtime:
- Even if that function is optimized to run in zero time ($s \to \infty$):
  $$S_{\text{max}} = \frac{1}{(1 - 0.15) + 0} = \frac{1}{0.85} \approx 1.176\times \quad (\text{Maximum } 17.6\% \text{ overall gain})$$
- Conversely, optimizing a function that consumes $80\%$ ($p = 0.80$) by a modest $2\times$ ($s = 2$):
  $$S = \frac{1}{(1 - 0.80) + \frac{0.80}{2}} = \frac{1}{0.20 + 0.40} = \frac{1}{0.60} \approx 1.667\times \quad (66.7\% \text{ overall gain})$$

**Rule**: Never optimize code paths consuming less than $10\%$ of profiled runtime until the primary bottlenecks ($p \ge 30\%$) have been exhausted.

---

## 6. Automated Benchmark Runner Script

Use the included utility script `run_benchmark_with_stats.py` to execute commands with automatic warmup, sample collection, statistical distribution computation, and noise validation:

```bash
# Run 5 warmup iterations and 30 sample iterations
python3 skills/profiling-software-performance/scripts/run_benchmark_with_stats.py \
  --warmup 5 \
  --iterations 30 \
  --json-out baseline_stats.json \
  -- ./my_target_program arg1 arg2
```
