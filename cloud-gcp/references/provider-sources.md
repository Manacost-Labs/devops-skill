# Google Cloud provider sources

last_verified: 2026-10-30
provider: Google Cloud
tooling_baseline: Compute Engine REST v1 and Resource Manager project IAM v1 references; verify the installed Google Cloud CLI, API model/release channel and exact operation before use. No installed CLI version is asserted by this documentation refresh.

## Official sources

- [Google Cloud CLI documentation](https://cloud.google.com/sdk/docs)
- [Google Cloud CLI release notes](https://cloud.google.com/sdk/docs/release-notes)
- [Google Cloud IAM overview](https://cloud.google.com/iam/docs/overview)
- [Virtual Private Cloud documentation](https://cloud.google.com/vpc/docs/overview)
- [Compute Engine documentation](https://cloud.google.com/compute/docs)
- [Google Kubernetes Engine documentation](https://cloud.google.com/kubernetes-engine/docs)
- [Cloud Run documentation](https://cloud.google.com/run/docs)
- [Cloud SQL documentation](https://cloud.google.com/sql/docs)
- [Cloud Billing documentation](https://cloud.google.com/billing/docs)

## Operation-specific evidence

On 2026-10-30 the existing architecture/IAM/CLI/VPC/Compute/GKE/Cloud Run/Cloud SQL documentation entrypoints and these exact operation references were opened. Google redirects many `cloud.google.com` links to `docs.cloud.google.com`. The old `cloud.google.com/resource-manager/reference/rest/v1/projects/{getIamPolicy,setIamPolicy}` URLs returned 404, while the explicitly listed `docs.cloud.google.com` URLs returned readable references. This refresh confirms documentation semantics, not live permissions, quotas, billing, service availability or installed tooling. No project was queried or changed.

| Concern | Official references checked | Local procedure |
|---|---|---|
| Project policy read/write and updateMask | [getIamPolicy](https://docs.cloud.google.com/resource-manager/reference/rest/v1/projects/getIamPolicy), [setIamPolicy](https://docs.cloud.google.com/resource-manager/reference/rest/v1/projects/setIamPolicy) | [IAM changes](iam-changes.md) |
| Conditions, concurrency and propagation | [policy versions](https://cloud.google.com/iam/docs/policies), [retry strategy](https://cloud.google.com/iam/docs/retry-strategy), [propagation](https://cloud.google.com/iam/docs/access-change-propagation) | [IAM changes](iam-changes.md) |
| Classic firewall method-specific semantics | [insert](https://docs.cloud.google.com/compute/docs/reference/rest/v1/firewalls/insert), [patch](https://cloud.google.com/compute/docs/reference/rest/v1/firewalls/patch), [rule behavior](https://cloud.google.com/vpc/docs/firewalls), [VPC quotas](https://cloud.google.com/vpc/docs/quota) | [network changes](network-changes.md) |
| One VM create and existing VM tags | [instances.insert](https://cloud.google.com/compute/docs/reference/rest/v1/instances/insert), [instances.setTags](https://docs.cloud.google.com/compute/docs/reference/rest/v1/instances/setTags), [allocation quotas](https://cloud.google.com/compute/resource-usage) | [Compute changes](compute-changes.md) |
| Scope, incarnation and bounded observation | [native zonal Operation](https://cloud.google.com/compute/docs/reference/rest/v1/zoneOperations), [handling requests/responses](https://cloud.google.com/compute/docs/api/how-tos/api-requests-responses) | [async recovery](async-recovery.md) |

The local inspector and synthetic tests exercise only saved instance-insert observation shapes, errors and identity mismatches. They are not an emulator or evidence of successful IAM/firewall/VM execution, recovery, quota availability or application health. Other cloud operations, including managed containers/databases, retain discovery/routing scope and need their own current exact operation sources. Refresh method-specific permissions, mutable model versions and live target facts before registering execution authority.

## Freshness procedure

1. Record the installed gcloud version and components, active account and configuration, project number and ID, location, and API endpoint or release channel.
2. Open the exact official CLI or REST operation reference immediately before planning a call. Do not mix general availability, beta, and alpha behavior.
3. Confirm API enablement, organization-policy constraints, service-agent effects, long-running-operation behavior, replacement risk, and regional availability.
4. Verify current IAM permissions and predefined-role contents; reduce the execution principal to the approved project and resources.
5. Obtain cost, quota, recovery, and consistency behavior from current official product documentation or live read-only APIs; do not infer them from examples.
6. Record source URLs, `last_verified`, discovered target behavior, and discrepancies in the operation evidence.

Treat any stale source, undocumented field, unexpected release channel, or target divergence as a stop condition.
