# MySQL and MariaDB diagnosis

Baselines: Oracle MySQL 8.4 and MariaDB 11.4. Detect vendor/version from the actual target; compatible client protocol does not make SQL/views/config/GTIDs interchangeable. Older releases require matching docs; do not claim their vendor support status.

## First probes

Select the matching bundled SQL. MySQL uses max_execution_time in milliseconds for eligible SELECT statements; MariaDB uses max_statement_time in seconds. These are diagnostic-session limits, not universal cancellation guarantees. Confirm permitted privileges and instrumentation; do not enable Performance Schema consumers or global logs during discovery.

For MySQL 8.4 inspect selected performance_schema.threads fields without PROCESSLIST_INFO, users or addresses, then bounded data_lock_waits links. For MariaDB 11.4 inspect selected information_schema.PROCESSLIST fields without INFO/user/host and INNODB_LOCK_WAITS transaction links. Metadata locks are a separate cause from InnoDB row locks; an empty row-lock table does not rule out lock contention. Restricted visibility or disabled instrumentation means incomplete evidence.

## Interval interpretation

Correlate Threads_connected/Threads_running, connection failures, Max_used_connections, Questions/slow-query counters, temporary-disk tables and InnoDB reads/requests with application throughput and latency. Sample GLOBAL values over the same interval and check uptime/reset continuity. Max_used_connections is a historical peak, not current demand; a lifetime ratio is not an incident rate.

High connections can reflect idle pools, retries or leaks rather than useful concurrency. High buffer-cache hit ratios do not prove healthy I/O. Investigate lock owners, long transactions, metadata/DDL waits and storage flush pressure before raising buffers/limits.

General/slow logs and statement digests can disclose SQL values. Collect only approved redacted evidence; raw InnoDB status is not a safe default. EXPLAIN ANALYZE/ANALYZE semantics differ by engine and can execute the statement; review version, query and isolation first. Do not run untrusted statements or reset counters to make comparisons simpler.

## Change boundary

Cancellation/termination, OPTIMIZE/REPAIR, DDL, log purge, instrumentation changes, parameter writes and restart are mutations requiring owner, plan, recovery and acceptance. MySQL SET PERSIST behavior must not be copied to MariaDB. Galera, Group Replication and InnoDB Cluster recovery are specialist topologies, not a generic replica restart.

Sources: [MySQL threads](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-threads-table.html), [row lock waits](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-data-lock-waits-table.html), [status](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html), [MariaDB processlist](https://mariadb.com/docs/server/reference/system-tables/information-schema/information-schema-tables/information-schema-processlist-table), [MariaDB lock waits](https://mariadb.com/docs/server/reference/system-tables/information-schema/information-schema-tables/information-schema-innodb-tables/information-schema-innodb_lock_waits-table).
