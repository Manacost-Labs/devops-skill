# MySQL/MariaDB recovery intake

Confirm server vendor/version, backup/client tool version, managed/self-hosted owner, source fingerprint, writer/replica/proxy role, database scope, storage engines, table sizes, transaction rate, DDL activity, encryption, replication/GTID mode and application invariants. Protocol compatibility is not backup compatibility.

Check backup, decoder and restore-client availability before the window. Minimal runtime images can omit mysqlbinlog; use a vetted compatible tool environment rather than installing packages or substituting a different vendor's decoder during recovery. Our CI stages a matching version/hash-pinned Oracle binary bundle; that is test provisioning, not a production installation recipe.

| Method | Appropriate when | Required evidence / limits |
|---|---|---|
| MySQL logical dump | Reviewed schema/data scope and acceptable import time | InnoDB snapshot plus matching log coordinates; separate accounts/config/keys and object inventory |
| MariaDB logical dump | Matching MariaDB client/server and acceptable import time | Same consistency review; sandbox command/client compatibility; separate security/config inventory |
| MariaDB physical full/incremental | Exact compatible mariadb-backup/server/storage layout | Complete prepared chain, LSN continuity, tool logs, keys/plugins and stopped empty isolated destination |
| MySQL physical product | A supported selected product and release-specific runbook exist | Product/licence/version/feature compatibility and rehearsal; do not use mariadb-backup |
| Managed snapshots/PITR | Provider supplies the feature | Provider owns API/identity, this module owns consistent target/point and application proof; IAM success is insufficient |

Nontransactional MyISAM/Aria/MEMORY tables, concurrent DDL and cross-database workflows need a lock/quiescence strategy or a different method. A single-transaction InnoDB dump does not make all engines consistent. Inventory routines, triggers, events, definers, grants, plugins/UDFs, time zones, charset/collation, sql_mode, case sensitivity and application version. Restore tested app schemas; do not blindly transplant the mysql system schema across versions.

Use scoped credential/secret profiles and TLS verification. Review exact dump/backup privileges: collecting consistent coordinates and taking backup-stage locks can need privileges beyond SELECT. Avoid granting blanket admin just to make a tool pass. Capturing from a replica can pause/change appliers and its own binlog may not equal the original primary's history; prove the snapshot/log mapping before reuse.

Define capture impact limits: maximum lock wait/time, allowed I/O/CPU, temporary disk, primary/replica delay and abort owner. A slow backup can hold a snapshot and retain undo/log space. Do not change purge/retention or enable binary logging during an incident without a separate change.

Before restore, name artifact provenance and expected full coverage, restore software/image, quarantine controls, external dependencies and acceptance. Confirm keys remain available after credential revocation/disaster. Do not paste keys or credentials into commands, chat, receipts or Git.

Sources: [MySQL methods](https://dev.mysql.com/doc/refman/8.4/en/backup-methods.html), [MariaDB overview](https://mariadb.com/docs/server/server-usage/backup-and-restore/backup-and-restore-overview), [MariaDB backup overview](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/mariadb-backup-overview).
