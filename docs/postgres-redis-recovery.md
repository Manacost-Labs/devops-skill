# PostgreSQL and Redis recovery scope

`data-resilience-operations` 0.5.0 adds detailed PostgreSQL 18 full physical/logical recovery and Redis Open Source 7.4 standalone persistence recovery guidance. The skill routes to method-specific references; the shared contract, exact operation gate, secret references, independent restore isolation and production approval requirements remain in force. Existing MySQL/MariaDB methods remain supported.

| Area | Operational guidance | Native fixture evidence |
|---|---|---|
| PostgreSQL capture/restore | Full base backup, streamed backup WAL, native manifest checks, logical method/role/tablespace boundaries | Actual `pg_basebackup`, `pg_verifybackup`, empty-target physical restore and application invariants |
| PostgreSQL PITR | Source system/timeline identity, complete archive, exact point and pause/acceptance | Multi-segment archive replay includes two wanted transactions and excludes a later unwanted transaction; named point pauses read-only |
| PostgreSQL transition | Independent fencing, recovery completion, new timeline, reconciliation after new writes | Synthetic source process stopped before restored copy becomes writable; resulting timeline 2 checked |
| PostgreSQL failures | Preserve originals, refuse incomplete or unreachable recovery | Native startup refuses missing/corrupt required WAL and nonexistent target; native verifier rejects changed base bytes |
| Redis RDB | Snapshot selection, validation, loading mode, types/expiry and desired point | Actual RDB validation/startup returns the earlier dataset and preserved absolute expiry |
| Redis multipart AOF | Coherent manifest/base/incremental set, fsync and rewrite boundaries, explicit loading mode | Actual rewrite/capture/native check/startup returns wanted later writes, excludes subsequent unwanted writes and chooses AOF over the older RDB |
| Redis failures | No implicit repair, discarded-history acceptance or partial loading | Native tools and startup reject corrupt RDB checksum, a missing manifest member and truncated AOF with truncation disabled |

The source-only fixtures run in separate disposable GitHub-hosted Linux CI jobs. `tests/recovery_fixture.py` inherits existing local-daemon identity, runner guard and labelled-resource ownership checks. Engine containers use digest-pinned official images, unprivileged engine users, a read-only root filesystem, bounded tmpfs/memory/CPU/PIDs, no capabilities, no published ports and no network. Image-declared volumes are overridden with tmpfs to avoid anonymous leftovers. Synthetic artifacts remain in the owned runner temporary directory and are removed with the fixture. Engine/native utility versions and assertion outcomes are recorded by the job.

Run only on the supported disposable runner:

```text
python tests/smoke_postgres_recovery.py
python tests/smoke_redis_recovery.py
```

Unsupported/local environments fail explicitly; do not spoof runner variables to use the fixture against another daemon. The workflow runs both native jobs on each PR/main push without an optional skip path; successful native results are part of this change's merge criteria, independent of which check names branch protection requires. Ordinary unit/package checks still run on both Linux and Windows.

## Practical limits

PostgreSQL physical recovery is tested only on the pinned PostgreSQL 18 image with default synthetic objects, no external tablespaces or extensions and a small explicit WAL segment size. Logical restore guidance is not a native logical-migration test. Checksums and base verification do not validate arbitrary future WAL, copied recovery configuration or production application invariants.

Redis testing covers the pinned Redis 7.4 standalone image and built-in string/hash/list/expiry behavior. It does not certify Redis 8, modules, every data type, provider persistence, Sentinel failover, Cluster resharding/reconstruction or distributed consistency. RDB/AOF restore is recovery to the captured persistence state, not arbitrary timestamp PITR.

Neither fixture proves disaster artifact availability, IAM/KMS/decryption, real storage durability, production fencing/orchestrator quorum, client cutover, failback, physical-platform compatibility, full-volume RPO/RTO or recovery under load. Rehearse the actual engine/version/topology, data handling, orchestration and application acceptance with their owners. Native source-process stopping demonstrates fixture ordering, not enterprise fencing.
