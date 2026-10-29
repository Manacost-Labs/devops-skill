# Operations expansion in 0.5.0

The platform now has 23 modules. This package deepens three connected layers without changing contract v2 or the execution gate.

| Layer | Added operational depth | Boundary |
|---|---|---|
| Linux | Debian/Ubuntu and confirmed RHEL/Rocky/Alma procedures; package transactions, cgroup/CPU/memory/OOM/I/O diagnosis, storage/LVM/filesystems, boot/reboot, resolver/routing/firewalls, SSH/sudo and SELinux/AppArmor | Host changes remain release-specific and require access/recovery evidence; containers and managed APIs keep their owners |
| Reliability | Prometheus queries/rules, Alertmanager routes, Grafana semantics/access, Loki labels, OTel pipelines/privacy, SLO burn windows, missing data, capacity and release/incident acceptance | Telemetry does not authorize repairs or notifications; actual component tooling and end-to-end evidence remain required |
| Database operations | Separate PostgreSQL/MySQL/MariaDB diagnostic SQL, waits/connections/capacity, replica consistency, maintenance/configuration planning | Application/schema changes need their owner; PostgreSQL/Redis recovery stays in data resilience; MySQL/MariaDB recovery is covered by data-resilience 0.4.0+ for documented methods; unsupported physical products/cluster topologies require specialists |

## Use and installation

Use `linux-operations` for a host symptom, `reliability-operations` for a signal/delivery or acceptance problem, and `database-operations` for engine waits/connections/performance. Core routes cross-layer work by affected state. Detailed procedures load only when the task needs them.

The `all`, `data-safe` and named provider profiles include database operations. Other focused profiles retain their existing scope; if the needed module is absent, stop at safe discovery and install an appropriate profile before claiming its capability. Managed databases do not require a Linux-host module solely for diagnosis.

```powershell
python tools/install.py --profile data-safe --destination <skills-folder>
```

This previews skill installation; follow the main README for applying it or installing a complete execution runtime. Upgrading instructions does not configure a live host, monitoring stack or database.

## Typical decisions

- A slow service with idle host CPU: compare workload cgroup throttling, I/O/waits and same-window user impact before resizing.
- A green panel with missing samples: investigate telemetry freshness and the independent user path before reporting health.
- A connection storm: sum backend pools across maximum simultaneous instances, rollout surge and failover targets before changing server limits.
- A replica with NULL/zero time lag: verify role, advancing positions, transport/apply and consistency before any recovery decision.

The offline connection and SLO helpers consume explicit secret-free JSON counts. Their exit code reports input/calculation validity; inspect the output status. They never connect to a target, change configuration or notify anyone. Their input schemas and limitations are in each module's references.

## Validation and limits

Unit tests cover arithmetic boundaries, ambiguous/malformed inputs and Linux discovery behavior. CI additionally executes the SQL templates on isolated pinned PostgreSQL 18, MySQL 8.4 and MariaDB 11.4 containers and runs real Prometheus 3.5.0 promtool tests. Containers use synthetic local access, no external network and no published ports. Cross-vendor SQL is checked for rejection.

These are syntax and bounded behavior checks, not production load, replication, recovery, privilege-matrix or full Linux distribution certification. No real paging receiver or production database is contacted. Run release/version-specific preflight and acceptance against an authorized target before any operational change.

Official-source mappings are checked for all three modules. Documentation freshness and a passing validator establish provenance and structure; independent review and target evidence are still needed for correctness.
