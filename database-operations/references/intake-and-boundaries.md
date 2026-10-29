# Intake, access and evidence

Record target fingerprint, engine/version/vendor, endpoint role, proxy/pooler, managed/self-hosted boundary, owner, application, environment, topology, incident onset, recent changes, data classification and allowed observation window. Do not infer primary from endpoint name or admin privilege from successful login.

Use an approved client profile/service file or secret provider without publishing its contents. Keep host verification enabled; use approved SSH/socket/TLS access. Diagnostic privileges vary: pg_monitor/pg_read_all_stats and MySQL/MariaDB PROCESS or Performance Schema grants can expose other workloads. Request only what is needed; restricted/missing rows must be labeled incomplete, not zero load.

## Bounded collection

Bundled SQL deliberately excludes query text, client addresses, usernames, connection strings and row values. IDs and states can still be internal information. Review locally, scope to the affected database/workload where possible and redact before storage. Never collect raw SHOW ENGINE INNODB STATUS, full processlist, slow logs or pg_stat_statements query text without a separate data-handling decision.

Run one short sample, close the session/transaction, then a second sample with UTC timestamps. Cumulative deltas need consistent reset/start times and scope. Do not leave idle diagnostic transactions open: they can retain snapshots and locks. Read-only mode does not protect against arbitrary functions or expensive scans. Timeouts reduce risk but cannot establish absence of all effects.

## Ownership matrix

| State | Owner |
|---|---|
| Engine waits, budgets, routine maintenance intent | database-operations |
| SQL/query/schema/client pool change | Application/data owner; compose migration recovery when state changes |
| OS/disk/cgroup/container settings | Linux/Docker/Kubernetes |
| Managed instance size, parameter group, maintenance API | Named provider pack, with engine validation |
| Credentials/role lifecycle | secrets-access with engine/provider executor |
| PostgreSQL/Redis backup, restore, PITR, migration, failover | data-resilience-operations |
| MySQL/MariaDB backup, restore, migration, failover or Galera/InnoDB Cluster surgery | Confirmed engine-specific recovery owner/runbook; unsupported here |

Recovery capability is not inferred from generic wording or a provider API. Missing MySQL recovery is a blocker for stateful work, not for bounded diagnosis. Shared/reused credentials do not authorize every database visible to the account.

Return evidence and its privilege/coverage limits, hypotheses/contradictions, the next discriminating probe, change owner and acceptance. When a role or topology remains unknown, stop mutation and preserve safe discovery findings.
