# Project IAM bindings

Bound the change to one confirmed project ID **and project number**, principal identity, exact role and condition. Changing a project allow policy does not remove access inherited from its folder/organization or override a deny policy. Compose privilege intent with `secrets-access-operations`; Terraform/Config Connector ownership goes to `iac-operations`.

## Read, modify, write

1. Call Resource Manager v1 `POST /v1/projects/{project}:getIamPolicy` with `options.requestedPolicyVersion=3`. Retain the complete returned policy, `etag`, bindings and conditions, audit configuration, timestamp and digest. A response can legitimately use version 1 when no conditions exist; an old version-1 projection containing `_withcond_` roles is not an editable policy.
2. Prepare only the named principal/role/condition delta. Preserve unrelated bindings, all condition expressions and audit settings. Conditional and unconditional bindings for the same role are distinct. Do not silently replace an existing condition with an unconditional binding. Resolve deleted/recreated principal identities explicitly.
3. Use `POST /v1/projects/{project}:setIamPolicy` with the fresh policy `etag`; use policy version 3 when conditions exist. Review the API's `updateMask`: its default updates bindings and etag, not arbitrary policy fields. A binding change must not broaden the mask into an audit-configuration change. `resourcemanager.projects.getIamPolicy` and `resourcemanager.projects.setIamPolicy` are separate permissions; discovery access does not grant write access.
4. Re-read with requested version 3, compare the intended delta and untouched fields, then perform authorized allowed/denied-path probes. Stored bindings, inherited access, group propagation and effective access are different observations.

Keep one in-flight policy mutation per project. An IAM `409 ABORTED` means contention: apply bounded jittered backoff, then repeat the **whole read-modify-write cycle**, preserving the newest unrelated changes. Never resend a stale policy repeatedly. A refreshed policy outside the reviewed intent or scope requires a revised plan; a lock local to this client does not exclude other writers.

## Uncertain result and recovery

`setIamPolicy` has no Compute-style `requestId`. If its response is lost, read the latest version-aware policy and compare the exact binding delta and retained before-state. A matching binding establishes desired stored state, not which writer created it. Use audit/request evidence before claiming ownership. Absence during propagation does not authorize a blind stale write.

Use the common [observation budget](async-recovery.md). On contention or uncertainty beyond that budget, stop writes and report the latest etag, confirmed delta and safe next read. Permission errors, malformed conditions and policy limits require correction, not a retry storm.

Undo only the attributable binding delta using a **new** complete read and etag. Do not restore the entire old policy or overwrite another writer's condition/audit changes. A preexisting binding is never an owned effect to remove. Recheck allowed/denied behavior after recovery; delayed group or policy propagation may leave the result partially verified.

Sources checked 2026-10-30: [getIamPolicy](https://docs.cloud.google.com/resource-manager/reference/rest/v1/projects/getIamPolicy), [setIamPolicy and updateMask](https://docs.cloud.google.com/resource-manager/reference/rest/v1/projects/setIamPolicy), [policy versions and etags](https://cloud.google.com/iam/docs/policies), [whole-cycle retry](https://cloud.google.com/iam/docs/retry-strategy), [access propagation](https://cloud.google.com/iam/docs/access-change-propagation). Refresh the exact resource/action/role documentation before execution.
