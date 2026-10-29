# MariaDB physical full and incremental recovery

Baseline: MariaDB 11.4 with matching mariadb-backup. Verify exact tool/server/storage-engine, page size, encryption/key-management plugin, compression and filesystem compatibility. This procedure does not apply to Oracle MySQL or a cross-version upgrade.

## Capture

Create a fresh restricted backup destination. mariadb-backup reads the local datadir even when connecting to a remote server for metadata: prove local storage and connected server identity match. Capture the full backup with approved profile, datadir and destination; review backup-stage lock privileges and workload impact. Preserve stdout/stderr privately, completion status, artifact inventory, tool version, checkpoint/LSN and binlog-coordinate metadata. Metadata filenames changed across versions (mariadb_backup_* versus older xtrabackup_*); discover actual output rather than guessing.

An incremental depends on its exact full/previous incremental. Record from_lsn/to_lsn, parent artifact and source identity. InnoDB deltas are not standalone backups; non-InnoDB coverage differs. Do not assume that a directory timestamp establishes order or that the newest incremental can be restored alone.

## Preparation

Preserve immutable originals and work on a checked copy. Decrypt/decompress through the matching documented tool before prepare, with key references and capacity accounting. Never overwrite the raw only copy.

1. Validate hashes, complete inventory, metadata and compatible binaries. Reject gaps, wrong parent/source, corruption, failed captures and unknown keys.
2. Prepare the full working copy with matching `mariadb-backup --prepare --target-dir=<working-full>`.
3. Apply each required incremental in LSN order with `--prepare --target-dir=<working-full> --incremental-dir=<incremental-copy>`, checking the expected preceding to_lsn equals the next from_lsn and recording the result after each step.
4. Follow the exact version's documented final prepare/consistency checks. Reject corrupted-page reports or incomplete preparation. Do not copy old XtraBackup `--apply-log-only` recipes into current MariaDB: option support/need differs.
5. Bind the resulting prepared artifact to its final checkpoint/binlog coordinate, not the original full's older point. Incremental preparation mutates the work copy and can consume the ability to recover an earlier point.

## Restore

Prove quarantine first. Stop and verify the destination MariaDB process is stopped; use a separately identified empty new datadir with sufficient capacity. Do not empty or force-overwrite an existing production datadir to satisfy the tool.

Use `--copy-back` with explicit source and destination under the approved plan; avoid move-back, which consumes the backup. Reconcile exact ownership/mode/SELinux labels with the host owner, validate vetted configuration/plugins, then start isolated with scheduler off, replication autostart disabled and no production consumers. Do not blindly restore plugin binaries, network listeners or replication credentials from the old host.

Verify all expected data/security objects, engine logs/checks and application invariants; then apply the reviewed binlog PITR range if required. Keep recovery point, data loss and full elapsed time in evidence. A successful prepare/start alone is insufficient.

Sources: [full restore](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/full-backup-and-restore-with-mariadb-backup), [incrementals](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/incremental-backup-and-restore-with-mariadb-backup), [backup files](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/files-created-by-mariadb-backup), [options](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/mariadb-backup-options).
