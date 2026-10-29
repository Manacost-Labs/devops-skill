# Resource diagnosis

Record timestamps, CPU affinity/count, virtualisation and sampling duration. Prefer available `vmstat 1 5`, `iostat -xz 1 5`, scoped pidstat and PSI over installing a monitoring stack. Initial reports may average since boot; use subsequent intervals. Missing sysstat or PSI means missing evidence.

## CPU/load

Separate user/system CPU, runnable tasks, uninterruptible tasks, hypervisor steal and cgroup throttling. Linux load includes uninterruptible tasks: high load with idle CPU can be I/O trouble. Correlate throughput/latency, run queue and pressure. Top CPU percentages depend on mode/CPU count. Identify service/workload before signaling a PID.

Inspect selected systemd properties: ControlGroup, CPUQuotaPerSecUSec, MemoryCurrent, MemoryHigh, MemoryMax and TasksMax when supported. Resolve the service's actual cgroup and ancestor constraints; do not infer its limits from the root group. On cgroup v2 compare two `cpu.stat` samples with `cpu.max` and cpuset constraints. Throttling can delay a service while the host is idle. Never edit cgroup files behind systemd/container management.

## Memory/OOM

Distinguish available memory, reclaimable cache, anonymous memory, swap activity and sustained memory PSI. Low free memory alone is not a leak; RSS can double-count shared pages. Request bounded PSS/smaps only if necessary and permitted.

Separate kernel global OOM, memcg OOM, systemd-oomd and ordinary allocation/limit failure. Record timestamp, constraint, affected unit and victim; an old OOM does not explain a new incident. Exit 137 alone does not establish OOM.

In v2 inspect `memory.current`, `memory.max`, `memory.high`, `memory.events` and ancestors. Compare event deltas: high, max, oom and oom_kill differ; max can mean unlimited. V1 has different files. Distinguish MemoryHigh reclaim pressure from MemoryMax hard limits. Check workload/connection growth before increasing limits. Do not drop caches, disable OOM controls or prescribe swap as a universal latency repair.

## I/O and process limits

Correlate device latency/queues, throughput, blocked tasks and I/O PSI with the same application interval. Device utilisation near 100% is not a universal saturation test for parallel devices; averages hide tails. Check cgroup/provider throttling before scheduler/provisioning changes. D-state processes may not exit until I/O returns.

Compare scoped open-file/task/socket demand against process/systemd limits; no environment or full-argv dumps. Raising limits can move the bottleneck. Route container constraints to Docker/Kubernetes and provider caps to the provider module.

Return each hypothesis with confirming signal, contradiction, scope/time window and next discriminating probe. Approve one intervention, repeat the same workload/measurements and verify user impact.

Sources: [cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html), [PSI](https://docs.kernel.org/accounting/psi.html), [systemd controls](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html), [procfs](https://docs.kernel.org/filesystems/proc.html). Check installed versions before new upstream options.
