# One NSG rule in an existing VNet path

Bind cloud, tenant/subscription, resource group, VNet/subnet/NIC IDs, NSG ID and rule name. Inventory every subnet/NIC associated with the group, effective security rules, route tables, service/application security groups, public IPs and relevant policy/locks. Subnet and NIC filtering both matter. Route topology, VPN, peering and enterprise segmentation changes to `enterprise-networking`; public-path acceptance joins `network-edge-operations`.

## Request and concurrency boundary

For Network API `2026-01-01`, the exact child resource is `{nsg-id}/securityRules/{rule-name}`. GET it and retain before-state, presence, returned ETag and the full intended writable rule tuple. Plan a `PUT` with explicit `properties.access`, `direction`, `priority`, `protocol`, source/destination address or application-group selectors and port selectors. Distinguish singular/plural fields and reject a broadened wildcard as an incidental fix. Check unique priority/direction and live NSG/rule limits, including temporary transition rules. The numeric priority range in this API is 100–4096; lower values are evaluated first.

This operation's published request parameters do not document `If-Match` or `If-None-Match`. A returned ETag is not proof a conditional write is supported. Do not transfer VM API concurrency headers to NSG rules or replace the parent NSG from a stale GET. Establish writer exclusion with the owning controller/operator, keep one group mutation in flight and re-read before each step. If competing writers cannot be excluded or before-state drifts, stop instead of claiming a race-free change.

Choose replacement ordering explicitly. Adding an allow before removing another can temporarily increase exposure; removing first can interrupt the intended path. If neither transient state is acceptable, obtain a staged design and separately bound plan. Do not silently change associations, route tables or public endpoints to make the rule work.

## Observe, recover and prove the path

A create/update can return an async header. Apply [the exact observation protocol](async-recovery.md) and then GET the child rule, comparing every intended field and its provisioning result. Following a lost response, read the retained rule identity and reconcile current tuple, request/activity evidence and before-state. Matching contents do not establish ownership. A temporary absence, timeout or failed poll does not authorize another PUT or a new rule name.

If a later step fails, stop new writes and inventory each actual effect. Restore only this operation's changed rule when its current tuple still equals the expected post-state and the restore remains authorized. Delete only a rule proven created by this operation; the delete API can return `202` with `Location`/`Retry-After`, requiring its own completion interpretation and final absence check. Preserve an unrelated writer's changes.

Check the effective permitted and denied paths with **new connections** from the intended sources. NSG flow tracking can retain existing sessions after a rule removal, so a surviving SSH connection does not prove new access remains allowed. Confirm host firewall, routing and application behavior separately; a converged ARM object alone is incomplete acceptance.

Sources checked 2026-10-30: [rule create/update](https://learn.microsoft.com/en-us/rest/api/virtualnetwork/security-rules/create-or-update?view=rest-virtualnetwork-2026-01-01), [get](https://learn.microsoft.com/en-us/rest/api/virtualnetwork/security-rules/get?view=rest-virtualnetwork-2026-01-01), [delete](https://learn.microsoft.com/en-us/rest/api/virtualnetwork/security-rules/delete?view=rest-virtualnetwork-2026-01-01), [NSG evaluation and flow tracking](https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview). Refresh operation permissions, supported cloud API and current limits before execution.
