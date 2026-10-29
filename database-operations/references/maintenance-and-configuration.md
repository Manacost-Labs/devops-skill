# Maintenance and configuration

Name desired behavior and measured constraint before selecting a setting. Record current/effective/source/pending value where available, engine version, managed/self-hosted owner, session/global/persistent scope, privileges, restart/recreation effect and client consequences.

A local file, PostgreSQL ALTER SYSTEM, MySQL SET GLOBAL/SET PERSIST and managed parameter group have different precedence/persistence. MariaDB semantics differ. Never copy one engine's command to another. Provider API changes belong to the provider pack; engine diagnostics and acceptance stay here. Configuration management remains source of truth.

## Procedure

1. Confirm target/topology, exact setting or maintenance operation, data/availability risk and acceptable window.
2. Establish usable engine-specific recovery and application compatibility. For MySQL/MariaDB use the installed data-resilience 0.4.0+ procedure matching the method/topology, or a verified specialist runbook when unsupported.
3. Predict locks, I/O, CPU, temporary disk/WAL/binlog growth, replication delay and restart/client drain. Review alternatives with smaller impact.
4. Rehearse on representative isolated data; preserve original values/config and an executable reversal or recovery plan. Some maintenance cannot be undone by restoring a setting.
5. Gate the exact plan; stage/canary where meaningful. Observe agreed abort thresholds and stop on topology/plan drift.
6. Verify effective and persistent values, required restart state, replica/client health, data checks and user latency/correctness. Watch an agreed window and reconcile configuration source.

VACUUM FULL rewrites and needs strong locks; dead tuple estimates alone do not justify it. ANALYZE affects plans; index builds/reindex and MySQL/MariaDB OPTIMIZE/DDL can have material locking/space impact despite online claims. Refresh exact engine/storage-engine/version behavior before planning. Cancellation may roll back a long transaction and add load; terminating the oldest session is not automatically safe.

Never disable fsync/synchronous durability, bypass checks, purge logs blindly, reset stats or repair live tables as incidental tuning. Schema/query/index changes belong with application and migration owners.

Sources: [PostgreSQL vacuum](https://www.postgresql.org/docs/18/routine-vacuuming.html), [MySQL persistence](https://dev.mysql.com/doc/refman/8.4/en/persisted-system-variables.html), [MariaDB variables](https://mariadb.com/docs/server/ha-and-performance/optimization-and-tuning/system-variables/server-system-variables).
