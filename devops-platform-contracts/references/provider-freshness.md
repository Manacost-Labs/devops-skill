# Provider knowledge freshness

Provider modules must declare this machine-readable manifest block:

```yaml
source_freshness:
  last_verified: 'YYYY-MM-DD'
  refresh_before_change: true
  official_sources:
    - https://official-provider.example/docs/
  capability_sources:
    bounded-provider-capability:
      - https://official-provider.example/docs/
```

The platform validator rejects a missing block, non-official host, future date, verification older than 183 days, or a capability without a mapped declared source for registered provider and Kubernetes packs. Capability mapping makes coverage reviewable; it does not prove semantic correctness. This release-time check is only a ceiling: every material provider change must still refresh the exact operation page immediately before planning execution.

Name the provider/API/CLI version when relevant. Treat behavior as uncertain when the installed CLI or API differs, the account lacks an expected capability, the documentation has changed, or the request relies on a preview feature. Run read-only discovery against the actual account/project. Do not manufacture command flags, IAM roles, quotas, resource defaults, pricing, or API behavior from memory. Record source URLs, retrieval time, discovered version, and confirmed facts in the operation ledger.
