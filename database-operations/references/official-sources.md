# Official source index

Last verified: 2026-10-29. Refresh the exact operation page before every material change.

PostgreSQL 18, Oracle MySQL 8.4 and MariaDB 11.4 diagnostic baselines. SQL smoke tests target those engines; no support-lifecycle or compatibility claim for other versions.

The manifest maps every capability to the following official sources. A source mapping establishes provenance, not semantic correctness or live-target verification.

## postgresql-engine-diagnosis

- [www.postgresql.org](https://www.postgresql.org/docs/18/monitoring-stats.html)
- [www.postgresql.org](https://www.postgresql.org/docs/18/monitoring-locks.html)
- [www.postgresql.org](https://www.postgresql.org/docs/18/sql-explain.html)

## mysql-mariadb-engine-diagnosis

- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-threads-table.html)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-data-lock-waits-table.html)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html)
- [mariadb.com](https://mariadb.com/docs/server/reference/system-tables/information-schema/information-schema-tables/information-schema-processlist-table)
- [mariadb.com](https://mariadb.com/docs/server/reference/system-tables/information-schema/information-schema-tables/information-schema-innodb-tables/information-schema-innodb_lock_waits-table)

## database-connection-capacity

- [www.postgresql.org](https://www.postgresql.org/docs/18/runtime-config-connection.html)
- [www.pgbouncer.org](https://www.pgbouncer.org/config.html)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html)

## database-maintenance-planning

- [www.postgresql.org](https://www.postgresql.org/docs/18/routine-vacuuming.html)

## database-engine-configuration-review

- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/persisted-system-variables.html)
- [mariadb.com](https://mariadb.com/docs/server/ha-and-performance/optimization-and-tuning/system-variables/server-system-variables)

## database-replication-diagnosis

- [www.postgresql.org](https://www.postgresql.org/docs/18/monitoring-stats.html)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/replication-administration-status.html)
- [mariadb.com](https://mariadb.com/docs/server/reference/sql-statements/administrative-sql-statements/show/show-replica-status)

