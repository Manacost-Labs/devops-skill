# Storage identity, capacity and recovery

Map application path -> container mount destination -> mount type -> exact volume name/driver/options or daemon-host bind path -> backing filesystem/device/provider. Record full container/volume identities and ownership before change. A bind source is on the daemon host, not necessarily the CLI machine. A new mount can hide image contents; a new/anonymous volume can silently look like an empty application.

| Symptom | Discriminate before repair |
|---|---|
| ENOSPC | Backing bytes, inodes, quota, writable-layer/log growth, deleted-open files and thin/provider capacity |
| EACCES/read-only | Numeric UID/GID, user namespace/rootless mapping, parent traversal, mount RW flag, ACL/SELinux and filesystem state |
| Data missing after recreation | Wrong project/volume/bind identity, changed destination, anonymous volume or masked image directory |
| I/O latency/errors | Same-window application/host/device events, fsync behavior, storage driver, provider limits and filesystem health |
| “Backup” archive exists | Application consistency, included volumes/streams/ACLs, keys, artifact integrity and isolated restore |

Read-only inventory does not require recursive content reads. Avoid calculating every container's writable-layer size on a degraded host as a first probe. File ownership repair can change unrelated objects and break mapped identities; do not use recursive chmod/chown or disable SELinux as a blanket fix.

Named volumes outlive ordinary container replacement, but they are not independent backups. tmpfs is volatile. A tar copy of a running database directory is not generally a consistent database backup; use its supported backup/restore method and owner. Volume plugins and remote backing services need their supported consistency/access/recovery procedure. Snapshots must be restored and checked, not merely listed.

Restore to a separate exact volume/path, keep original data and writer fencing, match application/version/UID expectations, then verify content and owner-defined invariants plus access. Only cut over with an explicit newest-write/loss decision. Never use `compose down -v`, prune, volume deletion or an empty replacement directory as diagnostic recovery.

Sources: [volumes](https://docs.docker.com/engine/storage/volumes/), [bind mounts](https://docs.docker.com/engine/storage/bind-mounts/), [tmpfs](https://docs.docker.com/engine/storage/tmpfs/), [down removal scope](https://docs.docker.com/reference/cli/docker/compose/down/).
