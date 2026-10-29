# Standard asynchronous recovery and cutover

This procedure supports planning/rehearsing a confirmed single-primary asynchronous topology. It is not a universal cluster repair or automatic failover. Galera, Group Replication/InnoDB Cluster, multi-source conflict resolution and cross-vendor migration require a topology specialist.

## Recover/reseed a replica

Confirm the intended source lineage, unique server identity, channel, exact base snapshot and matching coordinates/GTID state. Restore isolated with appliers stopped. Ensure the new replica cannot accept application writes or reconnect to the wrong source. Verify source history has all required transactions and no unexplained divergence before constructing vendor-specific replication configuration with credential references.

MySQL UUID/interval executed/purged sets differ from MariaDB domain/server/sequence state. For MariaDB, current_pos versus slave_pos changes which local transactions count; do not choose it to silence errors. Do not reset GTIDs, reuse server UUID/server_id, skip transactions or discard errant history without an explicitly reviewed data-reconciliation plan.

Start replication only after the exact source/channel, auth/TLS and initial point are approved. Verify receiver/applier errors, advancing positions, required transactions and lag under actual write activity; zero/NULL seconds lag alone is not catchup or consistency. Keep application consumers fenced until acceptance.

## Planned switch / failure recovery

1. Name failure hypothesis, accountable data/application owner, eligible target, current writer, replication mode and acceptable loss. Preserve the original writer and recovery artifacts.
2. Prove fencing independent of the suspected failure: old writer isolation plus exclusion of competing automation/other clients. A DNS change or read_only flag alone is not universal fencing; privileged sessions and old routes can still write.
3. For a planned switch, quiesce/drain writes and establish a final consistent source point, wait for required target transactions and verify no divergence. For unplanned failure, quantify the proven point and remaining uncertainty; obtain explicit loss acceptance.
4. Approve the exact promotion/cutover plan through core R4 gates, recovery, locks, actor and journal. Provider APIs, routing/pool clients and engine changes each retain their owner.
5. Promote once, change the bounded client path, and verify only one accepted writer, client convergence, error/latency and data invariants. Observe old endpoints as well as the new one.
6. Failback is a new data/topology change. Once new writes exist, a simple reverse route is not rollback. Reseed/reconcile the old source before reuse.

The CI recovery drills prove backup/import/replay boundaries on isolated single engines; they do not exercise live replica fencing, managed APIs or production failover. Rehearse those separately before claiming operational readiness.

Sources: [MySQL switching](https://dev.mysql.com/doc/refman/8.4/en/replication-solutions-switch.html), [MySQL GTIDs](https://dev.mysql.com/doc/refman/8.4/en/replication-gtids-concepts.html), [MariaDB GTIDs](https://mariadb.com/docs/server/ha-and-performance/standard-replication/gtid), [MariaDB replication](https://mariadb.com/docs/server/ha-and-performance/standard-replication/setting-up-replication).
