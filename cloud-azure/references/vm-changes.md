# One ARM VM create or update

Use for one VM resource and separately journaled dependencies. Confirm active cloud, tenant/subscription, group, location/zone, exact VM ARM ID, image version, size/SKU restrictions, disk/encryption settings, existing NIC/subnet/NSG IDs and managed identity. Resolve defaults into the reviewed writable request. `az vm create` can bundle other resources; do not use it as an unexamined single-effect shortcut. Existing scale sets, Bicep/ARM/Terraform or controllers retain ownership.

## Preflight and exact write

Check total regional vCPU and VM-family quotas, regional VM count, NIC/IP/subnet and managed-disk headroom, including overlapping replacements. Allocated and deallocated VMs can consume vCPU quota. Quota entitlement is separate from regional/zonal SKU capacity. Allocation failure is not fixed by blindly repeating a quota check or moving zones; another size, zone or region changes the approved target, cost and dependencies.

For Compute API `2025-04-01`, `PUT {vm-arm-id}?api-version=2025-04-01` documents `If-None-Match: *` for create-only and `If-Match` with the last observed ETag for guarded updates. Confirm the chosen cloud/API supports these exact headers; do not assume every ARM API does. GET an existing VM, retain ETag, `properties.vmId` and before-state. Build the intended writable body from the reviewed API schema, preserving unrelated settings; do not send raw GET read-only fields back as a request. Some properties are create-only. A precondition conflict requires a fresh read and plan, never an unconditional overwrite.

Before dispatch, persist exact method/URI/API version, body/header digest, VM identity or proven before-absence, request correlation IDs, dependency IDs/delete options, deadline and recovery boundaries. A client request ID helps correlation; it is not a provider-wide replay token. Keep the same intended ARM identity during reconciliation and do not infer that a PUT is safe to repeat solely from its HTTP method.

## Uncertain results and partial dependencies

Retain the returned async tracking headers and use [bounded observation](async-recovery.md). After terminal success, GET the VM and compare `vmId`, location/zone and the complete approved configuration. Provisioning state, instance-view runtime state and application acceptance are different observations. A reused ARM name with a different `vmId` is another incarnation; stop instead of adopting or deleting it.

After a lost response, inspect the saved tracking operation if available, exact VM GET and activity evidence. A missing VM does not prove no NIC, disk, IP or role-assignment effect occurred. Do not issue an unconditional PUT, change identity, or delete candidates based on names/tags. Keep the original uncertain operation and reconcile the dependency graph before any separately admitted retry or repair.

A failed VM operation can leave billable resources. Journal preexisting versus created NICs, managed disks, public IPs, associations and roles separately. Recovery must check each current object and attachment, data retention and `deleteOption`. VM deletion can detach or delete associated resources depending on those settings; never assume it cleans everything or preserves every disk. Stop destructive recovery on data/ownership ambiguity or concurrent changes. Verify retained service/data and intended resource absence after compensation.

## Optional offline inspection

`python cloud-azure/scripts/inspect-vm-operation.py --checklist checklist.json --capture capture.json` reads local JSON only. It handles saved **public Azure** `Azure-AsyncOperation` status responses plus an independent VM GET; it does not parse `Location` polling, perform synchronous completion inference, or query sovereign clouds. Those cases require their documented observation path.

The checklist contains exactly `cloud`, `tenant_id`, `subscription_id`, `resource_id`, `vm_id`, `location`, `operation_url`. The capture contains exactly those first three scope fields plus `operation_url`, `poll_http_status`, `poll_body`, `resource_http_status`, `resource_body`. Bodies are unmodified native JSON; a missing capture uses null status/body. Scope and the retained `vm_id` must come from independently established caller/endpoint and incarnation evidence, not a convenient final snapshot. `vm_id` cannot be inferred before a new VM's identity has been established.

The helper checks a narrow observation subset and emits `pending`, `failed`, `poll_unavailable`, `resource_unobserved`, `resource_pending` or `control_plane_match`. None proves authority, ownership, every planned setting or health. Exit 0 means only the retained LRO and VM subset match; exit 2 is unresolved/failed observation; exit 1 rejects evidence. Preserve timestamps, provenance and artifact digests outside the helper.

Sources checked 2026-10-30: [VM create/update](https://learn.microsoft.com/en-us/rest/api/compute/virtual-machines/create-or-update?view=rest-compute-2025-04-01), [VM GET and vmId](https://learn.microsoft.com/en-us/rest/api/compute/virtual-machines/get?view=rest-compute-2025-04-01), [quotas and capacity](https://learn.microsoft.com/en-us/azure/virtual-machines/quotas), [VM/dependency deletion](https://learn.microsoft.com/en-us/azure/virtual-machines/delete).
