# Host audit signals

Interpret signals in context; one transient sample is not an incident.

| Signal | Investigate when | First safe action | Handoff |
|---|---|---|---|
| Disk capacity | Any critical filesystem above agreed threshold; default warning 80%, critical 90% | Identify top directories/files and ownership; do not delete | Docker for container data; data-resilience for DB data |
| Inodes | Above 80%, critical 90% | Find small-file producer and retention policy | Reliability for alert design |
| Memory/swap | OOM events, sustained swap, service eviction | Inspect cgroup/service limits and recent journal | Docker or application owner as applicable |
| Load/CPU | Sustained saturation with latency or queue symptoms | Identify processes and correlate with service logs | Reliability for correlation/SLO impact |
| Failed units | Any expected service failed or restart loop | Capture `systemctl status` and recent `journalctl` | Owning module/service team |
| Ports/firewall | Unexpected public listener or blocked expected port | Confirm service owner and desired exposure | network-edge/cloud module |
| SSH/auth | Password auth/root login enabled, repeated failures, unknown sudo | Confirm break-glass and access owner before change | devops-core for R3 change control |
| Time | NTP unsynced or material clock drift | Inspect time service and sources | reliability if it affects telemetry |

`host-audit` signals are observations, not proof that a change is safe.