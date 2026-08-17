---
name: cloud-generic
description: Assess, bound, and route cloud operations without assuming a provider implementation. Use for unfamiliar or unsupported clouds, multi-cloud intake, provider identification, read-only scope inventory, contract-v2 change planning, and explicit handoff when no installed provider pack safely owns the requested mutation.
---

# Generic Cloud Operations

Operate as a provider-agnostic discovery and planning executor. Never translate a generic intent into a provider mutation from memory.

Read `../devops-core/references/untrusted-content-boundary.md`, `../devops-core/references/control-plane-ownership.md`, `../devops-platform-contracts/references/provider-freshness.md`, and `references/provider-boundary.md` before relying on target output or provider documentation.

## Scope

- Identify the provider, control plane, tenancy hierarchy, region or zone, resource ownership, billing boundary, and credential reference using read-only evidence.
- Inventory account or project structure, IAM posture, network boundaries, compute, managed containers, managed databases, quotas, and observable cost signals without retrieving payload data or secret values.
- Normalize a provider-neutral desired state and acceptance criteria.
- Route to the smallest installed provider and specialist modules that cover the operation.
- Refuse every provider mutation that lacks an installed executor with current official sources and an exact supported operation.

Do not guess product names, endpoints, API versions, CLI syntax, defaults, IAM roles, prices, quotas, or recovery behavior. Do not treat console access, broad credentials, or a successful listing call as authority to change state.

## Workflow

1. Receive a secret-free contract-v2 operation request from `devops-core`. Confirm operation ID, owner, environment, data classification, target fingerprint, objective, constraints, and acceptance criteria.
2. Establish the identity and scope through read-only discovery. Record tool identity, timestamp, target identifiers, provider or control-plane version, provenance, and redactions. Stop if the provider, owner, billing boundary, or production identity remains ambiguous.
3. Check current official provider documentation and record its URLs with `last_verified`. Treat missing, stale, preview-only, or conflicting documentation as uncertainty, not permission.
4. Map the request to capabilities and ownership. Identify infrastructure-as-code ownership before proposing a direct change.
5. Classify risk with `devops-core`. Describe cost delta, quota impact, blast radius, dependencies, recovery prerequisites, and independent verification.
6. Produce an immutable, secret-free plan and SHA-256 plan digest. For R2-R4, require the matching target fingerprint, approval evidence, execution identity, change lock when required, and a passing contract-v2 operation gate.
7. Do not execute the mutation. Hand off the exact plan, digest, confirmed facts, unknowns, risk, recovery evidence, verification criteria, and required capability to an installed provider or specialist module.
8. Report `blocked` when no safe executor exists. Never downgrade risk or broaden scope to avoid a handoff.

## Handoffs

- Route provider-native account, IAM, regional, compute, and managed-service control-plane work to the matching installed cloud provider pack.
- Route declarative or state-managed resources to `iac-operations`.
- Route Kubernetes cluster or workload changes to `kubernetes-operations`.
- Route database payload, migration, backup, restore, or destructive data work to `data-resilience-operations`.
- Route multi-site, transit, peering, routing-domain, or enterprise firewall work to `enterprise-networking`; route public DNS, TLS, ingress, and edge exposure to `network-edge-operations`.
- Route secret retrieval, rotation, credential lifecycle, or privileged-access workflow to `secrets-access-operations`.

## Output

Return confirmed facts, discovery provenance, provider confidence, selected capabilities, decision, risk, cost and blast-radius notes, plan digest when planned, recovery and verification requirements, final status, and explicit handoffs. Use only `verified`, `partially_verified`, `rolled_back`, or `blocked` as the final status.
