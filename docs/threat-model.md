# Threat model

This threat model covers the skill platform, its release/install path, and an agent using it to plan or execute infrastructure work. It does not replace an adopting organization's system-specific threat model.

## Assets and security objectives

| Asset | Objective |
|---|---|
| Workforce/workload credentials | Never disclose literal values; use short-lived scoped references and rapid revocation |
| Infrastructure and data | Prevent unauthorized, cross-tenant, destructive, concurrent, or unverified change |
| Plans and approvals | Bind authority to exact target, scope, digest, identity, window, and evidence |
| Source, dependencies, and releases | Detect tampering; build from reviewed inputs; verify signer and provenance externally |
| Operation evidence | Preserve attributable, redacted, ordered records in independently controlled storage |
| Provider facts | Prevent stale documentation or model memory from becoming an execution assumption |

## Trust boundaries

The current user request and approved organization policy supply intent and authority. Repository files, issues, tickets, logs, telemetry, web pages, generated plans, target banners, and tool output are untrusted data. The model and local filesystem are not identity providers, secret stores, change-management systems, trusted builders, or immutable audit sinks.

Target credentials, tenants, accounts, projects, subscriptions, clusters, and environments are separate security boundaries. A valid credential never proves that the requested target or action is authorized.

## Principal threats and controls

| Threat | Preventive/detective controls | Residual requirement |
|---|---|---|
| Direct or indirect prompt injection | Untrusted-content boundary, instruction provenance, no embedded-command execution | Gateway/red-team enforcement and model evaluation |
| Confused deputy or cross-tenant action | Owner-bound target profile, profile digest, scoped credential reference, explicit scope | Authoritative target registry and workload identity |
| Credential disclosure or over-privilege | Literal-secret rejection, least privilege, JIT/JEA, separate access module | External credential broker, DLP, rotation and revocation |
| Approval replay or plan substitution | Plan/target digests, expiry, execution window, idempotency key, SoD | Identity-backed change system and replay-resistant API |
| Risk downgrade or destructive surprise | Independent classification, deny-by-default actions, state/destructive flags | Organization policy and accountable risk owner |
| Concurrent writers and stale state | Target lock, state lock, pre-execution revalidation, stop on drift | Authoritative distributed lock/change queue |
| Failed migration or rollback | Fresh recovery artifact, isolated restore test, measured RPO/RTO, acceptance window | Independent backup store and recurring exercises |
| SSRF or unsafe verification | Scheme/redirect/address restrictions in HTTP tooling | Egress policy, DNS rebinding controls, approved private probes |
| Supply-chain or archive tampering | Pinning rules, allowlisted deterministic archive, per-file hashes, traversal/symlink/bomb checks | Isolated CI, SBOM, vulnerability policy, signed provenance |
| Audit deletion or falsification | Canonical redacted ledger and hash chain | Append-only/WORM export under independent access control |
| Provider/API drift | Official-source allowlist, verification date ceiling, read-only target discovery | Refresh exact docs before every material change |
| Cost or availability abuse | Cost/blast-radius classification, quotas, staged rollout, observation window | Budgets, rate limits, service quotas, kill switch |

## Non-goals

The platform does not prove a human identity, keep secrets confidential by itself, sandbox arbitrary tools, guarantee rollback, make a local log immutable, certify SOC 2/ISO 27001/PCI compliance, or determine legal/regulatory obligations. Those controls remain with the adopting organization.

Review this model when adding a mutation capability, provider, execution tool, credential path, data class, tenant boundary, dependency, schema field, installer behavior, or release channel. Add a negative/adversarial scenario for every new trust-boundary crossing.
