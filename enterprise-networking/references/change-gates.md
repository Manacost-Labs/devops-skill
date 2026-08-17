# Enterprise network change gates

## Preflight evidence

- Confirm owners and access on both sides, exact topology and administrative boundaries, synchronized time, maintenance window, and communication path.
- Capture route tables, BGP/VPN neighbors, tunnel selectors, ACLs, counters, health signals, configuration revision, and external path tests.
- Produce a semantic route/ACL diff: added and removed prefixes/rules, ordering, direction, next hop, preference/metric, communities, timers, and propagation boundary.
- Prove out-of-band access and snapshot/export the reversible configuration using approved controls.
- Check overlap, summarization, redistribution, default routes, route limits, graceful restart, asymmetric return paths, NAT, MTU/overhead, PMTUD, and DNS dependencies.

## Staging sequence

1. Acquire the target-scoped lock and recheck plan/config digests.
2. Apply the smallest canary peer, site, prefix, or segment.
3. Wait for stable convergence; compare observed routes and ACLs to the allowlisted diff.
4. Verify bidirectional control-plane and data-plane behavior plus expected denials.
5. Continue one bounded stage at a time or invoke the predeclared rollback/stabilization action.

## Stop and rollback triggers

Stop on loss of management/OOB access, route leak, unexpected default/next hop, adjacency flap, convergence timeout, asymmetric loss, MTU regression, broad exposure, or unexplained service degradation. If rollback is unsafe, freeze further changes, isolate the affected scope, preserve evidence, and hand off to the incident owner.

Completion evidence includes actual configuration digest, exact changed peers/prefixes/rules, route/ACL diff, convergence timestamps, application path tests, negative segmentation tests, health observation, and rollback status.
