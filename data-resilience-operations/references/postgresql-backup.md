# PostgreSQL capture and isolated restore

Baseline: PostgreSQL 18 full physical backup with the matching major-version tools, and version-reviewed logical export/import. Before work, inventory system identifier, database/role/tablespace scope, server/client/extension versions, collation environment, checksums, encryption/key references, topology and actual data directories. Physical recovery is same-major and compatible-platform work; a major upgrade needs a separate migration plan. Incremental/compressed backup products need their own compatible prepare/combine procedure.

## Select and capture

- Logical: `pg_dump` captures one database; record exclusions, large objects, extension dependencies, owners/ACLs and required global roles/tablespaces separately. A globals export can contain password hashes: restrict it and use reviewed secret-free role mappings for rehearsal. Record the snapshot and complete producer/compressor exit statuses. A partial export or one database is not an instance backup.
- Physical: choose an empty output, sufficient space/I/O and a scoped replication identity. A full `pg_basebackup` with streamed WAL needs replication connectivity and enough WAL senders. Preserve manifest, backup label, system ID, start/end LSN/timeline and all tablespaces with an explicit destination mapping. Do not use `-R` incidentally: it can preserve upstream connectivity/slot references.
- Finish publication durably before calling a capture available. Protect immutable artifact hashes, source/coordinate evidence and external configuration/key references separately. Backup capture load and slots/WAL retention can affect availability even without a restore.

## Rehearse

Use a new quarantined target with capacity and blocked production egress/clients. Review archive contents and SQL as executable untrusted input; confirm ownership, extensions and scheduler/subscription behavior before import/startup.

For logical restore, create the intended empty database from `template0`, pre-provision reviewed role/tablespace mappings, and use `pg_restore --exit-on-error` for archive formats or `psql -X --set=ON_ERROR_STOP=on` for plain SQL. Choose single-transaction versus parallel restoration deliberately. Record partial effects on any error; do not rerun into the dirty target or suppress errors. Compare objects, constraints, sequences, permissions and application invariants, then analyze as needed.

For a physical work copy, use matching `pg_verifybackup` including required WAL parsing before startup. It does not verify every later PITR segment, ignored recovery configuration, or application correctness. Override copied connection/archive settings through a separately reviewed configuration; map every tablespace to the isolated target. Start without production replication/consumers and validate databases, extensions, integrity and representative reads/writes. Preserve originals throughout.

Sources: [SQL dump](https://www.postgresql.org/docs/18/backup-dump.html), [pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html), [pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html), [pg_basebackup](https://www.postgresql.org/docs/18/app-pgbasebackup.html), [pg_verifybackup](https://www.postgresql.org/docs/18/app-pgverifybackup.html). Verified 2026-10-30; refresh exact versions before change.
