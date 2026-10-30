# Azure provider sources

last_verified: 2026-10-30
provider: Microsoft Azure
tooling_baseline: Azure CLI 2 documentation and operation-specific REST examples below; verify the installed CLI, extensions, cloud, and resource-provider API versions for every operation. No installed Azure CLI or live subscription was inspected for this update.

## Official sources

- [Azure CLI documentation](https://learn.microsoft.com/en-us/cli/azure/?view=azure-cli-latest)
- [Azure CLI installation and current version](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli?view=azure-cli-latest)
- [Azure CLI reference status and extensions](https://learn.microsoft.com/en-us/cli/azure/reference-types-and-status?view=azure-cli-latest)
- [Azure role-based access control](https://learn.microsoft.com/en-us/azure/role-based-access-control/overview)
- [Azure Virtual Network overview](https://learn.microsoft.com/en-us/azure/virtual-network/virtual-networks-overview)
- [Azure Virtual Machines overview](https://learn.microsoft.com/en-us/azure/virtual-machines/overview)
- [Azure Kubernetes Service overview](https://learn.microsoft.com/en-us/azure/aks/what-is-aks)
- [Azure Container Apps overview](https://learn.microsoft.com/en-us/azure/container-apps/overview)
- [Azure SQL Database overview](https://learn.microsoft.com/en-us/azure/azure-sql/database/sql-database-paas-overview)
- [Azure Cost Management documentation](https://learn.microsoft.com/en-us/azure/cost-management-billing/)

## Operation-specific evidence

The 2026-10-30 documentation refresh opened the existing framework, CLI, RBAC, VNet, VM, AKS, Container Apps and SQL entrypoints and the exact pages below. Microsoft Learn included a sign-in notice but exposed the referenced API schemas/content. Documentation inspection and synthetic saved-response tests do not prove live permission, capacity, cloud API availability, resource state or application health. Managed-container/database scope remains discovery and specialist routing; no account was queried or changed.

| Concern | Official references checked | Procedure |
|---|---|---|
| Assignment identity and provider effects | [identity](https://learn.microsoft.com/en-us/azure/role-based-access-control/role-assignments), [PUT](https://learn.microsoft.com/en-us/rest/api/authorization/role-assignments/create?view=rest-authorization-2022-04-01), [GET](https://learn.microsoft.com/en-us/rest/api/authorization/role-assignments/get?view=rest-authorization-2022-04-01), [DELETE](https://learn.microsoft.com/en-us/rest/api/authorization/role-assignments/delete?view=rest-authorization-2022-04-01), [propagation](https://learn.microsoft.com/en-us/azure/role-based-access-control/troubleshooting) | [RBAC assignment](rbac-assignments.md) |
| Rule identity, limited concurrency, path semantics | [PUT](https://learn.microsoft.com/en-us/rest/api/virtualnetwork/security-rules/create-or-update?view=rest-virtualnetwork-2026-01-01), [GET](https://learn.microsoft.com/en-us/rest/api/virtualnetwork/security-rules/get?view=rest-virtualnetwork-2026-01-01), [DELETE](https://learn.microsoft.com/en-us/rest/api/virtualnetwork/security-rules/delete?view=rest-virtualnetwork-2026-01-01), [flow evaluation](https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview) | [NSG rule](network-rules.md) |
| Guarded VM request and incarnation | [PUT](https://learn.microsoft.com/en-us/rest/api/compute/virtual-machines/create-or-update?view=rest-compute-2025-04-01), [GET/vmId](https://learn.microsoft.com/en-us/rest/api/compute/virtual-machines/get?view=rest-compute-2025-04-01), [case-insensitive names](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-name-rules) | [VM](vm-changes.md) |
| Quota/capacity and surviving dependencies | [quotas](https://learn.microsoft.com/en-us/azure/virtual-machines/quotas), [deletion settings](https://learn.microsoft.com/en-us/azure/virtual-machines/delete) | [VM](vm-changes.md) |
| Native async response and retry distinctions | [tracking protocols](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/async-operations), [throttling](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling) | [observation/recovery](async-recovery.md) |

The offline inspector supports a deliberately limited saved-response profile: public `AzureCloud`, a Compute `/locations/{location}/operations/{guid}` tracking URL with one non-preview `api-version`, ASCII VM resource names, a retained `vmId`, and a native Azure-AsyncOperation body. It performs no authenticated request and does not validate source authenticity. Other valid ARM protocols or identifiers require their own documented observation path, not a relaxed authority or network allowlist.

## Freshness procedure

1. Record installed Azure CLI and extension versions, active cloud, tenant, subscription, location, and resource-provider API version.
2. Open the exact official command and resource-provider operation reference immediately before planning a call. Distinguish core from extension commands and generally available from preview behavior.
3. Confirm provider registration, policy and lock effects, long-running-operation behavior, replacement risk, regional availability, and extension installation requirements.
4. Verify current RBAC permissions and role definitions; reduce the execution identity to the approved scope and resources.
5. Obtain cost, quota, recovery, and consistency behavior from current official product documentation or live read-only APIs; do not infer them from examples.
6. Record source URLs, `last_verified`, discovered target behavior, and discrepancies in the operation evidence.

Treat any stale source, undocumented field, unexpected extension, preview-only dependency, or target divergence as a stop condition.
