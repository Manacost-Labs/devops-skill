# Binary-log archive and point-in-time recovery

Start with a proven consistent base before the desired recovery point and its matching log coordinate. Confirm the exact server history/epoch, vendor, binlog format/encryption/checksum, clock/time zone, GTID mode and dataset scope. A replica's local binlog or a reused filename after reset is not automatically the primary's history.

## Archive coverage

Capture logs durably before source expiration; distinguish a closed immutable file from a currently growing log. Record source/epoch, ordered filenames, exact sizes/hashes, timestamp bounds and trusted inventory/provenance. A checksum proves bytes match a receipt, not that the receipt is truthful or the SQL safe. For encrypted source binlogs use the exact supported authorized export/decryption path; do not treat ciphertext as replayable plain logs. Protect data and keys separately.

Check every log from snapshot coordinate to target boundary; reject missing/reordered/duplicated files, wrong source/prefix/epoch and truncation. The optional verify-binlog-chain.py checks only the declared file/position receipt and artifact integrity; native decoder verification and a restore drill are separate.

## Resolve the endpoint

A human time is a search hint: establish UTC/local time zone, clock accuracy and incident evidence, then map to an exact reviewed transaction boundary. A stop position excludes the event beginning there; stopping inside a transaction can leave a different outcome than intended. Include complete commits and stop before the first unwanted transaction, including its GTID/event preamble. Document inclusive/exclusive semantics and prove them in rehearsal. Ambiguous boundary means blocked, not a guessed timestamp.

Use matching mysqlbinlog for Oracle MySQL or mariadb-binlog for MariaDB. Validate event/checksum decoding with the installed version without error suppression. Row-event decode output is for inspection, not necessarily executable replay; do not replay a human-readable decode-rows listing.

Supply the exact ordered explicit file list. On the documented MySQL CLI, start-position applies to the first named file and stop-position to the last; verify matching MariaDB behavior before command construction. Replay the approved sequence through one target client session to retain session/temporary-table context. Check decoder and client results separately; never accept a successful final pipe stage after an earlier failure. Generate a restricted reviewed replay artifact when that makes failure/retry handling clearer.

Do not use database/server-ID filters, skip-error, force-read, arbitrary text edits or GTID exclusion to bypass gaps. Cross-database transactions and statement/row formats make casual filtering unsafe. A failed replay leaves partial state: preserve it and restart from a verified base or an explicitly proven checkpoint, not by rerunning the whole stream.

## GTIDs and topology

MySQL UUID/interval GTID sets and MariaDB domain/server/sequence GTIDs are different. Preserve snapshot executed/purged state and exact source history. A logical dump's GTID directives can mark transactions outside a partial dataset; copying them blindly can skip needed work. Do not reset GTIDs or reuse source identity to silence duplicate errors. Our helper intentionally does not prove GTID-set coverage or emit replay commands.

After replay verify target coordinates/history and application invariants, including expected inclusion and exclusion around the incident. Recovery to an earlier time intentionally omits later legitimate work: quantify and obtain the owner's data-loss decision before cutover.

Sources: [MySQL binary-log PITR](https://dev.mysql.com/doc/refman/8.4/en/point-in-time-recovery-binlog.html), [event boundaries](https://dev.mysql.com/doc/refman/8.4/en/point-in-time-recovery-positions.html), [mysqlbinlog](https://dev.mysql.com/doc/refman/8.4/en/mysqlbinlog.html), [MariaDB PITR](https://mariadb.com/docs/server/server-usage/backup-and-restore/mariadb-backup/point-in-time-recovery-pitr-mariadb-backup), [MariaDB binlog options](https://mariadb.com/docs/server/clients-and-utilities/logging-tools/mariadb-binlog/mariadb-binlog-options), [MySQL GTIDs](https://dev.mysql.com/doc/refman/8.4/en/replication-gtids-concepts.html), [MariaDB GTIDs](https://mariadb.com/docs/server/ha-and-performance/standard-replication/gtid).
