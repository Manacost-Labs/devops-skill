# One Azure RBAC role assignment

Bound the change to the active cloud, tenant, subscription, exact scope, existing principal object ID, principal type and full role-definition ID. An application/client ID or display name is not the principal's object ID. Keep Entra identity lifecycle, credential changes, PIM and access intent with `secrets-access-operations`; this procedure changes the provider assignment only. Detect IaC ownership before planning a direct change.

## Exact request and before-state

Use Authorization API `2022-04-01` only after confirming it is supported on the selected cloud. The resource path is `{scope}/providers/Microsoft.Authorization/roleAssignments/{assignment-guid}`. Retain one stable assignment GUID before dispatch; assignment names must be unique within the tenant. Read the exact assignment and complete relevant direct/inherited assignments, role definition, deny assignments, conditions and governance constraints. Follow pagination to completion and distinguish an absent assignment from a denied or failed lookup.

For a new assignment, plan a `PUT` to that path with `properties.principalId`, `roleDefinitionId`, the confirmed `principalType` and any reviewed `condition`/`conditionVersion`. The current condition version is `2.0`; preserve the actual intended condition rather than widening access. `Microsoft.Authorization/roleAssignments/write` is the mutation permission; discovery and deletion require their separate permissions. Do not grant directory-wide lookup rights just to resolve a name when an independently confirmed object ID is available.

The GUID and request digest identify this intended assignment. They do not make arbitrary body changes safe. These create/get/delete operations do not document a compare-and-swap header. Serialize writers and re-read immediately before dispatch; a local lock does not exclude another controller or console. Stop on conflicting tuple, condition or ownership. A principal/role/scope change is a new plan, not an in-place retry under the old GUID.

## Lost response, propagation and recovery

After a timeout or `RoleAssignmentExists`, GET the retained scope/GUID and compare principal, role, scope and conditions. A matching assignment proves observed state, not that this operation created it. A missing or unreadable result remains uncertain; do not generate a new GUID or remove a preexisting matching assignment to make a retry pass. Preserve request/activity evidence and reconcile concurrent writers.

An assignment can exist before access takes effect. Microsoft documents ordinary role changes taking up to ten minutes and longer managed-identity group caches. Use bounded observations and fresh authorized identity context; never print tokens, repeatedly recreate the assignment, or broaden roles to defeat propagation. Check subscription assignment-limit headroom separately from effective authorization.

Compensate only an assignment proven absent before this operation and still matching its exact post-state. `DELETE` of the retained scope/GUID is separately authorized recovery; its `200`/`204` response must be followed by absence and effective-access checks. Removing one assignment does not remove inherited or group-derived rights. Preserve current state and hand off when another writer changed it. Verify both the intended allowed action and a scoped denied action; incomplete effective-access evidence is `partially_verified`.

Sources checked 2026-10-30: [assignment identity](https://learn.microsoft.com/en-us/azure/role-based-access-control/role-assignments), [create](https://learn.microsoft.com/en-us/rest/api/authorization/role-assignments/create?view=rest-authorization-2022-04-01), [get](https://learn.microsoft.com/en-us/rest/api/authorization/role-assignments/get?view=rest-authorization-2022-04-01), [delete](https://learn.microsoft.com/en-us/rest/api/authorization/role-assignments/delete?view=rest-authorization-2022-04-01), [propagation and lookup failures](https://learn.microsoft.com/en-us/azure/role-based-access-control/troubleshooting). Refresh exact permissions, limits and API support before execution.
