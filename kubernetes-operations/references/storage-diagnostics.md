# PVC, PV and backing storage diagnosis

Trace application path -> exact Pod UID/container/mount -> PVC namespace/name/UID -> bound PV UID/claimRef -> StorageClass/provisioner/CSI volume handle -> attachment/node/topology -> provider/backing disk. Record access and volume mode, reclaim policy, retention, encryption/key reference and application owner. A name or Bound condition alone does not prove the intended data is usable.

| Symptom | Discriminate |
|---|---|
| PVC Pending | UID-scoped events, StorageClass/defaults, capacity/access mode, quota, provisioner and topology |
| WaitForFirstConsumer | Scheduler placement and allowed topology; premature binding can defeat intended placement |
| FailedAttach/Multi-Attach | Old/new node attachment, actual old writer, access mode, fencing and driver health |
| FailedMount/EACCES | Secret/key reference availability, CSI/node plugin, filesystem/mount options, UID/GID/fsGroup and security policy |
| Full/read-only/I/O error | Backing bytes/inodes/quota/thin capacity, device/filesystem/CSI events and active resize/repair |
| Missing data after replacement | Different PVC/PV/claim UID, mount/subPath, restore source or application version |

ReadWriteOnce is a single-node access mode and can permit multiple Pods on that node; it is not a single-writer application lock. ReadWriteOncePod has version/CSI prerequisites. Raw block and filesystem volumes need different tooling. Do not remove protection/finalizers, delete/recreate claims, force-detach or mount a second writer before verified fencing.

For expansion confirm StorageClass/driver/filesystem support, exact claim/backing identity, quota/capacity, online/offline requirements and status conditions. Increasing requested capacity is not proof filesystem growth completed; shrinking or undoing backing expansion is not a generic rollback.

A VolumeSnapshot needs the appropriate API/controller/driver, readiness/content binding, deletion policy, key access and application consistency. Snapshot readiness alone proves neither data correctness nor isolated restore. Application/database quiescence and supported backup procedures remain necessary.

Restore into a separate approved claim/topology, prevent application hooks and production identity side effects, validate data/permissions/application invariants, then decide reconciliation/cutover with the data owner. PVC manifests do not include their bytes; workload backup does not recover etcd/control-plane identity. Complex clusters, distributed stores and unsupported engines require specialist recovery.

Sources: [PV lifecycle/modes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/), [StorageClass binding/expansion](https://kubernetes.io/docs/concepts/storage/storage-classes/), [VolumeSnapshots](https://kubernetes.io/docs/concepts/storage/volume-snapshots/).
