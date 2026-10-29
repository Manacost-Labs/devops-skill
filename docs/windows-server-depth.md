# Windows Server expansion in 0.7.0

The Windows module now covers the day-to-day host, file/security and recovery boundaries with focused references. It remains one of 23 modules under contract v2.

| Area | Added decisions/procedures | Verification boundary |
|---|---|---|
| SMB and NTFS | Share versus filesystem access, tokens/SIDs, inheritance, exact ACL deltas, migration and file recovery | Actual intended-identity allowed/denied tests; local admin or ABE is insufficient |
| Host certificates/keys | Store/consumer identity, validity/SAN/EKU, key ACL, renewal/binding and recovery | Key presence does not prove service access or client chain/name/revocation trust |
| Task Scheduler | Principal/logon, action/working-directory permissions, triggers/DST, export/rollback and result evidence | XML/registration success is not actual job correctness or authorization to execute |
| Standalone storage | Immutable disk/volume/backing identity, NTFS/ReFS, pools/jobs, resize/repair and encryption recovery | Provider/cluster/DFS/application owners retain their layers |
| Security/recovery | Effective policy, independent management recovery, VSS/backup scope, file/host restore and measured acceptance | Snapshots, agents, task presence and command duration alone do not prove recovery |

Use the new `windows-server` install profile for host + access + reliability, or `identity-directory` when AD/GPO work is required. The main README describes preview/apply and full-runtime installation. AD CS/CA recovery, complex clusters/DFS and SQL Server/Exchange recovery require their confirmed specialist runbooks; generic database resilience does not imply support.

## Evidence helpers

The host audit now emits bounded JSON with explicit unknown/truncation and rejects a workstation/unrecognised server build. It no longer copies raw event messages, task actions or service command lines, or equates a stopped automatic service with failure. It still relies on trusted native tooling and session-level time bounds.

Additional read-only helpers inventory one local file descriptor, one exact certificate, or one offline task definition. They preserve the distinction between observed metadata and effective access/trust/execution. Offline XML parsing disables DTD/external entities and caps input; it never registers or runs imported work. Protect local paths/artifacts against concurrent replacement and redact reports before sharing.

## Native tests and limits

Unit/adversarial checks run in Windows PowerShell 5.1 and PowerShell 7, using owned temporary files, in-memory certificates and mocked host probes. They check malformed/oversized/entity-bearing XML, omitted sensitive content, unknown failures and workstation rejection.

A separate hosted Server 2025 job creates only uniquely owned ephemeral resources: NTFS denied-write/descriptor rollback and file-content/DACL recovery, a restricted encrypted SMB definition, a disabled task registration/export, a CurrentUser test PFX export/import with actual restored-key signing, and a new small VHD whose exact backing identity is checked before filesystem work. Cleanup validates resource ownership and detach state before deleting fixture files. It does not alter firewall policy, live bindings, trust roots or production accounts.

These fixtures do not certify Server 2019/2022, remote SMB client tokens, application/task execution, service-account key ACLs, real trust/revocation, ReFS/cluster/physical disk repair, EFS/BitLocker disaster access, VSS application consistency or bare-metal recovery. Rehearse the actual chosen build/role/topology and user/application acceptance before those claims.
