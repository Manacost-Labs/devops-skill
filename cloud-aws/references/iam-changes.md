# IAM policy versions and role attachments

Use for one existing customer-managed policy ARN or one existing role/policy attachment. Role trust-policy changes, AWS-managed policy editing, credentials and service-linked roles need their own documented plan or specialist handoff. IAM is account-scoped: bind the partition, account, policy ARN and role's immutable `RoleId`, rather than treating a regional CLI selection as an IAM boundary.

## Preflight and exact operations

Read `GetRole`, `GetPolicy`, `ListPolicyVersions`, `GetPolicyVersion`, `ListEntitiesForPolicy` and `ListAttachedRolePolicies` as relevant. Follow IAM `IsTruncated`/`Marker` until complete even if a page contains fewer than `MaxItems`. Retain the old default version, decoded policy document digest, all version IDs, attachment before-state and affected principals. The raw API policy document is RFC3986 encoded; use a documented SDK decoding path or decode exactly once before canonical JSON comparison. Do not log policy documents with sensitive conditions.

| Change | Exact API parameters and outcome | Required re-read |
|---|---|---|
| Stage a policy version | `CreatePolicyVersion(PolicyArn, PolicyDocument, SetAsDefault=false)`; retain returned `PolicyVersion.VersionId` | `GetPolicyVersion` for the new ID and `GetPolicy` confirming the old default remains |
| Activate a staged version | `SetDefaultPolicyVersion(PolicyArn, VersionId)`; affects every attached principal | `GetPolicy.DefaultVersionId`, version content and authorized allowed/denied-path probes |
| Attach an existing policy | `AttachRolePolicy(RoleName, PolicyArn)`; changes permission policy, not trust | complete `ListAttachedRolePolicies`, `GetRole.RoleId`, actual permitted/denied requests |

Name `iam:CreatePolicyVersion`, `iam:SetDefaultPolicyVersion` or `iam:AttachRolePolicy` in the exact execution role as needed, scoped to the policy/role resources supported by the current authorization reference. Discovery permissions do not imply mutation permissions. Record SCPs, permission boundaries, session policies and resource policies separately; a policy attachment alone does not prove effective access. Never add wildcard rights to make verification pass.

## Contention, quota and lost response

These operations provide neither a client-token parameter nor an expected-default-version CAS parameter. Serialize writers for the policy/role, re-read before each step, and stop if any default, version inventory, document or attachment changed. A local lock does not exclude a console or external writer.

A managed policy stores at most five versions. Preserve the prior default for recovery; do not delete an arbitrary version to free a slot. Version cleanup requires named nondefault IDs and separate approved scope. Read current account usage/attachment limits through `GetAccountSummary` and the current IAM quota reference; a quota increase is not an implicit substep.

After a lost `CreatePolicyVersion` response, **do not repeat the create**: compare the complete before/after version sets and fetch new candidate documents. A unique matching document is a candidate, not ownership proof when another writer could have submitted it. Resolve using retained request/audit evidence; multiple candidates, unrelated versions or uncertain ownership stop activation and cleanup. After a lost default switch or attachment response, read the exact default/attachment state with bounded consistency waits; no response is not evidence that the change failed.

## Recovery and acceptance

IAM propagation can lag. Use the deadline and read-only backoff in [async recovery](async-recovery.md); never repeatedly write to accelerate propagation. Stage, activate and attach are separate journaled effects. If activation fails after staging, retain the inert version and reconcile it. Restore the retained default only after verifying that the current default is still this operation's version; detach only an attachment proven absent before this operation. If another writer changed either, stabilize and hand off rather than restoring an account-wide snapshot. Recheck effective allowed and denied behavior after recovery. Report partial verification when propagation or effective-access evidence remains incomplete.

Sources checked 2026-10-30: [CreatePolicyVersion](https://docs.aws.amazon.com/IAM/latest/APIReference/API_CreatePolicyVersion.html), [SetDefaultPolicyVersion](https://docs.aws.amazon.com/IAM/latest/APIReference/API_SetDefaultPolicyVersion.html), [AttachRolePolicy](https://docs.aws.amazon.com/IAM/latest/APIReference/API_AttachRolePolicy.html), [document encoding](https://docs.aws.amazon.com/IAM/latest/APIReference/API_GetPolicyVersion.html), [version pagination](https://docs.aws.amazon.com/IAM/latest/APIReference/API_ListPolicyVersions.html), [IAM consistency](https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot.html#troubleshoot_general_eventual-consistency), [IAM quotas](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_iam-quotas.html). Refresh the exact discovery, mutation and authorization pages before execution.
