# Enterprise adoption gate

Do not call the platform “enterprise approved” solely because this repository validates. Complete organization-specific architecture, security, privacy, legal, procurement, resilience, and operational reviews first.

## Required integrations before production

1. Place source under protected version control with two-party review, signed/attributed changes, CODEOWNERS-equivalent ownership, branch protection, and retained history.
2. Build releases in an isolated protected CI system. Pin dependencies, generate SBOM and signed provenance, scan artifacts, verify expected builder/signer/input policy, and distribute from an approved registry.
3. Connect workforce/workload identity and short-lived credential brokerage. Never give the model raw standing administrator credentials.
4. Connect change management so approvals are identity-backed, plan-digest-bound, expiring, role-separated, and queryable by evidence reference.
5. Store target profiles in an owner-controlled registry and calculate their digest after canonicalization.
6. Export redacted chained ledgers to append-only/WORM storage under independent audit access control and retention policy.
7. Define data residency, tenant isolation, prompt/tool logging, retention, deletion, eDiscovery, privacy, and restricted-data rules.
8. Run adversarial evaluation for direct/indirect prompt injection, confused deputy, SSRF, path traversal, malicious archives, secret leakage, stale approval, replay, concurrency, rollback failure, and compromised dependencies.
9. Exercise recovery, break-glass, credential revocation, kill switch, incident response, and safe degraded mode.
10. Assign accountable owners for policy, module releases, vulnerabilities, exceptions, target onboarding, incident command, and audit evidence.
11. Confirm legal/IP ownership and Apache-2.0 distribution rights, add any required third-party attribution/NOTICE, define support terms, complete export/sanctions review where applicable, and configure a monitored private vulnerability intake.

## Adoption stages

| Stage | Allowed use | Exit evidence |
|---|---|---|
| Sandbox | Synthetic/non-sensitive local targets; no standing credentials | Platform tests, threat model review, package integrity verification |
| Observe | Read-only inventory on bounded non-production targets | Data-flow review, output redaction tests, target ownership, audit export |
| Assist | Draft plans/configs; human executes changes | Independent review, deterministic preflight, rollback rehearsal |
| Controlled staging | R1/R2 execution with short-lived scoped credentials | Identity-backed approvals, change locks, replay tests, incident exercise |
| Limited production | Selected R3 runbooks and targets | Two-party approval, signed release/provenance, immutable audit, restore proof, SLOs |
| Broad production | Approved capability/target matrix only | External assessment, continuous control monitoring, periodic recertification |

## Non-negotiable rejection criteria

Reject production adoption if legal use/distribution rights are undefined, the deployment uses shared administrator credentials, cannot bind approval to an immutable plan, lacks an independent recovery test, allows untrusted content to select tools or credentials, cannot revoke access quickly, cannot attribute actions, or cannot export evidence independently of the agent.
