# Connection capacity

Build the worst credible simultaneous backend demand for each engine target, including autoscale maximum, rollout surge, workers, jobs, migrations, monitoring and failover consolidation. Compare against the actual target's usable slots and resource capacity. Current usage alone cannot size the system.

For direct pools: backend peak = sum(max simultaneous instances * maximum backend connections per instance). For PgBouncer or another proxy, frontend client limits differ from backend server pools; account for user/database pool combinations, reserve pools and proxy replicas. Transaction pooling can change session state, temporary tables and prepared-statement behavior depending on version/config. Verify actual compatibility; do not prescribe a universal mode or cores-based pool size.

Reserve operator/system/provider capacity without counting it twice. PostgreSQL superuser_reserved_connections/reserved_connections and managed-provider limits are version/role specific. MySQL administrative connection behavior differs. Fit within connection slots is only a necessary bound: CPU, memory, transaction contention, query latency and failover target may demand smaller pools.

## Offline budget helper

`python database-operations/scripts/connection-budget.py <input.json>` accepts exact fields:

```json
{
  "engine_max": 200,
  "reserved": 15,
  "other_peak": 10,
  "pools": [
    {"name": "api", "instances": 6, "per_instance": 20},
    {"name": "jobs", "instances": 2, "per_instance": 10}
  ]
}
```

All counts are explicit nonnegative integers, with positive engine_max/instances/per_instance and reserved < engine_max. Pool names are unique bounded identifiers. Other_peak excludes named pools and reserved capacity. Missing/unknown fields and duplicate JSON keys are rejected, not silently defaulted.

Output includes application/backend peak, usable slots, total committed slots and signed headroom with fits/at_limit/exceeds status. No secret, target or live query is needed. Exit 0 means valid arithmetic even when capacity is exceeded; invalid input exits 2. It does not discover demand, estimate RAM, set limits or prove performance. At_limit provides no spare unreserved capacity; choose headroom from measured burst/failure needs.

Mitigate connection storms through application retry/backoff, pool timeout/queue and bounded concurrency with the application owner; verify under realistic traffic before any server-limit increase.

Sources: [PostgreSQL slots](https://www.postgresql.org/docs/18/runtime-config-connection.html), [PgBouncer pools](https://www.pgbouncer.org/config.html), [MySQL status](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html).
