# AD DS and GPO safety boundary

## Official source baseline

Last verified: 2026-08-17. Before a mutation, refresh the exact Microsoft Learn page for the intended cmdlet and reconcile it with read-only discovery from the authoritative writable domain controller.

- Active Directory cmdlets: <https://learn.microsoft.com/en-us/powershell/module/activedirectory/?view=windowsserver2025-ps>
- Group Policy cmdlets: <https://learn.microsoft.com/en-us/powershell/module/grouppolicy/?view=windowsserver2025-ps>
- Active Directory security guidance: <https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/plan/security-best-practices/best-practices-for-securing-active-directory>

## Ownership matrix

| Concern | Owner | Required composition |
|---|---|---|
| AD DS object, OU, group, delegation, GPO, link, security filter | This module | `secrets-access-operations` for privileged-session and lifecycle controls |
| Windows host domain join, local policy result, WinRM/RDP, local groups | `windows-server-operations` | This module supplies the approved directory/GPO fragment |
| Entra ID, Azure RBAC, hybrid cloud directory API | `cloud-azure` | `secrets-access-operations` governs access intent and lifecycle |
| GPO-driven service availability and user-path acceptance | Owning service module | `reliability-operations` verifies observation-window health |

## Preflight and rollback evidence

For every mutation record the forest/domain, authoritative server, exact target DN/GUID, current object or GPO version, planned delta, execution identity, change lock, approval reference, and expiry. Never preserve passwords, ticket material, key material, or unrestricted reports.

For GPO work, require a fresh `Backup-GPO` artifact reference, baseline report, link/filter/precedence capture, approved pilot scope, result-of-policy evidence, and an explicit restore or unlink decision. For group/delegation work, require before/after immutable principal identifiers, a bounded positive test, a meaningful denied-action test, and a recovery administrator path.

## Stop conditions

Stop and escalate on replication or SYSVOL ambiguity, a protected or privileged group, an unexpected inherited/enforced GPO, a default-policy target, a broad delegation request, a cross-domain import without a reviewed migration mapping, a missing canary, or any plan/approval/target drift.
