# Data operation gates

Use this checklist after the target and operation type are confirmed.

| Operation | Required proof before change | Stop conditions | Verification |
|---|---|---|---|
| Backup assessment | Artifact identity, age, location, encryption, retention, chain/catalog status | Missing owner, unreadable metadata, unknown retention | Inventory reconciles with policy; no claim of recoverability |
| Isolated restore | Quarantined target, least-privilege reference, egress controls, capacity, integrity queries | Production consumers reachable, literal credentials, insufficient capacity | Restore completes; integrity and application checks pass; measured RTO |
| PostgreSQL PITR | Valid base backup, continuous WAL range, target timestamp/LSN, timezone, recovery destination | WAL gap, ambiguous target time, overwrite without separate approval | Timeline/LSN and integrity verified; achieved RPO/RTO recorded |
| Redis recovery | Compatible RDB/AOF, persistence and cluster topology, replication offsets | Corrupt/truncated artifact, slot ambiguity, unsafe client reachability | Keyspace/application invariants, cluster state, persistence and latency verified |
| Migration | Reviewed immutable plan, compatibility and lock analysis, tested recovery/cutover, fresh backup | Changed digest, unbounded rewrite/lock, unproven rollback | Schema/data invariants, clients, replicas, latency/errors, drift observation |
| Failover | Failure hypothesis, fencing, promotion target, replication lag/data-loss bound, failback plan | Split-brain risk, unknown writer, unacceptable lag | Single writer, client convergence, integrity, lag and service health |
| Retention deletion | Owner, policy, legal-hold check, exact allowlist, preview/digest | Hold or scope ambiguity, mutable/unbounded selector | Exact artifacts removed, protected set retained, evidence recorded |
| Masked restore | Approved masking rules, re-identification analysis, egress/identity isolation | Reversible identifiers, production credential path, unmanaged extracts | Sampling and invariant checks prove utility and masking boundaries |

Record sources, timestamps, target, actor/tool identity, artifact and plan digests, redaction state, exact changed resources, rollback result, and evidence references. Store raw sensitive evidence only in the approved access-controlled system.
