# AWS asynchronous effects and recovery

An acknowledged API request, completed CLI process and converged service are different observations. IAM replication and EC2 propagation do not provide a universal completion operation ID. Preserve native request IDs plus stable resource IDs, the exact input digest and before-state; do not invent a provider-wide job waiter.

Before dispatch, persist a per-step journal outside the skill package: account/partition/Region, operation and exact input digest, credential reference, target IDs, before-state digest, token if supported, UTC deadline, dependencies and compensating action. Record `intent`, `acknowledged`, `observing`, `observed`, `uncertain` or `compensating` as step phases. These are local evidence phases, not provider state, approval or the platform's final status. A durable intent without a response stays uncertain after restart.

Set one overall execution window and separate budgets for request attempts, consistency reads, health checks and recovery. For runbook consistency reads, start at 2 seconds and exponentially back off with jitter to at most 30 seconds, at most 12 reads and the approved deadline, whichever arrives first. These are conservative local defaults, not AWS latency promises. Stop on identity/permission drift, token/parameter mismatch, unexpected resources or a terminal state. Retain evidence and hand off when the read budget ends; do not reset it by restarting the process. Authentication, validation and quota errors need correction/new planning, not blind retries. Bound SDK/CLI automatic attempts too and include them in the journal; a shell wrapper retry must not multiply hidden SDK attempts.

| Failure | Required next observation | Mutation rule |
|---|---|---|
| Read throttled | Same bounded read with account/Region-aware backoff | Reduce concurrency; do not alter quotas/targets |
| Write response lost | Exact API/resource read and retained request evidence | No generic replay; apply the operation-specific token or no-token procedure |
| Dependency read says not found after create | Appropriate exact `Describe` with backoff | Absence is not proof create failed or delete succeeded |
| Some steps succeeded | Complete owned-effect inventory and current-state comparison | Halt new work; compensate only attributable effects in safe reverse dependency order |
| Recovery response lost or budget expired | Reconcile the compensating effect itself | Do not restart compensation or claim rollback without evidence |

Check the exact API's partial-result/error fields; do not assume a multi-resource request is atomic. Use single-resource steps where practical. Recovery is another effectful operation: it must be within current authority and cannot delete unknown/preexisting resources. If current state differs from the expected post-state, stop compensation to avoid overwriting a concurrent writer. An approved original write does not authorize arbitrary cleanup, scope migration or a quota increase.

Close with `verified` only after full desired-state and user-visible acceptance evidence; `rolled_back` only after the authorized recovery state and retained data/service behavior are rechecked; `partially_verified` for known effects with incomplete convergence/health evidence; `blocked` when execution cannot safely start or proceed. Preserve uncertain resource IDs, incurred-cost exposure, last read time, next safe read and accountable handoff.

Sources checked 2026-10-30: [EC2 request errors and throttling](https://docs.aws.amazon.com/ec2/latest/devguide/query-api-troubleshooting.html), [EC2 consistency](https://docs.aws.amazon.com/ec2/latest/devguide/eventual-consistency.html), [IAM propagation](https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot.html#troubleshoot_general_eventual-consistency). Refresh operation-specific retry guidance immediately before a material call.
