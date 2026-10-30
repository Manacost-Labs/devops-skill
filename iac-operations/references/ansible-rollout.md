# Ansible fleet rollout and failure boundaries

## Plan availability before parallelism

Identify service topology, healthy capacity, quorum/voters, replicas, replication lag, failure domains, load-balancer membership and independent management access. Calculate how many nodes can be unavailable at once while meeting acceptance criteria; include nodes already unhealthy or under maintenance. Application/data owners must confirm mixed-version reader/writer/schema/queue compatibility and recovery before mutating a stateful service.

Choose an explicit named canary and subsequent host batches across the intended topology. `serial: [1, 2, "20%"]` illustrates batch sizing, not a safe default: percentages use the selected host total and at least one host is used; the final listed size repeats. The first alphabetic/inventory host is not automatically a representative canary. Use an explicit reviewed order/host list and verify the actual batches; do not rely on file order or `shuffle`. Avoid putting multiple quorum members or the last healthy replica in the same batch.

Make the canary a distinct promotion phase: observe health and re-run identical desired-state inputs there to prove no unintended changes/restarts **before** any fleet expansion. `serial` alone will not pause for that proof; encode the canary/promotion boundary in the reviewed orchestration, without adding a human confirmation inside an unchanged valid envelope. Stop if the repeated run changes unexplained state.

Distinguish controls:

| Control | What it bounds | What it does not prove |
| --- | --- | --- |
| `serial` | Hosts completing a play per batch | Quorum, capacity or service acceptance |
| `forks` | Worker parallelism | Fleet-wide change rate or a cross-run lock |
| `throttle` | Workers on a task/block, bounded by forks/serial | Mutual exclusion with another job/controller |
| `strategy: linear` | Tasks progress together within the active batch | Global transaction/rollback or zero downtime |
| `strategy: free` | Hosts progress independently | Safe barrier ordering or shared-resource consistency |
| `run_once` with `serial` | One invocation per batch | One invocation for the entire deployment |

Use linear execution for reviewed batch barriers unless another strategy is explicitly proven. Shared migrations need their own exact identity, application lock, state evidence and data-recovery plan; a separate explicit singleton phase is easier to reason about. A conditional targeting one host still does not coordinate concurrent deployments or reruns. Include delegated resources and the configured fleet/resource lock.

## Per-batch execution

1. Recheck the exact host identities, authority window, lock, baseline health, available capacity, backups and dependency/credential versions. Freeze or reconcile inventory changes; unknown hosts stop advancement.
2. Drain the exact selected nodes through the approved load-balancer/service control plane. Verify no new traffic plus connection/job drain with a deadline. Prove remaining capacity and quorum. No blanket traffic disablement across an entire role.
3. Capture protected per-host baseline/backup references and stage immutable artifacts/configuration. Validate candidate syntax and required compatibility before activation. Never automatically copy production data to a testing environment.
4. Activate the reviewed service/package/configuration change. Handle reboot through the host module with a management path, reconnect deadline and post-boot identity/version evidence; a disconnect is not reboot success. Flush validated handlers before probing the new state.
5. Verify local readiness AND the real client path through the intended network/LB/TLS route. Observe error/latency/availability and application/data checks against defined thresholds for a fixed interval. HTTP 200 from a generic proxy is insufficient.
6. Return a node to service only after acceptance. Verify routing and continued capacity; update the ledger, then advance only if the entire batch and shared state are healthy. If authority expires, stop safely at the defined boundary and reconcile in-flight work.

`always` is suitable for bounded evidence capture/cleanup when it can run, not unconditional re-enabling traffic. A failed or unreachable server may never execute it. Ensure controller/out-of-band observation can preserve exclusion, locate async jobs and reconcile state after controller loss. External API calls can succeed even if the controller loses their response; inspect their actual state before repeating them.

## Failure thresholds are not health checks

Without stricter controls, one failed host is removed while others continue. Set `any_errors_fatal: true` for a zero-critical-failure rollout and retain an explicit failure after unsuccessful acceptance/recovery. It completes the failing task on the current batch before stopping; it cannot cancel other in-flight side effects.

`max_fail_percentage` is evaluated against each serial batch; the percentage must be **exceeded**, not merely reached. With a batch of two, one failure is 50%: a threshold of 50 permits that level, while 49 crosses it. Do not round a chosen error budget into accidental permission. Critical failures normally need zero tolerance, not a percentage tuned to keep CI green.

A successful `rescue` removes the failure from fatal/percentage control even though the recap records a rescued task. `ignore_errors`, `ignore_unreachable` and some `meta` termination paths can also leave a misleading successful run. Re-raise a failure after bounded safe recovery when a rollout must halt; verify actual next-batch exclusion in a real test. Reconcile the expected host set and critical outcome ledger outside recap/exit-code assumptions. Do not use an always-run later play to mutate after a fatal stop.

## Stop criteria and evidence

Stop new batches for configuration/activation failure, unreachable/unknown identity, missing or stale health evidence, capacity/quorum breach, unexpected schema/data/traffic effects, lock loss, expired authority or an unaccounted async job. Preserve the failed host's traffic exclusion. Record intended/observed hosts, before/desired/active version, artifact/configuration digest, batch/stage, drain status, health timestamps, task outcome, pending handlers/jobs and recovery references. No secret payloads or unrestricted hostvars.

Do not automatically reverse the whole fleet. Use `ansible-recovery.md` to classify mixed state and choose a compatible, scoped recovery with the relevant host, database and reliability owners.
