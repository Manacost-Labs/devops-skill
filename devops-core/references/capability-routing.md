# Capability routing

Select the smallest installed set that covers the confirmed task. Read a module manifest before invoking it.

| Confirmed concern | Module |
|---|---|
| Linux hosts, SSH, systemd, ports, disks, logs | `linux-operations` |
| Windows Server, WinRM/RDP, Windows services, Event Logs, Windows Firewall | `windows-server-operations` |
| Docker, Compose, images, registries, volumes | `docker-operations` |
| DNS, TLS, HTTP, reverse proxy, origin reachability | `network-edge-operations` |
| Cloudflare DNS, WAF, Tunnel, Access, Workers | `cloudflare-operations` |
| Metrics, logs, traces, SLOs, alerts, incidents | `reliability-operations` |
| Terraform/OpenTofu, Ansible, cloud-init, drift | `iac-operations` |
| GitHub Actions, artifact pipeline, deploy gates | `cicd-operations` |
| PostgreSQL/Redis, backups, restores, migrations | `data-resilience-operations` |
| Secret references, workload identity, JIT access, rotation, break-glass | `secrets-access-operations` |
| Generic, unfamiliar, or unsupported VPS/cloud account | `cloud-generic` |
| AWS account, Organizations, IAM, VPC, EC2/ECS/EKS/RDS control plane | `cloud-aws` plus the narrow technical module |
| Google Cloud organization/project, IAM, VPC, Compute/GKE/Cloud Run/Cloud SQL control plane | `cloud-gcp` plus the narrow technical module |
| Azure tenant/subscription, Entra/RBAC, VNet, VM/AKS/Functions/database control plane | `cloud-azure` plus the narrow technical module |
| Selectel account/project, IAM, cloud/OpenStack resources, managed services | `cloud-selectel` plus the narrow technical module |
| Kubernetes workload or cluster operations | `kubernetes-operations`; add the provider pack only for its managed control plane |
| VPN, BGP, routing, segmentation, on-premises or hybrid connectivity | `enterprise-networking` |
| Threat models, vulnerability lifecycle, exceptions, control ownership, evidence packs | `security-compliance-operations` |

## Composition rules

- Read `control-plane-ownership.md` for managed Kubernetes, managed database, IaC, identity, network, container and delivery boundaries. Cross-boundary changes require every named owner; a provider API success is not specialist verification.
- Route by the affected control plane, not by a tool name appearing in a file. Provider packs own provider facts; `iac-operations` owns plan/state discipline; the workload, data, network, access, and reliability modules retain their own layers.
- Use `cloud-generic` when a provider pack is absent or the platform is unfamiliar. Do not use it to guess provider-specific commands or permissions.
- Do not select Kubernetes merely for possible future scale. Select it for an existing cluster or requirements that justify its operational cost and failure modes.
- Add `data-resilience-operations` before a stateful migration, `secrets-access-operations` before credential or privileged-access changes, and `reliability-operations` when acceptance depends on service health or an observation window.
- Keep public DNS/TLS/HTTP paths in `network-edge-operations`; keep BGP, VPN, routing domains, and enterprise segmentation in `enterprise-networking`.
- Treat control mappings as evidence indexes. Only an accountable external assessor can determine compliance or certification.

If a required module is absent, limit work to core-safe discovery and design. State the missing module and do not simulate its expertise.
