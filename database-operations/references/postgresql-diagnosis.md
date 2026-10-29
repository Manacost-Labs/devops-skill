# PostgreSQL diagnosis

Baseline: PostgreSQL 18 documentation. Discover actual server_version_num and extension/provider differences before using views/columns. Do not label newer/older releases compatible solely from major version proximity.

## Connections, waits and transactions

Start with the bundled short read-only transaction. It sets local statement/lock timeouts, reports selected settings and bounded activity without SQL text, and rolls back immediately. Ordinary users cannot see all other-session details; record this limitation. Compare state counts with application pool active/idle/waiting, connection errors and transaction latency.

A long transaction can hold snapshots/locks even when idle; an active query's age and transaction age differ. Correlate wait_event_type/event with timestamped blocking PIDs. pg_blocking_pids can add overhead on busy systems; do not poll all sessions at high frequency. A lock chain identifies dependency, not permission to kill its root. Prepared transactions and background workers require additional owner-aware investigation.

## Workload and I/O

Use two scoped pg_stat_database samples with stats_reset and postmaster start time; a restart/reset or changed coverage invalidates naive deltas. Cache-hit ratio alone does not prove low disk latency. Correlate reads/temp files/deadlocks and host/provider I/O. pg_stat_io exists only on applicable versions and differs across releases; verify columns first.

If pg_stat_statements is already installed/authorized, use numeric aggregates/query IDs under approved data handling. Do not enable it, change preload settings, reset counters or expose query text incidentally. Instrumentation overhead/visibility changes require a plan.

## Vacuum and planning

Use dead tuple estimates, last vacuum/analyze, transaction age, autovacuum activity and workload trend together. Estimates are not measured bloat; a fixed dead-row threshold is not proof that VACUUM FULL is needed. Long snapshots, slots and prepared transactions can prevent cleanup. Escalate wraparound risk promptly without disabling autovacuum/durability. Ordinary vacuum/analyze still consume I/O and affect plans; schedule and verify them.

For a slow query, get a redacted approved statement and context from its owner. First inspect indexes/statistics/estimated plan without executing untrusted SQL. EXPLAIN ANALYZE runs the statement, can change data or call external effects and can worsen an incident; rollback does not undo every effect. Even plain planning may evaluate immutable functions. Use a representative isolated target for uncertain execution and explicitly approve any production measurement. Do not prescribe an index from one plan without workload/write/lock/recovery review.

Sources: [statistics](https://www.postgresql.org/docs/18/monitoring-stats.html), [locks](https://www.postgresql.org/docs/18/monitoring-locks.html), [vacuum](https://www.postgresql.org/docs/18/routine-vacuuming.html), [EXPLAIN](https://www.postgresql.org/docs/18/sql-explain.html).
