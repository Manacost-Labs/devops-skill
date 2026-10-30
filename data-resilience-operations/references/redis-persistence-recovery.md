# Redis persistence-point recovery

Baseline: Redis Open Source 7.4 standalone RDB and multipart AOF, with matching native tools. Discover exact version, modules/data types, role, databases, `dir`/filenames, append directory, fsync/rewrite settings, disk/memory headroom, expiry/clock behavior and topology first. Redis 8, managed products and cross-version/module moves require their own compatibility review. Replication is not independent historical backup. Redis RDB/AOF recovery does not provide arbitrary timestamp PITR.

## Capture a coherent artifact

- RDB: choose an approved snapshot operation, account for fork/copy-on-write and I/O impact, and verify completion/status and publication of the intended snapshot rather than assuming an accepted `BGSAVE` request completed. Preserve capture time, source identity and restrictions; its point predates later writes.
- AOF: inventory the manifest and every referenced base/incremental member, exact order and hashes. Coordinate a consistent capture with rewrite/append activity; copying a live directory file by file is not a coherent backup. Prefer an approved stopped capture or documented consistent storage/backup mechanism. Disable/restrict rewrite only through a reviewed reversible plan, not incidentally.
- Record the selected persistence point and uncertainty separately from client acknowledgement time. An fsync policy or `WAIT` acknowledgement is not a zero-loss guarantee; `WAITAOF` applies to preceding writes on that connection and its result/timeout must be inspected.

## Restore and prove

1. Preserve originals; stage a complete work copy in a fresh quarantined target. Prove production clients/egress and replication start are blocked; load only reviewed configuration, modules and opaque credential references.
2. Run compatible `redis-check-rdb` and/or `redis-check-aof` against the selected artifact/manifest without repair options. Set and verify effective `aof-load-truncated no` for normal rehearsal: a default that discards an incomplete tail is not strict recovery. Hash or format success cannot prove the desired dataset point. Missing members, corruption and truncation block normal recovery.
3. Set the intended loading mode explicitly. With both persistence modes enabled, Redis uses AOF at startup; dropping an old/new RDB beside an unrelated AOF does not select the RDB. For an RDB rehearsal, use an empty destination and deliberate AOF handling. For AOF, keep the complete selected manifest set; do not choose the newest filename by guesswork.
4. Require completed loading, expected role/topology, persistence health and application checks: key values/types, counts or bounded samples, streams/groups where used, absolute expiry semantics, newest required writes and excluded harmful writes. `PING` alone is insufficient. Assess expired keys against recovery wall clock rather than resetting TTLs accidentally.
5. Make production cutover only through [topology and fencing checks](redis-topology-cutover.md). Verify clients, persistence after new writes/restart, resource use and observation-window latency/errors.

If salvage is explicitly approved after an independent copy, run repair only on that copy and quantify discarded commands/transactions and application impact. Never enable truncation, `--fix`, disable checksums or accept partial loading merely to get a green startup. AOF rewrite may remove old command history; do not promise recovery of an earlier timestamp from the current AOF.

Sources: [persistence and multipart AOF](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/), [BGSAVE](https://redis.io/docs/latest/commands/bgsave/), [BGREWRITEAOF](https://redis.io/docs/latest/commands/bgrewriteaof/), [WAITAOF](https://redis.io/docs/latest/commands/waitaof/), [per-key restore/expiry](https://redis.io/docs/latest/commands/restore/). Verified 2026-10-30.
