# Data resilience official sources

Last verified: 2026-08-17. Refresh the documentation matching the exact PostgreSQL or Redis version, topology, persistence mode and managed-service wrapper before a change.

- PostgreSQL [maintenance](https://www.postgresql.org/docs/current/maintenance.html), [SQL dump backup](https://www.postgresql.org/docs/current/backup-dump.html), [continuous archiving and PITR](https://www.postgresql.org/docs/current/continuous-archiving.html), [warm standby/failover](https://www.postgresql.org/docs/current/warm-standby.html), and [logical replication](https://www.postgresql.org/docs/current/logical-replication.html)
- Redis [persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/), [replication](https://redis.io/docs/latest/operate/oss_and_stack/management/replication/), and [cluster scaling](https://redis.io/docs/latest/operate/oss_and_stack/management/scaling/)
- NIST SP 800-188, [De-Identifying Government Datasets](https://csrc.nist.gov/pubs/sp/800/188/final), as a masking/de-identification reference—not a compliance determination

A product document or successful backup job is not restore proof. Record artifact identity, isolated restore evidence, integrity checks and measured RPO/RTO against the live topology.
