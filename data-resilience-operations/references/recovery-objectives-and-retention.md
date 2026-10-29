# Recovery objectives, retention and operational ownership

Define dataset scope, owner, desired loss/time bounds and disaster scenarios before selecting cadence or retention. Cover accidental logical damage, primary loss, zone/provider loss, stolen deletion credentials and key loss. Replication can rapidly propagate a bad transaction; it is not an independent historical backup.

## Design and monitoring

Measure full capture, archive lag, retrieval/decryption, prepare/import/replay and application acceptance on representative volume. Choose full/incremental/binlog cadence and archive durability from those measurements and growth. State measured versus projected recovery times. Backup completion age, log upload lag, key access test, last isolated drill, restore error and expiring retention each need an owner/action.

Keep a recoverable chain for every required point: full plus necessary incrementals and binlogs, exact source/epoch, compatible software/config and accessible keys. Check that a new successful full has completed durable publication and restore validation before retiring older independent recovery paths. A pending or corrupt replacement must not justify deletion.

Store restricted copies outside the source failure domain with owner-controlled immutability/offline protections as appropriate. Separate archive writers from deletion authority, and exercise disaster access without publishing secrets. Immutable retention must still respect data/legal ownership; do not claim one setting establishes ransomware immunity or compliance.

## Retention/deletion

Build a dependency graph before deletion: legal holds, earliest required recovery point, every retained full/incremental/log chain, replicas still needing source logs and key-retention dependencies. Preserve complete coverage at retention boundaries; a timestamp cutoff alone can strand a retained full.

Generate an exact immutable allowlist and protected set, estimate impact, validate policy/hold/replica evidence, then gate the deletion as R4 when irreversible. Provider object lifecycle and server PURGE BINARY LOGS are different operations and require their own identity/scope checks. Never use RESET history, broad filesystem deletion or a mutable wildcard to make space during diagnosis.

Verify exact deleted and preserved artifacts and record before/after evidence without data payloads. A backup/hash-check helper grants no deletion authority.

Sources: [MySQL purge](https://dev.mysql.com/doc/refman/8.4/en/purge-binary-logs.html), [MariaDB binary logs](https://mariadb.com/docs/server/server-management/server-monitoring-logs/binary-log), [MariaDB optimisation tradeoffs](https://mariadb.com/docs/server/server-usage/backup-and-restore/backup-optimization).
