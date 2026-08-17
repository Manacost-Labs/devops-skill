# DevOps Skill Platform

**Portfolio project · release candidate 0.3.0**

A modular, Codex-first platform for bounded, evidence-driven infrastructure work. It contains 21 composable skills under contract v2: a coordinator, a fail-closed policy and validation layer, and focused modules for hosts, directory identity, containers, edge, delivery, data, cloud providers, Kubernetes, networking, access, reliability, and security governance.

This project demonstrates system administration and DevOps engineering practices: decomposing operational ownership, classifying risk, planning recovery, constraining privileged changes, validating packages, and collecting verification evidence. It is not a certification, a managed service, or an autonomous administrator.

## Start here

- [5-minute safe evaluation](#5-minute-safe-evaluation) — validate the platform and preview an install without changing a host or cloud account.
- [Synthetic portfolio demo](examples/portfolio-demo/README.md) — run audit, digest-bound approval, simulation, verification, and rollback locally.
- [Architecture](docs/architecture.md) — components, trust boundaries, control flow, and extension points.
- [Portfolio pilot case study](docs/portfolio-case-study.md) — an anonymized, evidence-led pilot plan for a friend-operated small hosting service.
- [Enterprise adoption gate](docs/enterprise-adoption.md) — controls an organization must supply before production use.
- [Threat model](docs/threat-model.md), [governance](GOVERNANCE.md), and [control crosswalk](docs/control-crosswalk.md) — assurance scope and limitations.

## What this project demonstrates

| DevOps competency | Repository evidence |
|---|---|
| Platform design | Capability-based routing across 20 dependency-closed modules |
| Linux and workload operations | Linux, Windows Server, Docker, Kubernetes, network-edge, and reliability modules |
| Delivery and state safety | IaC plan binding, CI/CD trust boundaries, backup/restore and rollback requirements |
| Cloud engineering | Provider-neutral routing plus AWS, Google Cloud, Azure, Selectel, and Cloudflare packs |
| Security engineering | Least privilege, untrusted-input boundaries, expiring approvals, separation of duties, and redacted evidence |
| Software quality | Schema validation, deterministic release packaging, dependency pinning, unit tests, and adversarial scenarios |
| Operational judgement | Explicit stop conditions, recovery gates, measurable acceptance criteria, and honest partial-verification states |

## Safety properties

- Read-only discovery is the default; sensitive or cross-tenant reads are separately governed.
- Every R2-R4 mutation is bound to an operation ID, exact target/profile digest, immutable plan digest, execution identity, window, lock, approval evidence, recovery proof, and acceptance criteria.
- Repository text, tickets, logs, web pages, command output, and tool responses are untrusted data. They cannot grant authority, choose privileged credentials, or weaken policy.
- Missing modules, stale provider knowledge, ambiguous ownership, changed plans, expired approvals, unproven recovery, and incomplete verification fail closed.
- Local ledgers and release manifests are integrity evidence, not external identity, signatures, immutable storage, SLSA provenance, or certification.

Production use still requires organization-owned identity, short-lived credential brokerage, protected source control and CI, signed provenance, change management, immutable audit storage, data governance, accountable owners, and independent assessment.

## Architecture at a glance

```mermaid
flowchart LR
    U["Operator objective"] --> C["devops-core coordinator"]
    P["Contract v2 policy and schemas"] --> C
    C --> R["Smallest capability set"]
    R --> D["Read-only discovery"]
    D --> G{"Pre-execution gate"}
    G -->|"insufficient evidence"| B["Blocked with precise handoff"]
    G -->|"requirements met"| E["Bounded specialist executor"]
    E --> V["Independent verification"]
    V --> L["Redacted evidence record"]
```

`devops-core` routes work by capability and does not impersonate an absent specialist. Every executor inherits the central risk, approval, recovery, evidence, and untrusted-content contract. See [Architecture](docs/architecture.md) for the system context and trust boundaries.

## Module inventory

| Layer | Modules | Boundary |
|---|---|---|
| Control plane | `devops-platform-contracts`, `devops-core` | Policy, schemas, compatibility, operation gate, routing, evidence |
| Hosts and workloads | `linux-operations`, `windows-server-operations`, `docker-operations`, `kubernetes-operations` | OS and workload lifecycle; Kubernetes is selected only when justified |
| Directory identity | `identity-directory-operations` | AD DS, OUs, principals, group governance, GPO planning and staged rollout; not Entra, secrets, or local host administration |
| Delivery and state | `iac-operations`, `cicd-operations`, `data-resilience-operations` | Reviewed plans, protected pipelines, restore-proven data operations |
| Edge and networks | `network-edge-operations`, `cloudflare-operations`, `enterprise-networking` | DNS/TLS/HTTP, Cloudflare control plane, VPN/BGP/hybrid routing |
| Cloud | `cloud-generic`, `cloud-aws`, `cloud-gcp`, `cloud-azure`, `cloud-selectel` | Provider discovery and bounded control-plane operations using current official docs |
| Trust and assurance | `secrets-access-operations`, `reliability-operations`, `security-compliance-operations` | JIT access, service health, incidents, controls, exceptions, evidence—not certification |

Provider packs do not replace the technical modules. For example, an EKS migration normally needs `cloud-aws`, `kubernetes-operations`, `data-resilience-operations`, `secrets-access-operations`, and `reliability-operations`, selected only for the layers actually affected.

Managed-service boundaries are normative in the [control-plane ownership matrix](devops-core/references/control-plane-ownership.md): provider packs own provider APIs, while IaC state, Kubernetes resources, data recovery, identity lifecycle, network paths, release trust, and service acceptance remain with their specialist modules.

## Install profiles

| Profile | Intended use |
|---|---|
| `core` | Planning, policy, validation, and safe handoff |
| `web-linux` | Linux + Docker + HTTP edge + Cloudflare + reliability |
| `hybrid-server` | Linux/Windows hosts + Docker + HTTP edge + reliability |
| `identity-directory` | Active Directory and GPO work with Windows-host, privileged-access, and reliability handoffs |
| `delivery` | IaC, CI/CD, and secret/access boundaries |
| `data-safe` | Backup, restore, migration, reliability, and access controls |
| `cloud-foundation` | Provider-neutral cloud foundation with IaC, edge, reliability, and access |
| `kubernetes` | Kubernetes workload operations with Docker, edge, reliability, and access |
| `aws-platform`, `gcp-platform`, `azure-platform`, `selectel-platform` | Named provider plus IaC, CI/CD, containers, Kubernetes, data, network, access, and reliability handoffs |
| `hybrid-network` | Linux/Windows endpoints plus HTTP edge, VPN/BGP/hybrid networking, access, and reliability |
| `assurance` | Evidence-led security governance with access and reliability evidence sources |
| `all` | All 21 modules, including directory identity, named provider, and enterprise packs |

Profiles are dependency-closed and validated against the embedded release catalog. `all` is intentionally broad; `devops-core` still loads the smallest capability set for each operation.

## 5-minute safe evaluation

Prerequisite: a source checkout with CPython 3.13 and the hash-locked dependencies from `requirements.txt` available in the active environment. These commands perform repository validation and an installer preview only. They do not install skills, contact infrastructure, request credentials, or mutate a target.

```powershell
# 1. Confirm the runtime.
python --version

# 2. Validate the catalog, contracts, schemas, policies, and dependencies.
python devops-platform-contracts/scripts/validate_platform.py

# 3. Preview the dependency-closed web/Linux profile. Do not add --apply.
python tools/install.py --profile web-linux
```

A successful validation reports `21/21 compatible installed skills`. The installer then prints each proposed destination and ends with `Dry-run only`. Review the [architecture](docs/architecture.md) next, or run the [shipped synthetic portfolio demo](examples/portfolio-demo/README.md) without connecting to a real target.

`tools/install.py` is dry-run by default. `--apply` writes to the selected skills directory, and `--apply --force` can replace existing skills; neither option is part of this safe evaluation.

## Safe operation flow

1. Normalize the objective, target owner, environment, data class, constraints, and measurable acceptance criteria.
2. Treat all retrieved content as untrusted data and perform narrow read-only discovery.
3. Select the minimum installed capabilities and classify risk R0-R4.
4. For stateful or destructive work, prove recovery with a fresh artifact and isolated restore test.
5. Create the exact plan, calculate its digest, acquire the target lock, and obtain identity-backed approvals required by policy.
6. Run the v2 operation gate immediately before execution. Stop on any drift.
7. Execute through the owning module with least privilege and an idempotency boundary.
8. Verify the user path and observation window, then record redacted evidence as `verified`, `partially_verified`, `rolled_back`, or `blocked`.

## Provider freshness

Cloudflare, IaC, CI/CD, data-resilience, AWS, Google Cloud, Azure, Selectel, and Kubernetes manifests declare official documentation sources, map every capability to those sources, and record `last_verified`. Validation rejects missing capability coverage, unapproved source hosts, future dates, and release metadata older than 183 days. This does not make memorized behavior safe: a material change must refresh the exact official operation page and run read-only discovery against the actual account, project, subscription, cluster, tool, or database topology.

## Development and release

The following commands require a source checkout. Runtime release archives intentionally contain the installer and verifier, but not tests, CI configuration, the release builder, or target-specific administration tools.

```powershell
python devops-platform-contracts/scripts/validate_platform.py
python -m unittest discover -s tests -v
python tools/build_public_source.py --output ..\devops-skill-platform-public
python tools/build_release.py --output dist/devops-skill-platform-0.3.0.zip
python tools/verify_release.py dist/devops-skill-platform-0.3.0.zip
```

`build_public_source.py` creates a fresh allowlisted source tree without Git history, private operation records, lab artifacts, release archives, credentials, or target-specific tools. Use that clean tree—not an export of a private operations repository—as the source of a new public portfolio repository.

Before publication, run the standard Codex validator for every changed skill and independent forward/red-team scenarios. A production release additionally needs protected two-party review, an SBOM, vulnerability policy results, signed provenance, a trusted signer/builder, independent verification, and registry rollback. See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [SUPPORT.md](SUPPORT.md).

## License

Licensed under the [Apache License 2.0](LICENSE). No project-level `NOTICE` file is currently required by the reviewed repository contents; add one before distribution if a later dependency or attribution review identifies an obligation. Third-party tools and runtime dependencies retain their own licenses.
