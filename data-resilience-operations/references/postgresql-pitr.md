# PostgreSQL WAL and exact recovery boundaries

Use a proven physical base backup plus an uninterrupted archive from its required start through the intended transaction boundary. A logical dump is not a base for WAL replay. Bind system identifier, source epoch, major version, WAL segment size, base start/end LSN, selected timeline and required history files; names or sequence numbers alone cannot establish lineage. Preserve archive and backup originals on controlled storage.

## Establish the point

Name the desired application state: commits included, harmful commit excluded and any external effects requiring reconciliation. Select exactly one supported target (named restore point, transaction, LSN or time). For time, record explicit timezone and inclusivity and correlate with commit evidence; wall-clock proximity is not a transaction boundary. A restore point must exist after the base backup can become consistent. An absent target or WAL gap blocks acceptance; never remove the target setting to make startup succeed.

## Restore the work copy

1. Verify the base with native tooling, retrieve every required archive object and history file, and preserve separately protected hashes/metadata. `pg_verifybackup` covers backup-required WAL, not the entire future PITR interval; replay is still essential.
2. Prove target/egress isolation and explicit data/tablespace mapping. Review copied recovery, archive, preload, connection and service configuration before startup. Stop conflicting auto-failover/reconciliation through its owner.
3. On PostgreSQL 18, use `recovery.signal`, an exact archive `restore_command`, the selected target/timeline and an explicit target action. The command must report a missing archive object truthfully and must not overwrite an existing unrelated file. Do not set up `standby.signal`/streaming as an accidental fallback.
4. Prefer pausing at the target for quarantined read-only checks, explicitly with `hot_standby=on`; without hot standby, a pause target action behaves as shutdown. Observe replay state and actual restored application markers; a listening socket or exit code alone does not prove the target was reached. A paused target remains in recovery. Preserve logs without dataset payloads.
5. Before making it writable, apply [cutover and fencing](postgresql-cutover.md), then prove recovery ended, the resulting timeline/history, writable role and client convergence. Promotion starts a new history; do not reattach the former writer automatically.

If archive retrieval fails, target is unreachable, state is inconsistent or recovery stops early, keep clients fenced, preserve the failed copy/evidence and prepare a fresh corrected rehearsal. Do not use WAL deletion, guessed history, `pg_resetwal`, skipped checksums or replay-target removal as routine repair. Report the achieved point and loss bound, including uncertain commits, separately from requested RPO/RTO.

Sources: [archive recovery and timelines](https://www.postgresql.org/docs/18/continuous-archiving.html), [recovery settings and target semantics](https://www.postgresql.org/docs/18/runtime-config-wal.html), [native verification limits](https://www.postgresql.org/docs/18/app-pgverifybackup.html). Verified 2026-10-30.
