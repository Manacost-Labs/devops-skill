# Selectel provider sources

last_verified: 2026-08-17
provider: Selectel
tooling_baseline: Selectel product APIs and OpenStack-backed cloud services expose service-specific versions; record the actual service catalog, endpoint, client plugins, and API version for every operation. Managed Kubernetes API v2.0.0 was current when checked.

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

## Freshness procedure

1. Record the actual account and project UUID, region and pool, service catalog endpoint, client and plugin versions, token scope without its value, and service API version.
2. Open the exact official Selectel or explicitly referenced OpenStack API operation immediately before planning a call. Do not infer that generic OpenStack behavior applies.
3. Confirm product availability, API version, project limits, asynchronous-operation behavior, replacement risk, and regional or pool constraints.
4. Verify current Selectel role and token-scope requirements; reduce the execution identity to the approved project and services.
5. Obtain cost, quota, recovery, backup, and consistency behavior from current official product documentation or live read-only APIs; do not infer them from examples.
6. Record source URLs, `last_verified`, discovered target behavior, and discrepancies in the operation evidence.

Treat any stale source, undocumented field, OpenStack divergence, unexpected API version, or target discrepancy as a stop condition.
