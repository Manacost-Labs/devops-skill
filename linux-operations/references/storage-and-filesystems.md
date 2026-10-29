# Storage and filesystems

Map mountpoint/UUID -> filesystem -> LV/VG/PV -> partition -> device -> provider disk. Use targeted findmnt, lsblk, df bytes/inodes and permitted LVM/RAID status. Device names can change; encryption, thin pools and bind mounts complicate ownership. A path name never proves a disposable volume.

| Evidence | Discriminating check | Unsafe shortcut |
|---|---|---|
| Bytes full, inodes available | Owner-scoped growth, retention, open deleted files | Delete the largest file |
| Inodes full | Bounded directory/file-count investigation on correct mount | Broad recursive deletion |
| df exceeds visible usage | Open deleted files, reserved space, snapshots, hidden mount contents | Assume corruption/truncate descriptors |
| Read-only remount or I/O errors | Kernel/device/array/provider health window | Force read-write or mounted repair |
| Thin pool or RAID degraded | Data/metadata usage, members, redundancy/rebuild | Force assembly/remove PV/extend wrong LV |

Du can be expensive and cross mounts: agree scope and budget. Scoped lsof can reveal paths/processes; redact. Coordinate supported log reopen with its service owner. Database data/WAL/binlogs are never host cleanup.

## Capacity change

1. Confirm every layer/size, target capacity, available extents/quota, data owner, restore evidence, encryption references and downtime tolerance.
2. Assign provider disk expansion to the provider pack; host partition/PV/LV/filesystem to Linux; data consistency to the data owner.
3. Verify online/offline support for exact filesystem/tool version. XFS growth and ext4 resizing differ; do not plan XFS shrink. Reducing an LV before a supported filesystem shrink destroys data. No generic shrink recipe.
4. State order and interruption recovery; rehearse equivalent disposable layouts. Growth often has no simple inverse; recovery may require restore.
5. Change one layer after approval; verify identity/size/health before proceeding. Verify mount options, ownership, persistence and application I/O.

Corruption, missing PVs and degraded arrays require a storage specialist and console-backed recovery before writes. No mounted fsck, force assembly, automatic repair flags or destructive write tests in discovery. Snapshot API success does not establish restore readiness.

Sources: [RHEL LVM](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_and_managing_logical_volumes/index), [filesystem management](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_file_systems/index).
