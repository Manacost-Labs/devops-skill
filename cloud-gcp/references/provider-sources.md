# Google Cloud provider sources

last_verified: 2026-08-17
provider: Google Cloud
tooling_baseline: Google Cloud CLI release notes were current through 577.0.0 (2026-07-21) when checked; verify the installed CLI and live API release channel for every operation.

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

## Freshness procedure

1. Record the installed gcloud version and components, active account and configuration, project number and ID, location, and API endpoint or release channel.
2. Open the exact official CLI or REST operation reference immediately before planning a call. Do not mix general availability, beta, and alpha behavior.
3. Confirm API enablement, organization-policy constraints, service-agent effects, long-running-operation behavior, replacement risk, and regional availability.
4. Verify current IAM permissions and predefined-role contents; reduce the execution principal to the approved project and resources.
5. Obtain cost, quota, recovery, and consistency behavior from current official product documentation or live read-only APIs; do not infer them from examples.
6. Record source URLs, `last_verified`, discovered target behavior, and discrepancies in the operation evidence.

Treat any stale source, undocumented field, unexpected release channel, or target divergence as a stop condition.
