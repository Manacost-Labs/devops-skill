# Disks, volumes and Storage Spaces

Map share/application path -> mount point/volume GUID -> filesystem -> partition -> disk UniqueId/serial/location -> virtual disk/pool/physical devices or provider backing disk. A drive letter, Disk Number or friendly name can change and is not immutable identity. Confirm boot/system/recovery, cluster/CSV and BitLocker roles before any write.

Use scoped Get-Disk/Get-Partition/Get-Volume and, when applicable, Get-StoragePool/Get-VirtualDisk/Get-PhysicalDisk/Get-StorageJob. Record health, operational state, size/free space, provisioned versus physical pool capacity and active repair/resync. Empty output from a missing role or restricted query is not healthy storage. Do not auto-import pools or online/clear disks to make discovery work.

## Diagnose by layer

| Symptom | Discriminate | Stop/owner |
|---|---|---|
| Volume full | Actual bytes, growth, quota, VSS, logs, dedup/temp/app ownership | No broad cleanup, shadow-copy deletion or database-file removal |
| Pool thin capacity exhausted | Virtual provisioned size versus physical pool/free/metadata and jobs | Storage/provider owner; do not repair by deleting an unknown virtual disk |
| Offline/read-only disk | Identity, SAN policy, cluster ownership, encryption and I/O events | Do not clear protection/force online without the owner |
| NTFS/ReFS errors | Filesystem/volume/device events and backing health | Preserve evidence, stop writes when indicated; no universal chkdsk recipe |
| Latency/timeouts | Same-window I/O, queues, storage/provider limits and workload | Do not infer media failure from one counter |
| Degraded pool | Member identity, redundancy, repair job and capacity | No retire/remove/reset/force-repair until recovery path verified |

## Grow, repair or restore

For growth confirm every layer's current/target size and supported limits. Provider/virtual disk expansion belongs to its owner; Windows partition/filesystem work belongs here. Query Get-PartitionSupportedSize for the exact confirmed partition and verify filesystem/adjacency constraints. Shrink/grow and rollback semantics differ; NTFS and ReFS are not interchangeable. Do not reduce the backing disk before a supported safe filesystem/partition reduction.

Storage repair/scans can consume I/O or require offline access. Distinguish Repair-Volume scan versus offline repair and chkdsk read-only versus write/dismount modes; verify exact filesystem support. ReFS recovery and clustered CSV/Storage Spaces Direct/Storage Replica need their specific owner/runbook. Do not format, initialize, clear, reset or recreate an unidentified volume as troubleshooting.

A change plan names immutable disk/volume/backing-file IDs, affected paths/data, allocation/capacity, downtime, active jobs, backup/restore proof and abort thresholds. Reconfirm identity immediately before each mutation; WhatIf cannot guarantee the later target. Verify mount persistence, filesystem health, BitLocker access by reference, data/ACL invariants and user path afterward.

Sources: [partition bounds](https://learn.microsoft.com/en-us/powershell/module/storage/get-partitionsupportedsize?view=windowsserver2025-ps), [storage jobs](https://learn.microsoft.com/en-us/powershell/module/storage/get-storagejob?view=windowsserver2025-ps), [volume repair](https://learn.microsoft.com/en-us/powershell/module/storage/repair-volume?view=windowsserver2025-ps), [chkdsk](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/chkdsk), [BitLocker protectors](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/manage-bde-protectors).
