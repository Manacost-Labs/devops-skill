# Provider-neutral boundary

last_verified: 2026-08-17

Read the platform `provider-freshness.md` rule before using this reference. This module intentionally defines no provider commands or APIs.

## Evidence required for routing

| Area | Confirm read-only | Required handoff |
| --- | --- | --- |
| Identity | Provider, principal, tenant or account, credential reference | Matching cloud provider pack |
| Scope | Organization hierarchy, project or subscription, region or zone, owner | Provider pack or `devops-core` when ambiguous |
| Desired change | Exact resource IDs, current state, desired state, dependencies | Owning provider or specialist module |
| Cost | Billing boundary, metering dimensions, quota headroom, estimated delta source | Provider pack with current official pricing source |
| Recovery | Provider-supported rollback or replacement path and preserved state | Provider pack plus `data-resilience-operations` for stateful data |
| Verification | Independent control-plane read and user-visible acceptance check | Executing module and `reliability-operations` when service health is involved |

## Provider source record

Before planning a provider call, record:

- provider and product;
- official documentation URL;
- documented API or CLI version, release channel, and feature status when relevant;
- `last_verified` date and verifier;
- actual target capability discovered read-only;
- any divergence between documentation and the target.

If an official source or supported executor cannot be established, return `blocked`. Do not substitute community examples, generated commands, or a similar provider's behavior.
