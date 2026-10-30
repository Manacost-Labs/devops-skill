# Bounded Compute Engine instance changes

Operate one VM in an exact project and zone. Confirm project number, instance name/numeric ID for an existing VM, network/subnetwork project and region, machine type, immutable boot image, disk IDs/encryption/auto-delete settings, service account/scopes, tags, metadata, external-IP behavior and deletion protection. Resolve image families/templates to reviewed immutable versions. Managed instance groups and declarative ownership route to their controllers.

## Insert and network-tag update

For one create, use Compute v1 `POST /compute/v1/projects/{project}/zones/{zone}/instances` (`instances.insert`) with explicit name and configuration. Check method-specific permissions, service-account use, image access and Shared VPC permissions; do not grant broad project roles to make launch pass. Persist a nonzero UUID `requestId`, canonical input digest, project/zone, before-state, deadline and dependency inventory before dispatch.

For existing network tags, first GET the exact numeric instance incarnation and retain `tags.items` and `tags.fingerprint`. `instances.setTags` takes the **complete intended tag list** with that fresh fingerprint; changing tags can change firewall exposure. Retain unrelated tags. A fingerprint-precondition failure requires a fresh GET and recomputed reviewed delta, not removing the fingerprint. Serialize writers and stop if the instance ID or material fields changed. An optional `requestId` deduplicates a request; it does not replace the fingerprint concurrency check.

The acknowledgement is a zonal Operation. Retain its name/numeric `id`, `selfLink`, `zone`, `targetLink`, `targetId` and `clientOperationId` (the supplied UUID). Follow the same zone's operation resource; a global or regional operation is a different identity. `DONE` can contain errors: inspect `error.errors` and HTTP error fields, then GET the instance and compare its numeric `id` to the operation's target incarnation, desired configuration and runtime state. A VM named identically in another zone, or a recreated VM with a new ID, is not the original effect.

Read live regional CPU-family, disk/storage, address and relevant per-project quotas; include temporary replacement resources, subnet addresses, and API/concurrent-operation consumption. Quota availability does not reserve zonal machine capacity. Capacity exhaustion is different from quota exhaustion or request throttling. Changing zone, type, network, image or purchasing mode requires a changed scope/cost plan, not an automatic retry.

## Lost response and recovery

After an uncertain insert, do not allocate a new UUID or instance name. Reconcile exact project/zone operation records using retained `clientOperationId`, target URL, actor/time evidence and request digest, following all pages. Independently GET the intended instance. A name match is not ownership proof; no match at one instant or an expired operation record is not proof that nothing happened. Only the exact unchanged request with the retained UUID may be considered for a documented same-request retry under still-valid authority; changed parameters or unresolved ownership stop execution.

If tag update response is lost, inspect current numeric ID, tag list and fingerprint. Reconcile whether the approved delta took effect before another write. A recovery tag update uses the newest fingerprint and preserves concurrent unrelated changes; a stale full-list replay can remove someone else's tags.

Journal disks, addresses, IAM changes, firewall rules and VM creation separately. A failed later step can leave chargeable disks/IPs or an existing healthy VM. Stop and enumerate actual effects, including disk auto-delete/attachment and current writers. Compensate only attributable owned effects in safe dependency order, with authorized data retention and current-state checks. Never delete a candidate solely by name/label, attached preexisting disk, or a whole project as cleanup. Verify each cleanup and its billing/resource evidence; response loss during cleanup is another uncertain effect.

## Optional saved-evidence inspection

`python cloud-gcp/scripts/inspect-operation.py --checklist checklist.json --capture capture.json` checks an already identified **zonal instance-insert** operation and separate saved instance GET. It does not discover a missing operation, inspect setTags/global firewall operations, verify every VM field or authenticate captures.

The checklist has exactly `project`, `zone`, `operation_name`, `operation_id`, `request_id`, `instance_name`, `target_id`: retain all from the original request/identified operation, not from an unrelated current resource. Capture has exactly `operation` (native Operation object) and `instance` (native instance GET or `null` when no independent resource observation is available). Preserve provenance, times, API version and artifact digests separately. Missing native correlation fields are rejected conservatively.

Outputs are `pending`, `failed`, `resource_unobserved`, `resource_not_running` or `control_plane_match`. Exit 0 means only a correlated, error-free DONE plus the same running instance incarnation; exit 2 means another observation, exit 1 rejected evidence. All outputs keep retry permission, full-plan and service-health verification false. Independent configuration/access/network/guest checks and the application observation window remain required.

Sources checked 2026-10-30: [instances.insert](https://cloud.google.com/compute/docs/reference/rest/v1/instances/insert), [instances.setTags](https://docs.cloud.google.com/compute/docs/reference/rest/v1/instances/setTags), [zonal Operation identity](https://cloud.google.com/compute/docs/reference/rest/v1/zoneOperations), [operation polling](https://cloud.google.com/compute/docs/api/how-tos/api-requests-responses), [allocation quotas](https://cloud.google.com/compute/resource-usage). Refresh exact permissions, versions and target behavior before execution.
