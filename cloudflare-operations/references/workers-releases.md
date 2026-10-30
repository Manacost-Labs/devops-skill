# Workers upload, deployment and compatibility recovery

## Separate versioned and external state

Bind account, script/environment name, source commit and bundle digest, tool version, compatibility date/flags, immutable version ID, active deployment ID and percentage split. Inventory routes/custom domains/workers.dev, triggers, bindings, secret references, service-binding consumers and external effects. Keep a source-of-truth owner for each setting; a version does not cover all routes/triggers or external resources.

A version holds code/configuration, including its bindings and compatibility settings. KV, R2, D1, Durable Objects and external services remain mutable state with their own recovery. Confirm both old and new code can read/write the actual data during overlap. An old binding to a deleted resource, a secret lifecycle change or Durable Object migration/class lifecycle can prevent safe rollback. Never assume deploying former code restores storage, reverses a migration or recalls queue messages/payments/emails.

## Upload then deliberately promote

Use the current supported versions/deployments workflow. Review the exact upload behavior for secrets, bindings and migrations; a preview must not call production data or consumers. Upload a version separately from production deployment where supported, capture its immutable ID and verify its bundle/configuration identity. Preview/version URL controls and availability must be confirmed for the account; do not expose sensitive version URLs or assume previews have production Access/WAF behavior.

Before promotion, re-read the active deployment and split, target version metadata, relevant routes/settings and external-state compatibility evidence. An unexpected deployment ID, binding/configuration change or concurrent dashboard/build/IaC deploy invalidates the candidate. Serialize deployers; a client-side digest check is not server-side CAS. Pin percentages and exact version IDs in each staged plan.

Use a bounded supported gradual deployment with per-version error/latency and application acceptance, a sufficient observation window and explicit stop criteria. Requests may reach different versions: a browser session is not automatically pinned. Check version-affinity requirements and service-binding version skew. Durable Objects have specific gradual-deployment behavior and migration constraints; do not apply an ordinary stateless percentage plan to them without their documented procedure and owner.

## Partial release and rollback

Version upload, deployment creation, route/domain update, trigger update and external migrations are separately recorded effects. A lost deployment response requires re-reading actual deployment history and the active split before any retry. Record returned deployment/version IDs and verify traffic by version rather than assuming a successful CLI output describes all edge locations or all requests. An unused uploaded version is not proof of a production change and does not require blindly deleting it.

If new code failed before incompatible external effects, choose a compatible recovery with the owner. A documented rollback creates a new deployment sending 100% of traffic to the chosen prior version; it does not resurrect the previous deployment ID or former arbitrary split. To restore a former multi-version split, create a separately reviewed deployment with those exact IDs/percentages. Reconcile routes/triggers separately.

If writes/migrations are incompatible, stop promotion, control affected writers through their owners and prefer a compatible forward repair or isolated data recovery with newest-write/external-effect reconciliation. Do not force an old version onto incompatible current data. Re-read the current deployment immediately before compensation and refuse to overwrite another deployer's release. Verify the recovered deployment ID/split, permitted traffic and external data with the agreed window; report unknown locations, absent traffic or missing data evidence as `partially_verified`.

Official behavior: [versions and deployments](https://developers.cloudflare.com/workers/versions-and-deployments/), [gradual deployments](https://developers.cloudflare.com/workers/versions-and-deployments/gradual-deployments/), [rollbacks](https://developers.cloudflare.com/workers/versions-and-deployments/rollbacks/), [deployment API](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/deployments/).
