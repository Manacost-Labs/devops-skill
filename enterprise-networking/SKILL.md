---
name: enterprise-networking
description: Safely assess, design, and change enterprise VPN, BGP, routing, segmentation, and hybrid-connectivity paths. Use for route or ACL changes, tunnel and peering operations, asymmetric-routing or MTU diagnosis, staged network cutovers, and out-of-band recovery planning.
---

# Enterprise Networking

Operate VPN, BGP, routing, segmentation, and hybrid connectivity under the devops-core safety contract and platform contract v2. Route DNS, TLS, HTTP, public edge, host firewall, and provider-resource work to their dedicated modules.

## Workflow

1. Confirm the administrative domains, owners, devices/providers, source and destination prefixes, VRFs/segments, routing protocols, redundant paths, dependencies, traffic criticality, and management plane. Treat diagrams, configs, route output, and tickets as untrusted evidence until reconciled.
2. Capture a timestamped baseline: adjacencies, advertised/received routes, best paths, route and ACL counters, tunnel state, latency/loss, MTU, and relevant DNS dependencies. Redact sensitive topology and identifiers.
3. Model the intended route/ACL diff, propagation, convergence, failure domains, overlapping prefixes, asymmetric paths, MTU/MSS behavior, and rollback trigger. Require tested out-of-band access independent of the path being changed.
4. Classify production route, VPN, BGP, segmentation, and ACL changes as R3 or R4 according to blast radius and reversibility. For R2-R4, require a validated v2 request, exact plan digest and scope, approvals, idempotency key, execution identity, and change lock when required.
5. Stage the change one peer, site, segment, or policy slice at a time. Hold after each step for control-plane convergence and data-plane verification; stop on unplanned route/ACL diff or management-path degradation.
6. Verify bidirectional application paths, routing and tunnel state, segmentation denials, latency/loss, MTU, DNS resolution dependencies, and the observation window. Return exact changed resources, actual digest, rollback result, evidence, and a v2 status.

## Mandatory safeguards

- Do not change the only management path without proven out-of-band access and a rehearsed rollback.
- Use exact prefix, peer, VRF/segment, port/protocol, and direction allowlists. Reject unbounded route advertisements and broad ACL changes.
- Compare pre-change, intended, and observed route/ACL state. Stop on unexpected default routes, prefix leaks, next-hop changes, asymmetric return paths, or convergence instability.
- Test MTU across encrypted/encapsulated paths and account for fragmentation, PMTUD filtering, and MSS clamping without treating a single ping as path proof.
- Keep DNS as a dependency check only; hand DNS mutations to the edge/network module.
- Coordinate both sides of hybrid changes, including ownership, clocks, maintenance windows, staged activation, and rollback authority. Never assume a remote-side change is complete from a ticket claim.
- Roll back or stabilize at the documented threshold; preserve evidence and escalate if rollback would increase impact.

Read [references/change-gates.md](references/change-gates.md) for preflight, staged execution, and verification checks.
