# Redis topology, cutover and failback boundaries

Start with the authoritative topology: standalone, non-clustered replication/Sentinel, Redis Cluster or managed product. Inventory all writers, replica IDs/offsets, persistence and loss bounds, client discovery, credentials/TLS references, automation and control-plane owners. A node's healthy persistence files do not establish a complete distributed dataset.

## Standalone or standard replication

Quiesce/fence old writers and preserve final persistence/replication evidence before the approved switch. Asynchronous replication can lose acknowledged writes; `WAIT` or a replica offset alone is not a backup or universal failover guarantee. Confirm candidate lineage and required application state, independent fencing (including auto-restart/controllers), explicit loss acceptance where needed and client convergence. Verify one writable owner and durable new writes through the agreed observation window.

## Sentinel

Do not turn Sentinel failover into a manual standalone promotion. Confirm monitored master identity, Sentinel membership/configuration, quorum and majority reachability, candidate eligibility, persistence and client Sentinel support. A quorum check does not fence an isolated former master or prove zero data loss. Partitioned clients may still write to the old master; resolve that path and accepted loss with the owner before calling recovery complete. Rehearse the actual failover/controller topology separately; no Sentinel native-coverage claim is made by this package.

## Redis Cluster

Require a shard-wide plan: every master/shard, replica relationship, slot ownership, config epochs, migrating/importing slots, reachable cluster endpoints and cluster-aware client redirects. Independent per-node snapshots may represent different moments. Do not assemble a cluster by starting arbitrary RDBs with old node metadata, reset epochs, force slot ownership or flush slots as routine recovery. Missing shard coverage, ambiguous ownership or cross-shard application invariants requires a specialist reconstruction/reconciliation plan. Preserve node metadata separately and block production peer discovery during rehearsal.

## After new writes

Failback is a new gated operation. Keep former nodes fenced; determine authoritative history and reconcile writes, queues, stream consumers, locks/leases and external effects before rebuilding/rejoining. A replication reconfiguration can replace a dataset, and restoring older keys can recreate stale leases; require application-owner acceptance. Retain old independent artifacts until replacement recovery is proven. Provider-managed promotion/restore belongs to its provider executor, not a guessed Redis command.

Sources: [replication and write-loss boundaries](https://redis.io/docs/latest/operate/oss_and_stack/management/replication/), [Sentinel and quorum](https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/), [Cluster and slot behavior](https://redis.io/docs/latest/operate/oss_and_stack/management/scaling/). Verified 2026-10-30. Native CI covers standalone persistence recovery only.
