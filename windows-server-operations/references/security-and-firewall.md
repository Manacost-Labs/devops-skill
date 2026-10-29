# Host security and firewall

Confirm actual host/domain role, effective GPO/MDM/configuration source, service identity, active network profile and independent recovery. Local edits can be superseded by policy; they must not bypass central intent.

Review exact firewall rule identity, direction/profile/interface/address/port/program/service and effective policy store. Inspect IPv4/IPv6 and the intended source/return path. A running WinRM/RDP service does not prove a reachable authorized listener. Preserve rule ordering/old state and a tested console/alternate path before narrowing access. Test a new authorized session and a meaningful denied source without disconnecting the last known-good session.

Keep Defender, UAC, auditing, SMB protection and TLS validation active. Diagnose specific access/negotiation or application compatibility; do not switch off the control to suppress an event. Security exclusions, trusted-root changes, local administrator grants, privileged task identities and private-key permissions need exact owner-approved scope and expiry where appropriate.

Use scoped local identity/SID evidence; do not dump all users/groups, credential stores, LSASS memory, recovery secrets or task arguments. JEA/JIT and service/gMSA credential lifecycle compose with secrets-access and directory owners. PowerShell execution policy is not a security sandbox or production authorization gate.

Hardening is a staged compatibility change with a named control owner, canary, effective-policy verification and rollback. A benchmark scan alone cannot certify the host secure. Preserve Event Logs and forensic evidence during a suspected compromise; incident containment/recovery takes precedence over routine cleanup.

Sources: [Windows Firewall](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/), [PowerShell security](https://learn.microsoft.com/en-us/powershell/scripting/security/security-features?view=powershell-7.5).
