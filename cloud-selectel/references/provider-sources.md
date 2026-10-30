# Selectel provider sources

last_verified: 2026-10-30
provider: Selectel
tooling_baseline: Selectel IAM API v1, Quota Management API v1 and documented OpenStack component references; record actual catalog endpoints, client/plugins and negotiated API versions for every operation. Managed Kubernetes and database capabilities retain discovery/routing scope.

## Official sources

- [Selectel documentation](https://docs.selectel.ru/en/)
- [Selectel API documentation](https://docs.selectel.ru/en/api/)
- [API authentication and token scopes](https://docs.selectel.ru/en/api/authorization/)
- [Identity and Access Management](https://docs.selectel.ru/en/access-control/)
- [Cloud Servers documentation](https://docs.selectel.ru/en/cloud-servers/)
- [Managed Kubernetes documentation](https://docs.selectel.ru/en/managed-kubernetes/)
- [Managed Kubernetes API](https://docs.selectel.ru/en/api/managed-kubernetes/)
- [Managed Databases documentation](https://docs.selectel.ru/en/managed-databases/)
- [Product security guidance](https://docs.selectel.ru/en/security-guide/manage-access/)

## Operation-specific evidence

The 2026-10-30 refresh opened the original Terraform, IAM/authentication, Cloud Servers, Managed Kubernetes and Managed Databases entrypoints plus the exact Selectel pages below. No live account, installed client, token, API quota or cloud resource was queried. Documentation and synthetic native-response tests cannot prove an account's compatibility, permissions, headroom, recovery or service health.

| Concern | Official Selectel references checked | Routed procedure |
|---|---|---|
| Service-user project-role grant/revoke and permission limits | [IAM API](https://docs.selectel.ru/en/api/users-and-roles/), [permissions](https://docs.selectel.ru/en/access-control/permissions/), [role reference](https://docs.selectel.ru/en/access-control/role-reference/), [API URLs](https://docs.selectel.ru/en/api/urls/) | [IAM changes](iam-changes.md) |
| Partial quota results, limits and pool endpoints | [quota API](https://docs.selectel.ru/en/api/quota-management/), [project limits/quotas](https://docs.selectel.ru/en/access-control/projects/quotas/), [URL list](https://docs.selectel.ru/en/api/urls/) | [async recovery](async-recovery.md) |
| Default SG, port security, MKS and active sessions | [SG semantics](https://docs.selectel.ru/en/cloud-servers/security-groups/about/about-security-groups/), [network security](https://docs.selectel.ru/en/cloud-servers/cloud-networks/about-networks/), [create rule](https://docs.selectel.ru/en/cloud-servers/security-groups/manage-rules/create-rule/), [delete rule](https://docs.selectel.ru/en/cloud-servers/security-groups/manage-rules/delete-rule/), [assign groups](https://docs.selectel.ru/en/cloud-servers/security-groups/manage-groups/assign-security-groups/) | [network changes](network-changes.md) |
| VM creation path, pool/segment, volume identity | [server creation](https://docs.selectel.ru/en/cloud-servers/create/create-server/), [network volumes](https://docs.selectel.ru/en/cloud-servers/volumes/about-network-volumes/), [client scope](https://docs.selectel.ru/en/cloud-servers/tools/openstack-cli/configure-openstack-cli/), [resource-envelope API](https://docs.selectel.ru/en/api/cloud-projects-and-resources/) | [compute changes](compute-changes.md) |
| Supported upstream components and version ceiling | [Selectel component table and upstream links](https://docs.selectel.ru/en/cloud-servers/tools/openstack-cli/about-openstack-cli/) | [compute changes](compute-changes.md), [network changes](network-changes.md) |

The Selectel component table explicitly links [Nova Compute API](https://docs.openstack.org/api-ref/compute/), [Neutron v2](https://docs.openstack.org/api-ref/network/v2/) and [Cinder v3](https://docs.openstack.org/api-ref/block-storage/v3/). Those linked official references were inspected for native response fields, request correlation, resource methods and version-dependent behavior. Their newest examples and optional extensions are not evidence of Selectel support: constrain use to the provider's documented ceiling and the discovered endpoint. Selectel's provider-owned pages remain the capability-source mapping in the manifest.

The attempted `/en/api/cloud-resources/` URL returned no readable page; the current linked `/en/api/cloud-projects-and-resources/` reference supplied the resource-envelope boundary. An attempted server-states URL was unavailable; native state fields come from the Selectel-linked Nova reference. The IAM GET reference leaves the response schema unspecified, so the runbook requires actual complete permission evidence or owner handoff rather than inventing a response/listing contract.

## Freshness procedure

1. Record the actual account and project UUID, region and pool, service catalog endpoint, client and plugin versions, token scope without its value, and service API version.
2. Open the exact official Selectel or explicitly referenced OpenStack API operation immediately before planning a call. Do not infer that generic OpenStack behavior applies.
3. Confirm product availability, API version, project limits, asynchronous-operation behavior, replacement risk, and regional or pool constraints.
4. Verify current Selectel role and token-scope requirements; reduce the execution identity to the approved project and services.
5. Obtain cost, quota, recovery, backup, and consistency behavior from current official product documentation or live read-only APIs; do not infer them from examples.
6. Record source URLs, `last_verified`, discovered target behavior, and discrepancies in the operation evidence.

Treat any stale source, undocumented field, OpenStack divergence, unexpected API version, or target discrepancy as a stop condition.
