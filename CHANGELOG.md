# Changelog

All notable platform changes are recorded here. The project follows Semantic Versioning for the platform catalog; individual modules retain their own versions.

## Unreleased

- Required a least-privilege `allowed-tools` declaration in every module manifest and `SKILL.md` frontmatter; validation now fails on missing, malformed, or mismatched declarations.
- Added `tools/devops_exec.py`, a wrapper that executes exactly one approved command: canonical argv digest must equal the approved plan digest, the operation gate re-runs immediately before launch, and every attempt is recorded in a secret-redacted execution ledger.
- Added `tools/hooks/pretooluse_gate.py`, a fail-closed PreToolUse hook that denies mutating, obfuscated, or unclassifiable shell commands without a fresh gate PASS bound to the exact command digest, with setup documentation in `docs/hooks-setup.md`.
- Migrated the portfolio demo to gated wrapper execution, including a blocked command-drift path.
- Split README safety properties into enforced and advisory guarantees.

## 0.3.0 - 2026-08-17 (release candidate 1)

- Added the remaining roadmap modules for Cloudflare, infrastructure as code, delivery pipelines, data resilience, generic and named cloud providers, Kubernetes, enterprise networking, secrets/access, and evidence-led security compliance work.
- Added machine-readable provider freshness, expanded install profiles and capability routing, and adversarial scenarios for the new risk domains.
- Added Apache-2.0 licensing plus contribution, governance, and support policies.
- Added SHA-256-locked Python dependencies and cross-platform CI with immutable action revisions.
- Hardened policy-digest binding, capability routing, transactional profile installation, symlink-safe packaging, and cross-runtime deterministic stored ZIP releases.
- Added a portfolio-focused README, architecture diagrams, an anonymized pilot case study, and a local-only fail-closed change-control demo with rollback verification.
- Added a clean public-source exporter so private Git history, operation records, lab artifacts, and target-specific tools cannot enter the portfolio repository.
- Added minimal-permission GitHub validation, dependency review, manual release preparation, issue forms, CODEOWNERS, and repository-security configuration guidance.

## 0.2.0 - 2026-08-17

- Introduced contract v2, plan-bound approvals, separation of duties, change locks, recovery evidence, untrusted-content boundaries, chained ledgers, deterministic packaging, release verification, and transactional installation.
- Added Linux, Windows Server, Docker, network-edge, and reliability executors.
