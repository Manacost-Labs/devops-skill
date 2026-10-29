# Symptom-driven investigation

These sequences discriminate causes; they are not automatic repair scripts.

| Symptom | First evidence | Competing cause / next probe | Boundary |
|---|---|---|---|
| Latency, CPU idle | Same-window load, PSI, cgroup throttling, device latency | Quota versus I/O/dependency queue; compare service and host | Container limits to workload owner; engine waits to database |
| Process killed | Unit result plus timestamped kernel/oomd/cgroup events | Global/memcg OOM, watchdog, explicit signal; 137 alone proves none | Preserve crash evidence before restart |
| Space stays full after deletion | Correct mount, bytes/inodes, scoped open-deleted descriptors | Thin pools, snapshots, hidden mounts | Never delete WAL/binlog |
| Service restarts | Original exit, bounded journal, dependencies | User/path/denial, port, timeout or limit | No reset-failed/restart loop |
| SSH fails | Console, listener, route/family and auth evidence | Network versus Match/PAM/key/account | Stop access edits without recovery |
| DNS works, connect fails | Family, chosen source/route, listener/return path | Split DNS, IPv6, MTU or cloud ACL | Route evidenced failed hop |
| Time jumps | Sync state/offset, VM clock and timeline | Clock issue versus actual certificate failure | No blind clock step or TLS bypass |
| Read-only filesystem | Kernel/device/array event and mount identity | Media/provider versus filesystem | No force remount; storage recovery |

Return confirmed facts, ruled-out causes, unknowns, next bounded probe and observation that would justify a change. Retain conflicting evidence and investigate time/scope differences. Repeat the same measurements and user path after intervention.
