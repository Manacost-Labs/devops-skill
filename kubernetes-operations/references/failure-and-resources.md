# Pod failure, probes and resource pressure

Capture Pod UID, controller UID/revision, node, creation/deletion times, generation, container names/IDs, state AND lastState for regular/init/ephemeral containers, restart count and probe definitions. A replacement Pod can reuse a name but has new history. Bound logs by exact container, time, tail and bytes; `--previous` selects the previous instance in that Pod, not all historic replicas. Messages/logs may contain credentials or tenant data.

| Observation | Discriminate next |
|---|---|
| CrashLoopBackOff | Previous termination, entrypoint/config/dependency, probe kills and backoff; it is not the root cause |
| OOMKilled | Current versus previous container, cgroup ceiling/peak/events and same-window node memory evidence |
| Exit 137 without OOM reason | SIGKILL/stop deadlines/operator/runtime/host evidence; do not infer OOM |
| Pending/FailedScheduling | Events for this UID, requests versus allocatable, taints/affinity/topology/quota and PVC binding |
| Evicted | Node memory/disk/inode/PID pressure and eviction reason; different from a container limit OOM |
| Running, not Ready | Probe outcome, readiness gates, startup state, endpoints and actual dependency/application path |
| Init incomplete | Ordered init/sidecar semantics, mounts/config and previous init termination |
| Image/admission error | Exact digest/architecture/pull identity, policy and webhook availability; no bypass |

Startup probes can protect slow initialization from liveness/readiness checks until startup succeeds. Readiness affects traffic eligibility; liveness can restart a container. A probe depending on a failing shared database can cause a restart cascade. Verify actual pod rules and controller behavior rather than deleting probes to get green status.

## Resource investigation

Compare admitted per-container AND pod-level resources when supported, requests/limits, QoS, LimitRange/quota and node allocatable. Requests guide scheduling; they are not measured consumption. Memory enforcement is reactive; CPU limits can throttle. Include native/runtime heap, cache, concurrent requests and memory-backed emptyDir in the budget. Quantity units/case matter; do not confuse memory `400m` with `400Mi`.

Metrics API/top may be unavailable or too coarse to capture a peak. Use historical workload/node telemetry and authorized cgroup/kernel evidence; no metrics is unknown. Resource changes/in-place resize depend on version/features and controller source, not a universal kubectl repair.

Node-pressure eviction can bypass PDB protections; changing a request or deleting an evicted Pod does not fix exhausted nodes. Include disk bytes/inodes, logs/writable layers/emptyDir, PIDs and ephemeral-storage accounting. Never fill a production node or allocate unbounded memory to reproduce an incident.

Confirm root cause and canary the approved resource/probe/application change. Verify scheduling, restarts, headroom, retained data, endpoints and user behavior through the agreed window.

Sources: [running-Pod diagnosis](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/), [Pod lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/), [resources](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/), [probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/), [node-pressure eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/), [bounded logs](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/).
