# Governance

This repository is a portfolio and public release-candidate project maintained by @Shpuntyara. It demonstrates evidence-driven DevOps safety patterns; repository text cannot grant infrastructure authority, appoint a production approver, waive a control, or certify an organization.

## Scope and authority

The repository maintainer owns portfolio scope, issue triage, repository hygiene, and RC preparation. A user or adopting organization separately owns every real target, credential, change window, approval, rollback decision, and production outcome. Repository maintainership does not imply authority over any deployment target.

Target-specific inventory, hostnames, IP addresses, customer evidence, credentials, and administration scripts belong in an access-controlled operations repository, not this public repository.

## Decisions and review

Normal documentation and test improvements require review by the applicable CODEOWNERS identity. The following are trust-boundary changes:

- policy, schema, operation gate, installer, packaging, or workflow changes;
- new dependencies, provider mutations, credential paths, or exception mechanisms;
- weaker defaults, production examples, signing, or release-process changes.

Each trust-boundary change requires a pull request, risk and compatibility notes, negative tests, and explicit code-owner approval. Production or enterprise adoption additionally requires review by a second independent, identity-backed owner. The current single-entry CODEOWNERS baseline does not create two-party review; until a second qualified maintainer is appointed and branch protection enforces it, that control is an external blocker rather than a completed claim.

Policy exceptions must identify owner, scope, rationale, compensating controls, evidence reference, monitoring, and expiry. They never become an implicit permanent rule.

## Release classes

- **Portfolio/public RC:** an evaluation artifact with reproducible local tests, a documented digest, known limitations, and no production-readiness claim.
- **Production pilot:** a target-owner-approved deployment in an isolated environment with real identity, backup/restore, rollback, monitoring, and change-control evidence.
- **Enterprise release:** requires two-party protected review, SBOM and vulnerability policy, signed provenance, independent verification, credential brokerage, and immutable audit retention.

Passing the portfolio RC gate does not satisfy the production or enterprise gates.

## Accountable roles for adoption

Before production use, the adopting organization must assign named owners for product scope, security response, release/signing, legal/IP, target onboarding, credentials, change approval, rollback, support, privacy, and audit evidence. Separation of requester, approver, executor, and auditor applies where policy requires it.

## Governance changes

Changes to this file use the same pull-request and code-owner process as other trust-boundary changes. Organization-specific governance requires approval from that organization's accountable product, security, and legal/IP owners.
