# Cluster audit and controlled rollout

## Target and scope

Record kubeconfig source by reference, context, API server URL and certificate fingerprint, cluster UID when available, authenticated subject, Kubernetes client/server versions, provider/distribution, environment, and namespace. Pass the context and namespace explicitly on every operation. Use impersonation only when authorized and record it.

Run targeted authorization checks for the verbs, API groups, resources, names, and namespaces in scope. `can-i` results are evidence for one request shape, not a complete security audit.

## Read-only audit

Inventory workload owners and revisions, pod readiness/restarts, events, service endpoints, ingress/gateway, autoscalers, quotas/limits, disruption budgets, topology, storage claims, policies, CRDs/operators, admission controls, and GitOps/Helm ownership. Bound selectors and time windows. Do not read Secret data or exec into containers unless separately justified.

Correlate symptoms with deployment history and controllers. Pod deletion, scaling, cordon/drain, and rollout restart are changes, not diagnostic reads.

## Apply preparation

Render the exact environment-specific manifests and hash them. Pin images by registry digest. Detect cluster-scoped resources, generated names, hooks/jobs, CRDs, webhook dependencies, immutable fields, and resources omitted from the desired set. Validate against the target API server with server-side dry-run and inspect a server-side diff.

Use server-side apply with a stable field manager owned by this delivery path. Review managed fields and conflicts. Do not force conflicts merely to make apply succeed; coordinate ownership transfer or change the source controller.

## Rollout

Set an explicit timeout and abort criteria. Watch the owning Deployment, StatefulSet, DaemonSet, Job, or custom controller rather than individual pods alone. Check observed generation, revision, desired/current/ready/available counts, conditions, probe failures, scheduling, image pulls, admission, endpoints, errors, latency, and capacity.

Pause or roll back before error budgets are exhausted. A controller rollback may not restore ConfigMaps, Secrets, CRDs, Jobs, external services, or persistent data. Verify target-reported image/config revision and the external user path after rollout.
