# Data resilience official sources

Last verified: 2026-10-29. Refresh exact server/client/backup-tool and topology documentation before material change.

Baselines: Oracle MySQL 8.4 logical/file-position recovery; MariaDB 11.4 logical and physical full/incremental recovery. PostgreSQL/Redis retain their existing engine contracts. Other versions/products/topologies need explicit compatibility discovery; this is not a vendor support-lifecycle guarantee.

## postgresql-operations

- [www.postgresql.org](https://www.postgresql.org/docs/current/maintenance.html)

## redis-operations

- [redis.io](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
- [redis.io](https://redis.io/docs/latest/operate/oss_and_stack/management/scaling/)

## backup-inventory

- [www.postgresql.org](https://www.postgresql.org/docs/current/backup-dump.html)
- [redis.io](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/backup-methods.html)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html)
- [mariadb.com](https://mariadb.com/docs/server/clients-and-utilities/backup-restore-and-import-clients/mariadb-dump)
- [mariadb.com](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/full-backup-and-restore-with-mariadb-backup)

## isolated-restore-testing

- [www.postgresql.org](https://www.postgresql.org/docs/current/backup-dump.html)
- [redis.io](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/reloading-sql-format-dumps.html)
- [mariadb.com](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/full-backup-and-restore-with-mariadb-backup)

## recovery-objective-validation

- [www.postgresql.org](https://www.postgresql.org/docs/current/continuous-archiving.html)
- [redis.io](https://redis.io/docs/latest/operate/oss_and_stack/management/replication/)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/point-in-time-recovery-binlog.html)
- [mariadb.com](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/point-in-time-recovery-pitr-mariadb-backup)

## point-in-time-recovery

- [www.postgresql.org](https://www.postgresql.org/docs/current/continuous-archiving.html)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/point-in-time-recovery-binlog.html)
- [mariadb.com](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/point-in-time-recovery-pitr-mariadb-backup)

## data-migration

- [www.postgresql.org](https://www.postgresql.org/docs/current/logical-replication.html)

## data-failover

- [www.postgresql.org](https://www.postgresql.org/docs/current/warm-standby.html)
- [redis.io](https://redis.io/docs/latest/operate/oss_and_stack/management/replication/)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/replication-solutions-switch.html)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/replication-gtids-concepts.html)
- [mariadb.com](https://mariadb.com/docs/server/ha-and-performance/standard-replication/gtid)
- [mariadb.com](https://mariadb.com/docs/server/ha-and-performance/standard-replication/setting-up-replication)

## retention-enforcement

- [www.postgresql.org](https://www.postgresql.org/docs/current/continuous-archiving.html)
- [redis.io](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/purge-binary-logs.html)
- [mariadb.com](https://mariadb.com/docs/server/server-management/server-monitoring-logs/binary-log)

## data-masking

- [csrc.nist.gov](https://csrc.nist.gov/pubs/sp/800/188/final)

## mysql-backup-and-recovery

- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/backup-methods.html)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/reloading-sql-format-dumps.html)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/point-in-time-recovery-binlog.html)

## mariadb-backup-and-recovery

- [mariadb.com](https://mariadb.com/docs/server/clients-and-utilities/backup-restore-and-import-clients/mariadb-dump)
- [mariadb.com](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/full-backup-and-restore-with-mariadb-backup)
- [mariadb.com](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/incremental-backup-and-restore-with-mariadb-backup)
- [mariadb.com](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/files-created-by-mariadb-backup)
- [mariadb.com](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/mariadb-backup-options)

## binlog-recovery-chain-validation

- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/point-in-time-recovery-positions.html)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/mysqlbinlog.html)
- [mariadb.com](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/point-in-time-recovery-pitr-mariadb-backup)
- [mariadb.com](https://mariadb.com/docs/server/clients-and-utilities/logging-tools/mariadb-binlog/mariadb-binlog-options)

## mysql-mariadb-asynchronous-cutover

- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/replication-solutions-switch.html)
- [dev.mysql.com](https://dev.mysql.com/doc/refman/8.4/en/replication-gtids-concepts.html)
- [mariadb.com](https://mariadb.com/docs/server/ha-and-performance/standard-replication/gtid)
- [mariadb.com](https://mariadb.com/docs/server/ha-and-performance/standard-replication/setting-up-replication)
