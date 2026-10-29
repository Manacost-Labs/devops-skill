# Replication health and consistency

Confirm topology, primary identity, replica/channel, transport, replay/apply, expected write activity and consumer consistency requirements. Collect role and timestamp evidence; endpoint names and running threads alone prove neither role nor freshness.

PostgreSQL: distinguish sent/write/flush/replay positions and bytes from time estimates. NULL lag does not mean zero lag; time since last replay can grow on an idle primary without backlog. Compare advancing primary/replay positions, receiver state and representative owner-approved consistency checks. Retained WAL can be caused by slots/archiving/lag; do not drop slots or delete WAL to clear disk pressure.

MySQL: inspect each channel's receiver/applier status, errors and version-specific positions/GTIDs under restricted data handling. Seconds_Behind_Source alone cannot prove consistency or catchup; consider stopped/disconnected threads, delayed replication, parallel apply and measurement scope. MariaDB uses different GTID domains/status fields; do not translate Oracle GTID set logic. Full status output can disclose source addresses/users/error SQL; select/redact needed evidence locally.

A lagging replica is not permission to promote it. Failover requires fencing, data-loss bounds, client cutover, recovery and failback ownership. PostgreSQL recovery routes to data-resilience. MySQL/MariaDB need an explicitly confirmed recovery runbook/owner; Galera and Group Replication membership surgery remain specialist work. No reset replica, skip transaction, reparent, writable replica or replication-log purge in diagnosis.

Sources: [PostgreSQL replication statistics](https://www.postgresql.org/docs/18/monitoring-stats.html), [MySQL status](https://dev.mysql.com/doc/refman/8.4/en/replication-administration-status.html), [MariaDB status](https://mariadb.com/docs/server/reference/sql-statements/administrative-sql-statements/show/show-replica-status).
