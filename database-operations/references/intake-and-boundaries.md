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
| MySQL/MariaDB logical/binlog recovery, MariaDB physical full/incremental recovery, standard asynchronous cutover | data-resilience-operations 0.4.0+ with confirmed versions, topology and recovery proof |
| MySQL physical products, cross-vendor migration, Galera/InnoDB Cluster surgery | Verified product/topology specialist; no generic fallback |

Recovery capability is not inferred from generic wording or a provider API. Missing installed recovery capability or unsupported topology blocks stateful work, not bounded diagnosis. Shared/reused credentials do not authorize every database visible to the account.

Return evidence and its privilege/coverage limits, hypotheses/contradictions, the next discriminating probe, change owner and acceptance. When a role or topology remains unknown, stop mutation and preserve safe discovery findings.
