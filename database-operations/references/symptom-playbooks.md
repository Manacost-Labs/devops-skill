# Symptom playbooks

| Symptom | Discriminate | Unsafe inference/action |
|---|---|---|
| Too many connections | Pool active/idle/waiting, rollout/autoscale peak, slot reservations, retries | Raise max_connections or kill every idle session |
| Slow with low host CPU | Lock/transaction age, pool queue, I/O, replica path | Assume missing index |
| High CPU | Workload/plan change, concurrency, same-window rates, host limits | Execute arbitrary EXPLAIN ANALYZE in production |
| Disk growth | Data versus WAL/binlog/temp, retention/slots/archiver and mount | Delete engine files or drop slots |
| Replica lag | Correct channel/role, advancing positions, receiver/apply/errors | Treat NULL/zero time lag as consistency or promote |
| Deadlocks | Time/counter delta, application transaction order and retry behavior | Kill root blocker without workload/recovery decision |
| PostgreSQL cleanup stalls | Snapshot/transaction age, slots, vacuum activity and wraparound evidence | VACUUM FULL or disable autovacuum |
| MySQL/MariaDB lock wait empty | Metadata locks/instrumentation/privilege visibility | Conclude no lock contention |

Return observed impact, confirmed evidence, contradictions, remaining unknowns and next bounded probe. Performance change needs comparable workload before/after; a successful maintenance command alone is not success. Compose host, application, provider, reliability and recovery owners only at their affected boundaries.
