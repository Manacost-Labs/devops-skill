# Crashes, restarts and resource pressure

Preserve full container ID, creation/start/finish times, runtime state, restart count/policy, image ID plus registry digest, candidate/config revision and incident interval. Recreation resets container-local history. Correlate application, daemon and host evidence in the same interval; a current sample can miss the peak that killed a previous process.

| Observation | Next discrimination | Avoid |
|---|---|---|
| Exit 137 | Runtime OOM flag, kernel/cgroup OOM evidence, operator kill/stop timeout and timestamps | Declaring every SIGKILL an OOM |
| Exit 143 | SIGTERM source, graceful shutdown and deadline | Calling all controlled stops crashes |
| Repeated nonzero exit | Entrypoint/application error, missing config/dependency, permission, architecture | Restarting away evidence |
| Exit 0 then restarts | Intended one-shot versus long-running process and restart policy | Treating zero as service success |
| Running but unhealthy | Exact probe, timeout, process/listener and dependency | Assuming Engine restarts unhealthy containers automatically |
| Container starts but request hangs | Worker/thread/pool, CPU throttling, PID exhaustion, I/O and downstream waits | Raising memory as the universal remedy |

Use exact IDs and bounded `docker logs --since ... --tail ... --timestamps` under the explicit context. Logs may contain credentials/data and may be absent/rotated/unavailable with a driver; empty logs are not successful startup. Keep raw inspect output protected: environment, labels, arguments and healthcheck output are sensitive. Avoid `--details` and broad event/log streams; bound event start/end and target.

## Memory

Compare effective HostConfig limits with the reviewed Compose candidate; configured reservation is not a hard ceiling. MemorySwap is a combined memory/swap setting with special unset/zero/-1 behavior; it is not measured swap use. Check host capacity and other workloads before raising a ceiling. Never disable the OOM killer to mask exhaustion.

On Linux correlate runtime OOMKilled with the owning cgroup's version/path, current/peak memory, limit, `memory.events` counters and kernel OOM records where authorized. A counter may include earlier/descendant activity; record scope, timestamps and deltas. Container-internal `free` and CLI stats are not interchangeable with cgroup accounting. Distinguish leak/growth, working set/cache, tmpfs, runtime heap/native allocations and concurrency spikes. Tune application budgets against the real ceiling and canary under representative load.

For CPU/PID symptoms check quota/throttling, runnable contention, process/thread count and limit, then owner-level code/concurrency. Do not install profilers, dump process memory, expose profiling ports or attach privileged debuggers without separate approval and sensitive-evidence handling.

After repair verify restart/exit evidence over an interval, expected dependency behavior, allowed/denied access, request correctness and resource headroom; “container stays up” is only one signal.

Sources: [exit codes](https://docs.docker.com/engine/containers/run/), [restart behavior](https://docs.docker.com/engine/containers/start-containers-automatically/), [resource limits](https://docs.docker.com/engine/containers/resource_constraints/), [stats accounting](https://docs.docker.com/reference/cli/docker/container/stats/), [logs](https://docs.docker.com/reference/cli/docker/container/logs/), [cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html).
