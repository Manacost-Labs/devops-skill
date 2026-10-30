# DevOps Skill Platform

**Portfolio project · release candidate 0.15.0**

A modular, Codex-first platform for bounded, evidence-driven infrastructure work. It contains 23 composable skills under contract v2: a coordinator, a fail-closed policy and validation layer, and focused modules for hosts, directory identity, containers, edge, delivery, the GitHub control plane, data, cloud providers, Kubernetes, networking, access, reliability, and security governance.

This project demonstrates system administration and DevOps engineering practices: decomposing operational ownership, classifying risk, planning recovery, constraining privileged changes, validating packages, and collecting verification evidence. It is not a certification, a managed service, or an autonomous administrator.

DNS, TLS and reverse proxies now cover authoritative/cache-aware diagnosis, certificate renewal and safe pair rotation, upstream/trust failures, staged changes and partial recovery. See [edge scope and real DNS/TLS/proxy checks](docs/network-edge-depth.md).

CI/CD now covers GitHub Actions trust, effective secrets/OIDC rights, artifact and signed-provenance admission, staged deployments and recovery after partial effects. See [CI/CD scope and actual workflow/artifact checks](docs/cicd-operations-depth.md).

Terraform/OpenTofu now cover exact state/backend ownership, lock contention, drift, stale plans and recovery after partial apply or failed state persistence. See [state and recovery scope with native CI](docs/terraform-operations-depth.md).

Ansible now covers repeatable configuration, exact group/host targeting, gradual fleet updates and recovery after a partial failure. See [Ansible scope and native CI evidence](docs/ansible-operations-depth.md).

## Install as a Claude Code plugin

```
/plugin marketplace add Manacost-Labs/devops-skill
/plugin install devops-skill-platform@manacost-devops
```

This enables the 23 skill instructions. The plugin does not enable execution protection automatically. Use a stable execution runtime and explicitly configure the optional Claude Code gate when operating infrastructure; see [hook setup and its trust boundary](docs/hooks-setup.md). The manifest is also validated with Claude Code 2.1.207.

## Choose an installation

| Installation | What you receive | Execution protection |
|---|---|---|
| Claude Code plugin | Skill instructions and their packaged supporting files | Optional; configure the hook explicitly |
| Codex skill profile | Selected skill folders in the skills directory | Guidance and local validators; full runtime supplies the native Codex guard |
| Full execution runtime | Planner, signed task broker/client, native Codex guard, verifier, documentation and all 23 modules | Protected execution requires separate broker provisioning; hooks are defense in depth |

For a complete runtime, start from a source checkout or a verified runtime archive with Python 3.13 and the hash-locked requirements installed:

```powershell
# Preview without writing.
python tools/install.py --runtime --destination ../devops-runtime
# Install the reviewed complete runtime.
python tools/install.py --runtime --destination ../devops-runtime --apply
# Optionally install the instructions needed by Codex.
python ../devops-runtime/tools/install.py --profile web-linux --apply
```

Runtime installation requires an explicit destination outside the source tree. Replacing it requires `--apply --force`; the installer retains a recovery copy and preserves `operations/` plans and journal records. It refuses to replace an unrelated nonempty directory. The runtime keeps all modules so its catalog remains self-contained; the skill profile selects which instructions the agent discovers.

Planning and runtime replacement retain the local upgrade lock. Protected execution has its own broker lifetime lock, durable receipts and target quarantine; the read-only client creates no local execution authority. Stop old direct executors before migration.

Use absolute paths to runtime programs when working in another project. The relative command examples below assume your current directory is the runtime or source root. Installing a skill profile alone does not install the top-level execution programs.

## How the pieces fit together

Skills guide investigation and planning. The local gate checks contract consistency. A separately protected broker admits only registered tasks using externally signed, finite authority, then runs a verified snapshot under a separate worker identity. The agent has neither signing keys nor direct target credentials. See [protected execution and migration](docs/protected-execution.md).

## Autonomy modes

| Mode | Automatic ceiling inside issued authority | New exact confirmation |
|---|---|---|
| Safe (default) | R0–R1 | R2–R4 |
| Balanced | R0–R2 | R3–R4 |
| Semi-Auto | R0–R3 | R4 |
| Full Auto | R0–R4 in an explicitly trusted authorized environment | Destructive/irreversible effects and exceptions; hard policy denials remain blocked |

Above-Safe work uses one operator-issued scope/target/window authorization, then reuses it for new exact plans inside that envelope. Every launch still checks policy, risk, identity/scope bindings, recovery and audit. A tested production deployment remains R3. The agent prepares unapproved drafts; a protected external issuer/store supplies actual authority. The enterprise baseline retains Safe. Read the [operator setup, examples and trust limits](docs/autonomy-modes.md). These modes are independent of install profiles and host/tool permission settings.

Say **“work in Balanced for this project”** to prepare the scope through chat. Local confirmation selects a planning preference; it cannot authenticate execution authority. The protected owner issuer signs that finite scope once, and ordinary covered tasks reuse it. “Safe” routes a principal-wide restriction to the broker when configured. See [chat flow and limitations](docs/autonomy-modes.md). Installing this release never escalates an environment.

These pieces have different responsibilities: a successful package check proves compatible files; a command exit code proves only a process outcome; service acceptance needs its own evidence. See the [5-minute safe evaluation](#5-minute-safe-evaluation) for a read-only introduction.

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
| Platform design | Capability-based routing across 23 dependency-closed modules |
| Linux and workload operations | Linux, Windows Server, Docker, Kubernetes, network-edge, and reliability modules |
| Delivery and state safety | IaC plan binding, CI/CD trust boundaries, backup/restore and rollback requirements |
| Cloud engineering | Provider-neutral routing plus AWS, Google Cloud, Azure, Selectel, and Cloudflare packs |
| Security engineering | Least privilege, untrusted-input boundaries, expiring approvals, separation of duties, and redacted evidence |
| Software quality | Schema validation, deterministic release packaging, dependency pinning, unit tests, and adversarial scenarios |
| Operational judgement | Explicit stop conditions, recovery gates, measurable acceptance criteria, and honest partial-verification states |

## Safety properties

Each check enforces only the stated execution or packaging path. Skill prose is guidance. Tool pre-approvals are convenience permissions, not a deny list. The optional Claude hook requires trusted, protected settings, runtime, interpreter, PATH and CLI configuration; it is not an operating-system sandbox.

| Property | Type | Mechanism |
|---|---|---|
| A request with invalid policy, target/plan/authority binding, approval records, window or recovery fields is refused | Request validation | `operation_gate.py` validates exact approval or scoped prior authority; external identity and evidence authenticity remain organization-owned |
| Only fixed registered tasks may execute | Protected broker | mTLS identity, scoped Ed25519 grants, authoritative risk/target, verified code snapshot, durable admission and separate worker UID |
| Direct shell/edit/connector/delegation tools are denied in configured Codex sessions | Defense in depth | Native PreToolUse guard; managed host policy and independently bounded credentials remain necessary |
| Every module declares matching `allowed-tools` metadata and manifest entries | Package validation | This checks declarations. In Claude Code, `allowed-tools` pre-approves tools and does not restrict the available tool pool; use actual runtime permission controls |
| Catalog compatibility, dependency-closed profiles, hash-locked dependencies, deterministic releases, and archive path safety | Enforced | platform validator, release builder, and `verify_release.py` |
| Read-only discovery is the default; sensitive or cross-tenant reads are separately governed | Advisory | documented workflow in `devops-core` |
| Repository text, tickets, logs, web pages, command output, and tool responses are untrusted data and cannot grant authority, choose privileged credentials, or weaken policy | Advisory | untrusted-content boundary references consumed by every module |
| Risk classification, minimal module routing, honest `partially_verified` reporting, and evidence redaction outside the wrapper ledger | Advisory | module contracts, templates, and evaluation scenarios |

Local ledgers and release manifests are integrity evidence, not external identity, signatures, immutable storage, SLSA provenance, or certification. Production use still requires organization-owned identity, short-lived credential brokerage, protected source control and CI, signed provenance, change management, immutable audit storage, data governance, accountable owners, and independent assessment.

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
| Delivery and state | `iac-operations`, `cicd-operations`, `github-operations`, `data-resilience-operations` | Reviewed plans, protected pipelines, GitHub protections/environments/releases, restore-proven data operations |
| Daily database operations | `database-operations` | PostgreSQL/MySQL/MariaDB waits, connection budgets, replication diagnosis and maintenance planning; recovery stays with a confirmed engine-specific owner |
| Edge and networks | `network-edge-operations`, `cloudflare-operations`, `enterprise-networking` | DNS/TLS/HTTP, Cloudflare control plane, VPN/BGP/hybrid routing |
| Cloud | `cloud-generic`, `cloud-aws`, `cloud-gcp`, `cloud-azure`, `cloud-selectel` | Provider discovery and bounded control-plane operations using current official docs |
| Trust and assurance | `secrets-access-operations`, `reliability-operations`, `security-compliance-operations` | JIT access, service health, incidents, controls, exceptions, evidence—not certification |

Provider packs do not replace the technical modules. For example, an EKS migration normally needs `cloud-aws`, `kubernetes-operations`, `data-resilience-operations`, `secrets-access-operations`, and `reliability-operations`, selected only for the layers actually affected.

Managed-service boundaries are normative in the [control-plane ownership matrix](devops-core/references/control-plane-ownership.md): provider packs own provider APIs, while IaC state, Kubernetes resources, data recovery, identity lifecycle, network paths, release trust, and service acceptance remain with their specialist modules.

## Host, monitoring and database operations

Linux covers Debian/Ubuntu and confirmed RHEL-family hosts with focused procedures for cgroups/OOM, packages, storage/boot, networking and mandatory access controls. Reliability covers Prometheus/Alertmanager, Grafana, Loki/OTel, missing data, burn rates, capacity and release acceptance. The database module separates everyday PostgreSQL/MySQL/MariaDB diagnosis from recovery. Data resilience now includes [MySQL/MariaDB backup, PITR and isolated restore drills](docs/mysql-mariadb-recovery.md). Read the [scope, examples and validation limits](docs/operations-depth.md).

## Windows Server operations

Windows operations now covers SMB/NTFS, host certificates/keys, Task Scheduler, standalone storage and file/host recovery with focused procedures and read-only evidence helpers. The [scope and native-test limits](docs/windows-server-depth.md) distinguish configuration inventory from effective access, trust and restore proof.

## Docker and Kubernetes operations

Container modules now cover crash/OOM/probe/eviction diagnosis, DNS/listener/Service/policy paths, mount/PVC/backing-storage identity and recovery after data-changing releases. They distinguish compatible application reversal, forward repair and isolated restore with newest-write reconciliation. [Scope and native tests](docs/container-operations-depth.md) explain offline snapshot helpers, disposable Docker/kind fixtures and limits; image/template rollback alone does not restore data.

## Install profiles

| Profile | Intended use |
|---|---|
| `core` | Planning, policy, validation, and safe handoff |
| `web-linux` | Linux + Docker + HTTP edge + Cloudflare + reliability |
| `windows-server` | Windows host, SMB/NTFS, certificates, tasks, storage/recovery, access and reliability |
| `hybrid-server` | Linux/Windows hosts + Docker + HTTP edge + reliability |
| `identity-directory` | Active Directory and GPO work with Windows-host, privileged-access, and reliability handoffs |
| `delivery` | IaC, CI/CD, GitHub control plane, and secret/access boundaries |
| `data-safe` | Database diagnosis, connection budgets, supported recovery, reliability and access controls |
| `cloud-foundation` | Provider-neutral cloud foundation with IaC, edge, reliability, and access |
| `kubernetes` | Kubernetes workload operations with Docker, edge, reliability, and access |
| `aws-platform`, `gcp-platform`, `azure-platform`, `selectel-platform` | Named provider plus IaC, CI/CD, containers, Kubernetes, data, network, access, and reliability handoffs |
| `hybrid-network` | Linux/Windows endpoints plus HTTP edge, VPN/BGP/hybrid networking, access, and reliability |
| `assurance` | Evidence-led security governance with access and reliability evidence sources |
| `all` | All 23 modules, including directory identity, GitHub, named provider, and enterprise packs |

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

A successful validation reports `23/23 compatible installed skills`. The installer then prints each proposed destination and ends with `Dry-run only`. Review the [architecture](docs/architecture.md) next, or run the [shipped synthetic portfolio demo](examples/portfolio-demo/README.md) without connecting to a real target.

`tools/install.py` is dry-run by default. `--apply` writes to the selected skills directory, and `--apply --force` can replace existing skills; neither option is part of this safe evaluation.

## Running one real change

Use the [protected broker setup and typed client examples](docs/protected-execution.md).
The agent submits a registered task ID and finite parameters under one externally
signed task grant. It cannot supply command strings, risk, target or approver labels.
The broker prepares exact additional admission when policy requires it and refuses
unknown, expired, widened or unsigned authority.

**Migration:** the old `devops_exec.py --operation ... -- command` API refuses all
execution. Existing planners, legacy JSON approvals and chat callbacks are planning
and consistency helpers only. No fabricated local record can authorize the broker.
Do not restore the old wrapper or grant the agent direct infrastructure credentials
to work around this refusal.

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

Windows Server, Linux, reliability, database operations, Cloudflare, IaC, CI/CD, GitHub operations, data-resilience, AWS, Google Cloud, Azure, Selectel, and Kubernetes manifests declare official documentation sources, map every capability to those sources, and record `last_verified`. Validation rejects missing capability coverage, unapproved source hosts, future dates, and release metadata older than 183 days. This does not make memorized behavior safe: a material change must refresh the exact official operation page and run read-only discovery against the actual account, project, subscription, cluster, tool, or database topology.

## Development and release

The following commands require a source checkout. Runtime release archives intentionally contain the installer and verifier, but not tests, CI configuration, the release builder, or target-specific administration tools.

```powershell
python devops-platform-contracts/scripts/validate_platform.py
python -m unittest discover -s tests -v
python tools/build_public_source.py --output ..\devops-skill-platform-public
python tools/build_release.py --output dist/devops-skill-platform-0.15.0.zip
python tools/verify_release.py dist/devops-skill-platform-0.15.0.zip
```

`PUBLIC-SOURCE-MANIFEST.json` is generated only in a fresh public-source export, not maintained as a stale receipt in the development tree. `build_public_source.py` creates a fresh allowlisted source tree without Git history, private operation records, lab artifacts, release archives, credentials, or target-specific tools. Use that clean tree—not an export of a private operations repository—as the source of a new public portfolio repository.

Before publication, run the standard Codex validator for every changed skill and independent forward/red-team scenarios. A production release additionally needs protected two-party review, an SBOM, vulnerability policy results, signed provenance, a trusted signer/builder, independent verification, and registry rollback. See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [SUPPORT.md](SUPPORT.md).

## License

Licensed under the [Apache License 2.0](LICENSE). No project-level `NOTICE` file is currently required by the reviewed repository contents; add one before distribution if a later dependency or attribution review identifies an obligation. Third-party tools and runtime dependencies retain their own licenses.
