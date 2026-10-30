# One classic VPC firewall rule

Use for a Compute v1 `firewalls.insert` or `firewalls.patch` in one confirmed project and VPC. These are project-global resources, although their targets include zonal VMs. Shared VPC, hierarchical/network firewall policies, routing, peering or organization-wide policy need the owning specialist and separate operations.

Read the exact rule with `firewalls.get`, its numeric `id`, network URL, direction, priority, disabled/logging settings, source/destination ranges, target tags/service accounts and protocol/ports. Inventory affected instances and applicable higher-level policies. Bind the full before-state and desired-state digests; rule names, descriptions and tags do not establish ownership.

## Mutation and ordering

For create, use `POST /compute/v1/projects/{project}/global/firewalls` with a complete reviewed rule. For a supported change, use `PATCH .../global/firewalls/{firewall}` with only the reviewed fields, accounting for the documented replacement semantics of supplied arrays. Pin direction, network and target semantics; never let omitted defaults broaden exposure.

Both exact methods document a `requestId`; persist a nonzero UUID, exact request digest and project-global scope before dispatch. The same ID must never be reused for different input or another scope. Classic firewall PATCH has **no `fingerprint` field or documented expected-before-state CAS**. Do not borrow fingerprints from instance tags/metadata or another firewall API. Serialize one mutation per rule, re-read immediately before dispatch and stop on drift; external writers can still race.

Retain the returned global operation name, numeric operation ID, `targetLink`, `targetId` and `clientOperationId`. Observe through `globalOperations.get`/`wait`, check terminal errors and independently re-read the exact firewall numeric ID and every changed field. See [async recovery](async-recovery.md). An HTTP acknowledgement or `DONE` alone does not prove the intended rule is enforced.

Choose add-before-remove only when the temporary union of permissions is explicitly acceptable. Choose remove-before-add only with accepted outage and a verified management path. Plan quotas for both transition states, including current project firewall-rule consumption, API rate limits and dependent target changes. A quota increase or change of project/network is a new operation.

## Lost response and partial effects

Reconcile a lost insert response with the retained request ID, bounded complete operation discovery and exact rule GET. An existing matching name/tuple is a candidate; require request/audit evidence and numeric incarnation identity before taking ownership. A conflict does not authorize deleting the existing rule or choosing a new name. A transient missing rule or expired operation record does not prove the write failed.

For a lost patch response, compare current numeric ID and full desired/before-state. Do not replay a patch with stale list values over a concurrent writer. An exact same-ID retry is considered only under the method's documented deduplication behavior, unchanged input/scope and still-valid authority; it is never a generic recovery step.

After partial rollout, inventory each actual effect and stop new changes. Compensate only owned fields/resources still in the expected post-state. Never replace the whole network policy from a snapshot or delete a preexisting rule. Reconcile the compensation itself if its response is lost.

Verify a new permitted connection and an authorized denied-path probe from the intended source and target. Existing tracked connections can outlive rule changes. Check routes, higher-level policies, guest firewall and service health independently; stored rule equality alone is partial verification.

Sources checked 2026-10-30: [firewalls.insert](https://docs.cloud.google.com/compute/docs/reference/rest/v1/firewalls/insert), [firewalls.patch](https://cloud.google.com/compute/docs/reference/rest/v1/firewalls/patch), [VPC rule behavior](https://cloud.google.com/vpc/docs/firewalls), [VPC quotas](https://cloud.google.com/vpc/docs/quota), [operation handling](https://cloud.google.com/compute/docs/api/how-tos/api-requests-responses).
