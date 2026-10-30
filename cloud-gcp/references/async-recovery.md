# Operation observation and recovery

Persist a per-step intent before dispatch: operation ID, project ID/number, zone/region/global scope, target name and known numeric incarnation IDs, exact input digest, request UUID when supported, before-state, credential reference, dependency order, UTC deadline and recovery owner. Record native operation/request IDs on acknowledgement. Keep local phases such as `intent`, `observing`, `uncertain` and `compensating` distinct from provider state, platform final status and execution authority.

Keep one in-flight mutation per project IAM policy, firewall rule or instance. These are local coordination limits, not provider rate guarantees or a lock on console/other controller writers. A managed resource belongs to its declared controller; do not bypass its state or concurrency rules.

Compute Operations are scope-specific: select `zoneOperations`, `regionOperations` or `globalOperations` from the retained operation identity, never by guessing a name. `get` returns the current state. `wait` can return before `DONE`, including immediately under load. Continue a bounded observation loop, inspect errors on `DONE` and then read the actual target. A completed operation can later age out; operation absence is not resource absence.

Set an overall window and budget request attempts, operation polling, consistency reads, service verification and compensation separately. A conservative local default for GET observation is exponential backoff with jitter from 2 to at most 30 seconds, at most 20 reads or the approved UTC deadline, whichever comes first. These values are operator defaults, not Cloud latency promises. Account for SDK/CLI automatic retries and nested loops. When using wait, bound each call to the remaining local deadline and evaluate every returned status. Never restart the budget with a new process.

| Observation | Next step |
|---|---|
| Read throttling/transient service failure | Same scoped read with bounded backoff; lower concurrency |
| IAM409 ABORTED | Fresh full policy read-modify-write, preserving unrelated state and intent |
| Fingerprint conflict on supported instance update | Fresh exact instance GET and recomputed delta; never discard the precondition |
| Write response lost | Retain request identity; reconcile method-specific operation and actual effects before considering any retry |
| DONE with error, timeout, expired/missing operation | Inventory actual resources and partial effects; never infer no effect |
| Some dependent steps succeeded | Stop new changes; compare current state and compensate only attributable owned effects |
| Compensation response lost | Reconcile that compensation; do not claim rollback from dispatch alone |

Validation/permission errors and exhausted quota need correction or a new plan. Capacity failure does not authorize another zone; a request UUID does not authorize changed input. Preserve original identities across restart. Recovery has its own current authority and verification requirements, and must not overwrite concurrent/preexisting resources.

Use `verified` only after full desired-state and user-path evidence; `rolled_back` only after authorized recovery and retained data/service checks; `partially_verified` for known effects without full convergence/health evidence; `blocked` when safe continuation is unavailable. Include uncertain IDs, latest observed state/time, cost exposure, next safe read and accountable handoff.

Sources checked 2026-10-30: [operation polling and scope](https://cloud.google.com/compute/docs/api/how-tos/api-requests-responses), [native Operation fields/retention](https://cloud.google.com/compute/docs/reference/rest/v1/zoneOperations), [IAM retry semantics](https://cloud.google.com/iam/docs/retry-strategy), [IAM propagation](https://cloud.google.com/iam/docs/access-change-propagation).
