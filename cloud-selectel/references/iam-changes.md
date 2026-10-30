# One service-user project role

Bound the change to an existing Selectel service-user ID, account, project UUID and exact role name with `scope=project`. Account-wide permissions, group membership, credentials, owner changes and user deletion need separate plans. Compose privilege intent and revocation with `secrets-access-operations`; do not create or retrieve credentials during this procedure.

Selectel's IAM API is at `https://api.selectel.ru/iam/v1`. Its service-user role methods require an account-scoped IAM token, supplied by the protected worker's credential reference. An OpenStack project token or generic Keystone `role add` is not a substitute for this API. Confirm the API audience and account independently; a regional OpenStack configuration does not scope an account-wide IAM credential.

## Read and apply one tuple

Read the exact user through `GET /iam/v1/service_users/{user_id}` and resolve the current role through the IAM role reference/API. Obtain complete current direct and inherited permission evidence for that user and project, including group/account grants; preserve provenance, timestamp, before-state and untouched permissions. The published user GET reference does not fully specify its response schema: confirm the actual supported permission representation instead of inventing a `roles` field or a listing endpoint. If a complete attributable before/after comparison is unavailable, stop for the IAM owner.

| Intent | Exact documented method and payload | Required observation |
|---|---|---|
| Grant one role | `PUT /iam/v1/service_users/{user_id}/roles` with `{"roles":[{"project_id":"<retained-project-id>","role_name":"<reviewed-role>","scope":"project"}]}` | Re-read the exact user's permission evidence and authorized allowed/denied access probes |
| Revoke that role | `DELETE /iam/v1/service_users/{user_id}/roles` with the same one-tuple payload | Re-read direct/inherited access; removal of one grant does not prove effective revocation |

Both methods document `204 No Content`: there is no completion job or mutation ID in a response body to invent. Do not substitute user deletion for permission revocation: that separate API also deletes the user's keypairs. Select only a role confirmed to support the requested product/actions and project scope. A broad `member` or account grant is not an implicit workaround for denied verification.

## Contention, uncertain result and recovery

These role methods document no request idempotency token or expected-before-state precondition. Serialize the exact user/scope writers and re-read immediately before dispatch. A local lock does not exclude the console, another broker, group changes or an organization administrator; stop on drift.

After a lost response, retain the original operation/tuple and read the current permission state. A matching grant proves desired stored state, not which writer created it. An absent grant, stale view or authorization cache does not prove the write never occurred. Reconcile audit/request evidence and effective access within the [observation budget](async-recovery.md); never grant repeatedly to accelerate propagation or widen scope to diagnose a failure.

Grant and revoke are separate effects. Compensate only an attributable new grant after confirming no concurrent change now depends on it; preserve preexisting and inherited permissions. A recovery grant after a failed revoke must restore only the named prior intent under current authority. Do not restore a whole account/user snapshot. Report partial verification when current stored state or effective access cannot be established.

Sources checked 2026-10-30: [IAM role methods](https://docs.selectel.ru/en/api/users-and-roles/), [API URLs](https://docs.selectel.ru/en/api/urls/), [token scopes](https://docs.selectel.ru/en/api/authorization/), [permissions](https://docs.selectel.ru/en/access-control/permissions/), [role reference](https://docs.selectel.ru/en/access-control/role-reference/). Refresh exact role/actions and response representation before execution.
