# PostgreSQL single-writer cutover and recovery after promotion

Confirm the replication/orchestration owner, all writers, connection pools/proxies, DNS/service discovery, scheduled jobs, logical subscriptions and application external effects. Provider and HA-controller APIs keep their own executor; these checks do not authorize manual promotion behind a controller.

For planned switching, quiesce writers and record an authoritative final commit/WAL position. Prove candidate receive/replay state covers it and application checks pass. For an unavailable writer, distinguish an unknown outcome from a confirmed loss bound; obtain explicit loss acceptance when the last acknowledged commits cannot be proved. Time-lag displays alone do not establish either condition.

Fence the former writer independently of the database path being changed. Include restart/autoscale/controller behavior: a stopped process that can be automatically restarted is not lasting production fencing. If fencing or quorum/ownership is uncertain, stabilize and hand off rather than promote. Stop or drain every relevant client/writer, then perform only the approved orchestrator/promotion fragment.

Verify exactly one writable primary, candidate system/timeline identity, required committed data, fresh-write/read behavior, replica and slot state, client convergence and the agreed health window. Logical failover slots need their version-specific readiness checks. Archive new timeline/history and retain the previous recovery path until a new independent recovery proof exists.

After new writes, changing a pointer back is not rollback: identify both histories and reconcile newest writes/external effects. Rejoin the old primary through a reviewed fresh base backup or compatible `pg_rewind` procedure; check its prerequisites and required WAL first. Keep the old copy fenced. Rewind can overwrite data/configuration and may leave an unusable target on failure, so preserve a recovery copy and gate it separately. A service restart does not resolve divergent histories.

Sources: [failover and old-primary fencing](https://www.postgresql.org/docs/18/warm-standby-failover.html), [pg_rewind prerequisites and failure behavior](https://www.postgresql.org/docs/18/app-pgrewind.html). Verified 2026-10-30. Native CI tests PITR-target promotion after stopping the synthetic source; it does not certify streaming failover, controller quorum, rewind or production fencing.
