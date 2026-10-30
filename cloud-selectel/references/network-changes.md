# One security-group rule or port assignment

Bind account, project UUID, pool, Neutron endpoint, group/rule/port UUIDs, subnet/network and affected server UUIDs. Verify the endpoint's supported API/extensions and current ownership; Terraform/controllers own their resources. A security group acts on ports within one pool, while a router firewall has a different traffic path. Transit/routing design goes to `enterprise-networking`.

## Selectel preconditions

Confirm effective port security, all groups on each affected port and the resulting union of allowed traffic. Selectel's `default` group permits incoming and outgoing traffic for allowed port addresses, cannot be deleted, and is not a default deny-ingress boundary. Do not modify it when Managed Kubernetes uses the same project/pool: the provider warns of cluster failure. A newly created group also has initial egress rules; inventory actual rules before interpreting its exposure. Changing port security is a separate security change, not a way to make a group update succeed.

## Exact bounded operations

Use Neutron v2.0 through the confirmed network service endpoint, not deprecated Nova security-group proxy methods. Read the exact rule/group/port and complete related lists, including pagination. Retain project ownership, rule tuple, port `security_groups`, `port_security_enabled`, device relationship and revision information where exposed.

- Add one rule with `POST /v2.0/security-group-rules` and one `security_group_rule` object containing the reviewed `security_group_id`, `direction`, `ethertype`, `protocol`, port range and either the explicit remote CIDR or remote group. Pin all exposure-relevant defaults. Retain the returned rule UUID and re-read it. An omitted source/protocol can broaden access.
- Remove one rule with `DELETE /v2.0/security-group-rules/{rule_id}` only after comparing its current full tuple and project. Re-read absence and test the intended paths; an acknowledgement is not enforcement evidence.
- For an existing port, `PUT /v2.0/ports/{port_id}` with a reviewed complete `security_groups` list changes its assignments. Preserve unrelated groups and port-security settings. Verify current endpoint/client semantics before translating this into CLI flags; an append-like flag is not proof that the intended complete set was applied.

Keep one in-flight mutation for the group/port, compare immediately before each step, and stop on drift. Do not assume an `If-Match`, revision precondition or client retry token is supported merely because a newer upstream API describes it. Use a concurrency precondition only after the actual Selectel endpoint and exact method confirm it; otherwise the remaining external-writer race requires coordinated ownership.

## Ordering, lost responses and acceptance

Choose add-before-remove only with accepted temporary exposure and quota headroom; remove-before-add needs accepted interruption and a preserved management path. Selectel explicitly warns that removing a rule or changing a port's group assignments can interrupt existing sessions. Do not borrow another provider's connection-tracking promise. Budget current and transitional group/rule consumption from fresh provider limits and quotas.

On lost create response, enumerate all exact normalized candidates in the same project/pool and use request/audit evidence to identify ownership. Names, descriptions and an identical tuple alone do not authorize replay or cleanup. Reconcile lost deletes by UUID and lost port updates by the whole current assignment set. Duplicates or ambiguous ownership stop writes. A second-step failure requires actual-state inventory; undo only a proven owned effect still in its expected post-state, preserving preexisting rules and another writer's groups.

Independently re-read rule/port state, then test fresh allowed and authorized denied connections from the intended vantage points. Inspect route/guest firewall, provider-blocked ports and service health separately. Control-plane equality alone is partial verification.

Sources checked 2026-10-30: [Selectel SG semantics](https://docs.selectel.ru/en/cloud-servers/security-groups/about/about-security-groups/), [create rule](https://docs.selectel.ru/en/cloud-servers/security-groups/manage-rules/create-rule/), [delete rule/session warning](https://docs.selectel.ru/en/cloud-servers/security-groups/manage-rules/delete-rule/), [port assignment](https://docs.selectel.ru/en/cloud-servers/security-groups/manage-groups/assign-security-groups/), [network/port security](https://docs.selectel.ru/en/cloud-servers/cloud-networks/about-networks/), [supported components and upstream links](https://docs.selectel.ru/en/cloud-servers/tools/openstack-cli/about-openstack-cli/), [Neutron methods](https://docs.openstack.org/api-ref/network/v2/). Upstream fields/extensions remain conditional on actual endpoint support.
