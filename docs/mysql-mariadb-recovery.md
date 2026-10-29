# MySQL and MariaDB recovery in 0.6.0

Data resilience now owns the documented MySQL/MariaDB recovery methods; database operations retains daily engine diagnosis. Install profiles and the full runtime remain dependency-closed with 23 modules.

| Method | Scope | Verification |
|---|---|---|
| Oracle MySQL 8.4 logical backup/restore | Consistent reviewed InnoDB dataset, objects and snapshot coordinates | Import inventory/business checks on isolated target |
| MySQL file/position PITR | Complete ordered binlogs from the base to an exact transaction boundary | Two-file replay includes wanted work and excludes the unwanted transaction |
| MariaDB 11.4 logical/binlog recovery | Matching tools, consistency/GTID/client review | Separate real-engine dump/import/PITR drill |
| MariaDB physical full/incremental recovery | Compatible mariadb-backup, preserved originals, ordered LSN chain and prepared work copy | Empty stopped destination copy-back, isolated startup and data/object checks |
| Standard asynchronous cutover | Confirmed lineage, fencing, acceptable loss, client convergence and separate authorization | Topology-specific rehearsal; not established by single-engine CI |

MySQL physical products require a selected compatible product/runbook. Cross-vendor migration, Galera/Group Replication/InnoDB Cluster recovery and automatic failover are specialist work. This package does not make those procedures generic or claim production certification.

## Start from the intended recovery point

Confirm source/target identity, engine/tool versions, storage engines, schema/security object inventory, exact consistent base, log history, keys, owner and acceptance. Read the data-resilience procedure for the selected method. Core coordinates approvals, locks, journal, provider/runtime boundaries and the final change.

Use the `data-safe`, `all` or relevant named-provider install profile. Preview first using the main README. Updating a skill or installing the checker does not configure a backup service or grant production restore authority.

The offline `verify-binlog-chain.py` helper verifies a strict receipt against actual artifact bytes under an approved directory. It rejects missing/reordered files, changed bytes, unsafe paths and excessive I/O. A valid result explicitly leaves replay unproven: native event/transaction checks, quarantine and a real restore are mandatory. Hashes cannot establish truthful provenance or application correctness.

## Recovery evidence

Measure retrieval/decryption, prepare/import/replay, integrity/application checks, client cutover and observation. State the achieved consistent point, accepted loss and uncertainty. Backup age, a successful compression job, replica lag and command duration alone cannot establish RPO/RTO.

Keep recovered schedulers/appliers/consumers disabled, block production egress and preserve immutable originals. Restored SQL/config can contain secrets or external effects; client sandbox options do not replace isolation. Retention plans preserve every dependency needed for retained recovery points and require separate exact deletion approval.

## Tests and limits

Hosted CI uses the already pinned MySQL 8.4/MariaDB 11.4 images in containers without network access or published ports. Synthetic fixtures exercise tables, a view/procedure/trigger/event, a logical restore, rotation across two binary logs and exclusion of a bad transaction. MariaDB also exercises full+incremental capture, preparation on a work copy, copy-back and isolated startup. Artifact tests reject corruption and chain gaps.

These drills use small synthetic InnoDB datasets and local fixture access. They do not establish production throughput, key-manager disaster availability, all privilege matrices, nontransactional consistency, GTID topology coverage, provider recovery or live failover. Verify the chosen release/tool and rehearse the actual topology before making those claims.
