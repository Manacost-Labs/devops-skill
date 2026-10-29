# Quarantine and restore proof

Before any SQL import, physical startup or replay, establish an independently identified destination with no path to production consumers. A new database name on a production server is not quarantine.

## Effective isolation

Verify network/egress, routing, listeners, DNS/service discovery, credential scope and application endpoints. Disable event scheduler, replication auto-start, application workers/outbox consumers, cron/hooks and automatic registration. Use vetted configuration and binaries; do not boot a recovered image with inherited cloud identity or production secret access. Restored routines/UDFs/plugins/federated engines can have external effects; review before activation. A client sandbox or read-only flag cannot replace network and privilege isolation.

Use separate identities for capture, archive write, archive deletion and recovery. Keep encryption keys reachable through authorized disaster access, not embedded in the backup receipt. Restore access must not imply permission to delete original copies.

For logical import inspect trusted provenance, scope, creation/drop statements, client commands, definers/security objects and engine plugins. For physical restore inspect the restored configuration and replication identity separately from data. Preserve original evidence and prepare only copies.

## Acceptance matrix

| Layer | Required evidence |
|---|---|
| Artifacts | Source/epoch, exact scope, hashes, keys available, full/log or incremental chain accounted for |
| Restore process | Compatible tools, all stage results, no skipped errors/corruption, elapsed stage timings |
| Engine | Expected schemas/tables/indexes/objects and version/config compatibility; required constraints and engine checks |
| Data | Owner-defined invariants, representative row/aggregate checks, expected transaction included and unwanted transaction excluded |
| External effects | Scheduler/replication/egress/production consumers remain disabled; no unauthorized delivery or mutation |
| Recovery objectives | Achieved consistent point and uncertainty, accepted lost work, measured total recovery time |
| Cutover | Separate approval/fencing, single writer, client convergence and service observation |

Row counts and checksums alone do not prove business correctness; two identically broken copies can match. A native CHECK TABLE result also cannot prove cross-table/application invariants. Sample queries must be bounded, reviewed and avoid exposing customer rows in evidence. Masking must be validated before broader non-production use.

Record timestamps for incident declaration, retrieval, decryption, prepare/import/replay, checks, cutover and acceptance. The restore command duration is only one part of RTO. For RPO identify the last proven consistent committed point relative to the failure; backup age or replica time-lag is not enough. If source loss prevents a precise bound, record uncertainty rather than a fake zero-loss claim.

After a failed stage, preserve restricted logs and the failed target, revoke temporary access as planned and identify a clean retry point. Do not repair by force-importing remaining SQL or replaying everything again. Quarantine cleanup/retention is a separate allowlisted operation with ownership/legal-hold checks.
