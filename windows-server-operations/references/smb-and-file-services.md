# SMB shares and file services

Map client identity/credential context -> UNC/DFS name -> actual server/cluster share -> share security -> local path/mount -> filesystem permissions -> data. Confirm requested operation (list/read/create/modify/delete), client address/family, timestamp and expected denied behavior. A hidden share or access-based enumeration changes visibility, not authorization.

Inspect exact Get-SmbShare/Get-SmbShareAccess and relevant sessions/open files through the existing authorized session. Do not dump all clients, credentials or paths into public evidence. Distinguish a normal local share, administrative share, DFS namespace/replication and clustered/scoped/continuously available share. Cluster/DFS changes need their topology owner; do not recreate a clustered share as a standalone shortcut.

## Diagnose and change

Remote access depends on share and filesystem checks plus the actual token, groups, claims, policy, network authentication and other controls. Local administrator access does not reproduce a remote user's token. Identify whether denial happens before SMB authentication, at the share, on a parent path or on the file. A cached connection with different credentials or a stale token can invalidate testing; do not disconnect unrelated sessions to simplify it.

Record share name/scope, local target identity, selected flags (encryption, caching, ABE, availability), share ACL and NTFS descriptor baseline, open handles/leases and application dependencies. Plan exact changes with both data and access owners. SMB signing/encryption and authentication defaults differ by OS/build and client; preserve protection and investigate negotiation/policy instead of disabling it or enabling guest/SMB1.

Verify a new session as the intended user from the actual path, including allowed read/write/delete and a meaningful forbidden operation. Server-side cmdlet success proves configuration, not client access. Do not close all SMB sessions/open files; forced closure can lose writes and needs separate scope/approval.

## Migration and recovery

Inventory bytes, file count, ACL/owner/audit requirements, alternate streams, EFS keys, reparse points, sparse/compressed files, quotas and application consistency. Choose an explicit source/destination and small rehearsal. Robocopy options determine what is preserved; /COPYALL and backup mode require corresponding privilege, while /MIR and /PURGE can delete destination data. A listing preview is not a lock or execution approval. Scope retries/waits and avoid unbounded junction traversal.

Preserve original data/share definitions and a reviewed rollback or cutover plan. Same-volume moves, cross-volume copies and inheritance at the destination can produce different access. Treat exit codes >=8 as failure; lower robocopy codes still need file/security/application verification and interpretation of mismatches/extras. Do not regard code 0 alone as proof of full metadata fidelity.

For restore use a separate quarantine destination first, validate data and descriptor/owner/streams plus client behavior, then separately approve overwrite/cutover. A file-content backup does not restore the SMB definition, and replication/VSS alone is not an independent backup.

Sources: [SMB](https://learn.microsoft.com/en-us/windows-server/storage/file-server/file-server-smb-overview), [robocopy](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy).
