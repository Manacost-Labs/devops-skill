# Windows file and host recovery

Choose a recoverable point and scope: individual files/security, share configuration, volume, host/bare metal or application data. Confirm backup product/version, original host/volume identity, artifact catalog and integrity, encryption/EFS/BitLocker recovery references, storage capacity and isolated destination.

A VSS snapshot on the same failing disk, replication, a scheduled backup task or a green agent is not independent restore proof. Writer status is a diagnostic signal, not a successful application-consistent backup. Windows Server Backup/wbadmin and third-party products differ in supported recovery scopes and application handling.

## Capture and retention

Inventory data plus owner/group/DACL/SACL requirements, streams, EFS keys, share settings/ACL, task XML and credential references, host certificate/private-key recovery, service/configuration and application consistency. DACL/XML/.cer exports alone cannot recover all of those dependencies.

Establish quiescence/VSS writer consistency, backup privilege, performance/downtime limits and a trusted catalog. Preserve immutable/off-source recovery copies and separate backup-write, restore and deletion authority where required. Legal holds and retained-point dependencies govern retention; do not delete VSS shadows, logs or old backups simply to clear capacity warnings.

## Restore rehearsal

1. Prove isolated target identity and access. Prevent recovered tasks, services, replication, domain/cloud identity and production consumers from executing against real systems.
2. Validate compatible OS/firmware/boot/storage/product and keys by authorized references. A bare-metal or domain-controller recovery has additional dependencies; do not boot a cloned identity into the live network.
3. Restore into a separate known destination first using the exact product catalog/version and reviewed options. wbadmin recovery can overwrite files or restore security; choose scope deliberately. Do not blindly force a restore over live data.
4. Verify bytes and owner-defined data invariants, timestamps/streams where required, owner/permissions, intended allowed/denied access, share/task/certificate dependencies and service/user path. A matching hash alone is insufficient.
5. Measure retrieval, decryption, restore, checks, service/client cutover and observation. Report the achieved point/loss bound and total recovery time with unknowns, not merely command duration.
6. Approve overwrite/cutover separately, preserve originals and failed-target evidence, then observe service and security behavior. Once new writes occur, reverting a route is not necessarily rollback.

System state/AD recovery composes with the directory owner and its verified forest/DC procedure. SQL Server, Exchange and other application-consistent recovery require their specialist owner/product runbook; the current database-resilience module does not supply them. Never edit NTDS/SYSVOL or replay an arbitrary database restore as a Windows host repair.

Sources: [wbadmin recovery](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/wbadmin-start-recovery), [VSS writers](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/vssadmin-list-writers), [system state backup](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/forest-recovery-guide/ad-forest-recovery-backing-up-system-state).
