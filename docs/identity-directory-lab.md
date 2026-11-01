# Directory diagnosis and recovery lab

The `identity-directory-operations` module covers AD replication versus DFSR/SYSVOL, GPO applicability/precedence, exact delegation and single-object/GPO recovery. Its references route each diagnostic branch without broad repair commands. Ordinary Windows-host CI does **not** exercise a domain, GPO processing, AD object restore or SYSVOL recovery.

## Required separate target

Use an owner-approved disposable `.test` forest with two writable DCs and a domain member/canary on the chosen Server build. Isolate its virtual network from production, disable external trusts and production credential reuse, reserve an independent console/recovery identity, and record exact domain, NTDS and VM identities. Domain creation, Recycle Bin enablement, roles, networking, membership and reboot need their own approved provisioning plan; this repository does not discover or repurpose arbitrary VMs. Test each supported release/topology before claiming it.

Run reviewed source on a protected management host with Windows PowerShell 5.1, AD/GroupPolicy RSAT and a scoped lab management session. Read-only access does not grant mutation authority. Protected execution in platform 0.15 requires an administrator-registered immutable typed task, external signed grant and exact R4 admission; no AD recovery task is shipped or configured here. Local operation_gate results, unsigned requests and owner-run flags are planning-only. Do not give a public PR a domain credential or persistent privileged runner. Run integration manually against the reviewed commit in the isolated lab; publish only redacted receipt/digests. Keep raw GP reports, backup contents and principal/topology data in access-controlled storage.

## Read-only preflight and planned recovery fixtures

The source-only `tests/check_identity_directory_lab.ps1` requires fixtures prepared by the lab owner:

- One dedicated OU and one disabled disposable user directly inside it, both with description `DevopsSkillDisposable:<lab_id>`. The user has no non-primary memberships, SID history, service principal names or protected flags, and primary group 513. Enable Recycle Bin **before** creating/deleting the fixture under its separate approved plan.
- One dedicated, entirely **unlinked** nondefault GPO with the same description and a String registry setting `HKLM\Software\Policies\DevopsSkillLab`, value name `RecoveryMarker`, value equal to `<lab_id>`. This avoids applying the recovery-test mutation to clients. Do not attach scripts, secrets or production settings to this fixture.
- An existing local backup parent protected from other writers, with enough space. The child `<backup_parent>/<lab_id>` must not exist. The read-only preflight creates nothing. The external owner drill retains its exact fresh `Backup-GPO` instance and does not automatically delete backups or the OU/GPO/user.

Create a private JSON plan from live read-only inventory. All IDs below are synthetic placeholders to replace; the script rejects empty GUIDs and identity mismatch. `script_sha256` is the lowercase SHA-256 of the reviewed preflight script. Preserve a digest of the saved plan bytes as evidence and, for a future registered task, bind those bytes through its administrator-defined typed parameters. A local plan digest never authorizes execution.

```json
{
  "schema_version": "1.0",
  "lab_id": "directory-lab-20261030-fixture01",
  "domain_dns": "directory-lab.test",
  "domain_guid": "11111111-1111-4111-8111-111111111111",
  "servers": [
    {"host": "dc1.directory-lab.test", "ntds_guid": "22222222-2222-4222-8222-222222222222"},
    {"host": "dc2.directory-lab.test", "ntds_guid": "33333333-3333-4333-8333-333333333333"}
  ],
  "ou_guid": "44444444-4444-4444-8444-444444444444",
  "object_guid": "55555555-5555-4555-8555-555555555555",
  "gpo_guid": "66666666-6666-4666-8666-666666666666",
  "backup_parent": "D:\\ProtectedDirectoryLab",
  "script_sha256": "REPLACE_WITH_REVIEWED_SCRIPT_SHA256",
  "timeout_seconds": 300
}
```

The plan is a source-only fixture description, not an execution request. Its `.test` suffix is an explicit harness restriction, not evidence of isolation. Existing domains with another suffix need a separately reviewed fixture plan; do not rename a real domain to satisfy this check.

From the source root, validate the plan without connecting to AD:

```powershell
powershell.exe -NoProfile -File tests/check_identity_directory_lab.ps1 -PlanPath D:\ProtectedDirectoryLab\plan.json
```

With approved read-only access, an isolated lab operator can add `-ReadOnly` to inspect exactly those two DCs, replica health/recency, SYSVOL/NETLOGON availability, fixture identities, disabled nonprivileged user, Recycle Bin state and matching GPO AD/SYSVOL version counters. The script creates no backups and changes no directory or policy state. `-Execute` always refuses **before** reading plan metadata or importing AD/GPMC. Neither a forged approval field nor an owner-run flag enables it.

Native LDAP/SMB/GPMC calls can exceed the declared planning deadline: use an external process/session watchdog for read-only probes. Even successful preflight returns `partially_verified`; matching counters and shares do not establish SYSVOL content integrity, client application, effective delegation or recovery.

## External owner-controlled recovery drill

This is a concrete **planned** integration drill, not an executable agent mutation path. The separate lab owner uses their own protected change process and tools. Agent-driven execution remains blocked until an administrator installs an immutable typed AD task on a separately protected worker, reviews its exact target/parameter/risk boundaries, and supplies external signed grant plus exact destructive R4 admission. Do not add that task, signing keys, write credentials, registry or bypass to this public source checkout. The task must journal intent/outcome, enforce the actual lock and recheck admission and fresh state by phase; a local operation_gate ALLOWED result is insufficient.

1. Establish a clean baseline: record domain and both NTDS identities; exact user GUID/SID, original parent/name, disabled state, attributes, memberships and delegation; exact unlinked GPO GUID, marker, report, DACL/WMI and versions. Back up the dedicated GPO in protected storage and record the fresh backup-instance ID and artifact digests. Demonstrate usable independent lab recovery before deleting a fixture.
2. Immediately before deleting the exact fixture user, re-read its SID/GUID/parent, disposable marker, account/protected state and memberships, and compare the write-DC change metadata with the baseline. Any drift aborts. The owner deletes only that fixture and observes the same tombstone GUID on both DCs within a deadline.
3. Immediately before exact object restoration, recheck deleted/restorable state, lastKnownParent, Recycle Bin eligibility, original parent GUID/DN/marker and absence of name conflicts. A missing parent, unexpected privilege or changed method requires a new owner decision. After restoration, both DCs must show the original GUID/SID/location, disabled nonprivileged state and intended links; an unrelated fixture must be unchanged.
4. Immediately before changing the benign GPO marker, re-read its complete policy/permission/WMI/description/version and external links against the original baseline. It must still be dedicated and entirely unlinked. Compare report content after removing only generated ReadTime, and check the exact baseline registry value. An unexpected link, edit, permission or version change aborts before any GPO mutation.
5. After the owner changes the one benign marker, record the exact expected resulting report/version. Immediately before backup-ID restore, repeat the live checks against that expected state, including the unlinked condition and backup digest. Abort on concurrent changes rather than overwriting them. Restore only the reviewed existing GPO from that exact backup instance; then verify the baseline marker/content and both DCs' GPC/GPT convergence. Deleted-GPO recovery is a separate untested method.
6. Retain redacted timestamps, elapsed recovery, source/task digests, expected/observed results and partial-state flags. On failed/unknown outcome stop, preserve backups and reconcile state before retrying or cleanup. Never force replication or perform an unapproved automatic rollback. Remove only exact owned fixtures through a separately reviewed cleanup.

Until these steps actually run with acceptance evidence, object and GPO recovery stay `not_run`. This repository currently ships no runnable destructive AD integration task.

## Required domain acceptance matrix

Run each row under an exact owner-approved fixture plan and preserve timestamped source commit, target/build IDs, command results, expected/observed difference, elapsed recovery and artifact hashes. Missing rows remain `not_run`; unknown/failed rows prevent a verified domain claim.

| Scenario | Fault and expected evidence | Recovery/negative check |
|---|---|---|
| AD versus SYSVOL | On isolated fixture infrastructure, an owner-controlled network fault makes one serving DC stale; inspect partner result/time, exact object metadata and GPC/GPT independently | Restore the exact network before-state through its owner; normal replication converges before deadline. Never force replication to pass |
| Non-applied policy | Link a separate benign canary policy only to its pilot OU; demonstrate the intended computer value and fresh computer RSoP/GroupPolicy activity/DC | An excluded canary identity lacks the value and shows the correct filtering reason. WMI false, disabled half and stale token are distinct cases |
| Inheritance | Separate parent/child fixture OUs and benign conflicting settings show order 1, inheritance block and enforced-ancestor behavior | Remove only the test deltas; verify expected winner on client. Keep default domain/controller policies untouched |
| Delegation | A dedicated limited identity performs its approved action inside one fixture OU | The same identity is denied the comparable action in a separately named sibling OU and cannot edit/link an unrelated GPO. An admin token is invalid evidence |
| Single object | External exact-fixture delete/restore drill above | Original GUID/SID/location, disabled state, expected links and no unexpected privilege on both DCs; another fixture remains unchanged |
| Existing GPO | External marker change/backup-ID restore drill above | Restored setting and AD/GPT convergence, independent permission/link/WMI baseline; a separate canary processing cycle proves the selected settings |
| Refusal | Current preflight rejects wrong plan/domain/DC/GUID/marker, default GPO, unhealthy baseline or modified script; `-Execute` always refuses. A future external task must additionally reject linked/changed fixtures, expired grants, missing exact admission and drift | Current harness performs zero mutations. External task refusal must occur before its affected write; unknown state is not success |

SYSVOL authoritative/non-authoritative recovery, deleted-GPO recovery, forest/DC disaster recovery, protected objects, trusts and unsupported classes remain specialist rehearsals beyond this fixture. A clean lab, matching versions or an offline fixture cannot substitute for those tests.

## CI and reporting boundary

The existing PR validation remains enabled, including Windows-host native fixtures. New regression tests exercise script parsing, plan/digest boundaries and refusal without connecting to a domain; refusal tests trap all native calls before an execution request can reach AD; evaluation fixtures support independent agent forward-testing and do not automatically grade the agent's behavior. No domain integration success is claimed by those jobs. Until the separate lab is actually executed and the acceptance rows have evidence, report domain behavior as `partially_verified` with each missing scenario listed.
