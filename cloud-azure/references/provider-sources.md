# Azure provider sources

last_verified: 2026-08-17
provider: Microsoft Azure
tooling_baseline: Azure CLI 2.88.0 was documented as current when checked; verify the installed CLI, extensions, cloud, and resource-provider API versions for every operation.

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

## Freshness procedure

1. Record installed Azure CLI and extension versions, active cloud, tenant, subscription, location, and resource-provider API version.
2. Open the exact official command and resource-provider operation reference immediately before planning a call. Distinguish core from extension commands and generally available from preview behavior.
3. Confirm provider registration, policy and lock effects, long-running-operation behavior, replacement risk, regional availability, and extension installation requirements.
4. Verify current RBAC permissions and role definitions; reduce the execution identity to the approved scope and resources.
5. Obtain cost, quota, recovery, and consistency behavior from current official product documentation or live read-only APIs; do not infer them from examples.
6. Record source URLs, `last_verified`, discovered target behavior, and discrepancies in the operation evidence.

Treat any stale source, undocumented field, unexpected extension, preview-only dependency, or target divergence as a stop condition.
