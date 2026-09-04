# Measurement design and environmental noise

Define what is being measured before choosing controls. Startup tests should include startup; steady-state tests should warm and measure the same process. Record inputs, build flags, runtime, hardware, power state and relevant system load. Use representative data and keep correctness checks outside the timed region when appropriate.

Default to observing the host and running a process-local profiler. CPU affinity can be useful when it matches the deployment question; it can also hide scheduler or heterogeneous-core behavior. Do not routinely change CPU governors/turbo, Spotlight, real-time priorities or system-wide ASLR. If a host-wide experiment is necessary, obtain explicit authorization for that operation, capture the actual previous settings, bound the experiment and restore those settings on success or failure. Never assume a hard-coded restoration value.

Collect enough observations to assess the effect relevant to the decision. There is no universal 30-sample or CV threshold. Keep raw samples, describe outliers instead of silently dropping them, and inspect order/drift. Alternate baseline/candidate runs or randomize order with a recorded seed. Independent-process runs include startup and cannot warm later processes' JIT state.

Use the same estimator for reported effect and uncertainty. The bundled runner uses a mean percentile bootstrap; the comparator uses median-ratio resampling. Both intervals are approximate, assume independent samples and can understate uncertainty with small or correlated samples. Two observations permit a variance calculation but do not establish reliable confidence or tail estimates. Tail claims need enough observations in the relevant tail. CV is descriptive and does not establish precision or causal attribution.

Interpret IPC, cache misses, GC and sampling profiles in the actual CPU/runtime context; there are no universal pass/fail cutoffs. Amdahl's law can estimate end-to-end benefit from a fraction p and local speedup s: `1 / ((1-p) + p/s)`. The target can instead be tail latency, memory or cost, for which a small aggregate CPU hotspot may still matter.
