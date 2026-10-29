# Logical capture and isolated restore

Use the actual engine's tools. A dump is executable SQL and can contain client commands, privileged definers and sensitive rows. Verify provenance/hash and import only after quarantine and the approved exact plan. The commands below are parameter patterns, not approval or a universal script; choose exact dataset/paths and replace references locally.

## Capture differences

| Oracle MySQL 8.4 | MariaDB 11.4 |
|---|---|
| mysqldump; coordinate option `--source-data=2` | mariadb-dump; coordinate option `--master-data=2` |
| Review `--set-gtid-purged` against full/partial scope and restore topology | Review `--gtid` and vendor GTID state; no MySQL gtid_purged substitution |
| Restore with matching mysql client | Restore with matching mariadb client; newer dump sandbox directives can fail in old/MySQL clients |

For a confirmed InnoDB-only dataset with controlled DDL, `--single-transaction --quick` avoids per-table locking for row capture. Coordinate options can still require a brief global lock. Inventory nontransactional tables and coordinate DDL with the owner; transaction mode is not a consistency guarantee for everything.

Explicitly decide routines/events/triggers, binary-safe columns, tablespaces and account/config coverage. Grants/definers require a separately reviewed restoration plan. Do not dump/import all system tables as a cross-version shortcut.

Representative capture fragments (approved connection options omitted deliberately):
```text
mysqldump <approved-connection-options> --single-transaction --quick --source-data=2 --routines --events --triggers --hex-blob --databases <reviewed-databases>
mariadb-dump <approved-connection-options> --single-transaction --quick --master-data=2 --routines --events --triggers --hex-blob --databases <reviewed-databases>
```

For each tool verify exact available flags and privileges. Coordinate mode 2 comments the replication change instead of executing it at import; it does not remove locking/privilege requirements. A separately sampled server position after the dump is not its snapshot coordinate. Do not pick GTID OFF/AUTO blindly: partial dumps and GTID inclusion can change future replay/replication.

Write to a new restricted temporary artifact, capture producer/compressor/encryptor exit codes (pipefail alone does not validate data), verify byte count and decoding, then hash/catalog and publish atomically. Do not let redirection overwrite a known-good backup or accept a truncated dump because compression exited successfully. Store capture UTC interval, source identity, scope, exact tool/options by reference, consistency strategy and coordinates with the artifact.

## Restore

1. Follow restore-proof.md before connection. Confirm matching target version/config, required keys and sufficient disk/temp/undo space. Disable event scheduler and replication autostart and fence application consumers before import.
2. Restore on a clean destination scoped to the approved schemas. Review database creation/drop statements, DEFINER/security objects, client-side commands, plugins/UDFs and external-data engines. Client sandbox/binary modes reduce some client-command hazards but are not SQL isolation.
3. Import with an explicit target/profile and abort on any error. Never use force/skip-error flags. Do not log row data or whole SQL streams.
4. Verify tables, indexes, views, routines, triggers and disabled events against inventory; constraints, row/business invariants and representative queries must pass. Treat collation/charset/sql_mode warnings as compatibility findings.
5. Replay only the independently reviewed required binlog range, then recheck invariants and target point. Retain the original artifacts and failed target evidence; a retry starts from a known base rather than replaying into an ambiguous partial import.

Sources: [mysqldump](https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html), [mariadb-dump](https://mariadb.com/docs/server/clients-and-utilities/backup-restore-and-import-clients/mariadb-dump), [SQL import](https://dev.mysql.com/doc/refman/8.4/en/reloading-sql-format-dumps.html).
