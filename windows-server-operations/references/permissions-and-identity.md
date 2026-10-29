# NTFS permissions and identity

Record the exact local object and parent chain, owner SID, inheritance/protection, explicit and inherited ACEs, allow/deny rights and propagation flags. Use SIDs as stable identifiers; translate display names only through the confirmed identity authority. Unresolved SIDs are evidence to investigate, not disposable entries.

Distinguish a null DACL (unrestricted by that DACL) from an empty DACL (no grants from that DACL). ACE order and requested rights matter; “deny always wins” is too coarse, especially across explicit/inherited entries. Ownership permits security administration in many contexts but is not ordinary data access. Share ACLs, token groups, deny-only SIDs, UAC filtering, central access policy, privileges, EFS and application authorization can alter the result.

Use `scripts/inspect-file-access.ps1` for bounded descriptor inventory on one approved local object. It does not evaluate a remote token, walk a tree, include SACL evidence or follow reparse points. For effective access, use the supported effective-access tooling plus actual intended-identity allowed/denied tests at the UNC/application path. An administrator's test is not the user's test.

## Change and rollback

1. Confirm business/access intent, exact objects/principals/rights, inheritance effects and configuration/GPO ownership. Avoid broad recursive selectors.
2. Capture parent and target before-state, including owner/group/DACL and, when required and authorized, SACL/central policy. icacls /save saves DACLs, not a complete file/security/share backup. Record the matching restore root and relative path semantics.
3. Model the smallest ACL delta and canary. Disabling inheritance with preservation versus removing inherited rules are different operations. Do not use /reset, takeown or recursive Full Control as a generic repair.
4. Preserve independent operator access and verify the restoring identity can apply the before-state. Backup/restore privileges can bypass checks and must be explicitly scoped, not casually enabled.
5. Apply the approved change, re-read canonical descriptor and verify intended allow/deny behavior, new sessions/token refresh and unaffected sibling/parent cases.
6. Restore only the reviewed exact state if rollback is valid. Reapplying an old descriptor over concurrent access changes is drift, not rollback; stop and reconcile.

Do not collect broad account/group dumps or enable audit privilege just to make a report look complete. SACL omission means audit policy is unverified. A DACL export does not preserve EFS decryption keys, share permissions, owner, streams or data.

Sources: [Get-Acl](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/get-acl?view=powershell-5.1), [ACE order](https://learn.microsoft.com/en-us/windows/win32/secauthz/order-of-aces-in-a-dacl), [icacls](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls).
