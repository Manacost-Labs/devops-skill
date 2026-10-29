# Changelog

All notable platform changes are recorded here. The project follows Semantic Versioning for the platform catalog; individual modules retain their own versions.

## Unreleased

## 0.8.0 — 2026-10-29

- Deepen Docker and Kubernetes crash/resource, networking and storage diagnosis with explicit target, history, identity, ownership and partial-evidence boundaries.
- Add application/data compatibility and newest-write decisions before image/controller reversal; cover forward repair, writer fencing, isolated restore and external-effect reconciliation.
- Add bounded offline identity-bound Docker/Pod summaries, official-source mappings, adversarial scenarios and disposable native Docker/kind fixtures, including incompatible synthetic data changes and recovery-choice evidence.
- Correct Compose preflight handling of long-form named volumes and reject literal sensitive fallback values in environment interpolation.

## 0.7.0 — 2026-10-29

- Deepen Windows Server procedures for SMB/NTFS, host certificates/private keys, scheduled tasks, standalone storage, security and file/host recovery. Correct unsupported SQL Server recovery routing.
- Add failure-aware bounded metadata helpers for server discovery, exact descriptors/certificates and offline task XML; preserve unknown/partial state and avoid raw sensitive payloads.
- Add focused Windows install profile, official-source mappings, adversarial scenarios and native disposable Server 2025 fixtures for ACL/file recovery, restricted SMB, disabled task definitions, PFX/key recovery and VHD-backed storage.


## 0.6.0 — 2026-10-29

- Extend data resilience to MySQL/MariaDB logical/binlog recovery, MariaDB physical full/incremental preparation and standard asynchronous cutover planning.
- Add quarantine, transaction-boundary, GTID, key/retention and application recovery evidence procedures, plus a bounded offline artifact-chain checker.
- Add real isolated logical/PITR and physical incremental restore drills on pinned engines, adversarial receipt tests and updated routing/source/profile documentation.


## 0.5.0 — 2026-10-29

- Expand Linux operations with RHEL-family procedures, cgroup/resource diagnosis, storage/boot, networking, access and SELinux/AppArmor boundaries. Make the local audit report missing evidence without claiming health or running package discovery.
- Expand reliability with Prometheus/Alertmanager, Grafana, Loki/OTel pipelines, privacy/cardinality/cost, SLO burn windows, incident/capacity/release procedures and real promtool examples.
- Add database-operations for PostgreSQL/MySQL/MariaDB waits, connections, replication diagnosis and maintenance intent, with separate engine SQL and an offline connection budget. Keep recovery ownership explicit, including unsupported MySQL/MariaDB recovery.
- Add strict offline SLO arithmetic, source freshness mappings, negative evaluations, isolated pinned-engine SQL/promtool CI and release/install coverage for 23 modules.

### Earlier 0.4.1 work

- Independent review follow-up: reject output operands in the inspection form of `uniq`; coordinate runtime execution/planning/upgrades with a native process lock outside the replaceable directory; sync POSIX journal directory entries before launch.

- Prepare RC 0.4.1 with a conservative command grammar: reject unknown options, attached shell operators, arbitrary output paths, alternate shells and direct editing tools in explicitly protected Claude sessions. Preserve the real-time approval checks from the security hardening PR.
- Persist an fsynced launch intent before execution; distinguish pre-launch refusals, process results, timeouts, unknown outcomes and post-launch audit failures.
- Add explicit, preview-first complete runtime installation with recovery copies and preservation of local operation records. Keep skill-only installation separate and clearly labeled.
- Correct Claude plugin root-path compatibility, explain permission pre-approval semantics and runtime trust assumptions, and generate public-source receipts only at export time.


- Added `tools/devops_plan.py`, which builds a contract-v2 operation request bound to one exact command: it computes the canonical command, policy, and target-profile digests, derives the minimum risk class the policy implies and refuses to understate it, requires acceptance criteria at R2 and above, and names every remaining human obligation. Generated requests are structurally unauthorized until a real approver fills them, so planning never grants authority.
- Packaged the repository as a Claude Code plugin and marketplace (`.claude-plugin/`), installable with `/plugin marketplace add Manacost-Labs/devops-skill`. The plugin ships skills only; the fail-closed command gate stays opt-in through `docs/hooks-setup.md`.
- Added `github-operations`, a bounded GitHub control-plane executor (catalog 0.4.0, 22 skills): branch protection and rulesets, deployment environments and reviewer gates, Actions run and runner administration, releases, and token-permission scope, with a permission-model reference, verified failure modes, a change-card template, and a read-only repository-protection audit script; joined the `delivery` and `all` profiles with docs.github.com freshness validation.
- Taught the PreToolUse gate to classify the `gh` CLI: view/list/checks subcommands and body-less `gh api` GET calls pass as read-only; every other `gh` invocation is denied and routed through the gated wrapper.
- Added six GitHub prompt-injection scenarios (PR-comment merge pressure, log-embedded protection rollback, bypass-list requests, fake API approvals, release re-tagging, fork access to privileged runners) to the adversarial evaluation suite.
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
