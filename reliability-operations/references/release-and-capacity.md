# Release and capacity acceptance

Define the user outcome, baseline, canary cohort, expected traffic, observation window, stop/rollback thresholds and decision owner before rollout. Compare equivalent periods/cohorts; quiet traffic cannot prove peak capacity. Account for warmup, caches, dependency changes and instrumentation/schema changes.

Verify the deployed artifact/version with its executor, then user-path availability/correctness, latency distribution, error ratio, traffic and saturation. Include background jobs, queues and data consistency where relevant. The HTTP helper provides samples only; do not run it against a state-changing endpoint or treat three responses as an SLO.

Capacity review combines throughput, resource/queue trends, headroom, scaling delay, maximum replicas, dependency limits and expected failover load. State measured versus projected figures and assumptions. A linear extrapolation is a hypothesis, not a load test. Live load tests require explicit target/rate/duration/abort authorization.

For telemetry changes compare cardinality/bytes/drops/query cost and effective retention. For service changes hand remediation to its owner; reliability supplies acceptance. When the service and monitoring disagree, investigate coverage/time/scope before declaring success.

Return baseline and comparison artifacts, interval/cohort, decision and unresolved gaps. Missing production traffic or integration evidence means partially_verified.
