# Control-plane ownership and composition

Select modules by the state and API being changed. A tool, repository, or credential may cross several control planes; it does not transfer ownership between them. When a row requires composition, every named owner must provide its plan fragment, risk and verification evidence before the combined operation is approved.

| Boundary operation | Primary executor | Required composition |
|---|---|---|
| Provider account/project/subscription discovery, quotas and resource envelope | Named cloud provider pack | `secrets-access-operations` for identity lifecycle; `cloud-generic` only for intake when the provider is unknown |
| Provider IAM/RBAC policy or workload-identity binding | Named cloud provider pack for provider API | `secrets-access-operations` owns access intent, least privilege, JIT/rotation/revocation and break-glass evidence |
| VPC/VNet, security group and provider load balancer | Named cloud provider pack | `network-edge-operations` for public DNS/TLS/HTTP; `enterprise-networking` for transit, BGP, VPN, routing domains or hybrid segmentation |
| Terraform/OpenTofu-managed provider object | `iac-operations` for source, state, locking and saved-plan identity | Named provider pack validates current provider semantics, target identity, permissions, quota, cost and live verification |
| Managed Kubernetes control plane, version or node pool | Named cloud provider pack for provider API | `kubernetes-operations` validates skew, APIs, workloads, disruption, capacity and post-change cluster health; `data-resilience-operations` joins for stateful storage risk |
| Kubernetes API objects, workloads, RBAC, PSS and NetworkPolicy | `kubernetes-operations` | Provider pack only for managed control-plane, cloud load-balancer, identity, node or storage-envelope effects |
| Managed database instance size, engine envelope, maintenance window or provider parameter group | Named cloud provider pack for provider API | `data-resilience-operations` owns data compatibility, replication, backup/restore proof, RPO/RTO, cutover and application consistency |
| Schema/data migration, PITR, logical failover, backup, restore or retention | `data-resilience-operations` | Provider pack executes only the separately planned provider-native infrastructure/API fragment; `iac-operations` joins when state-managed |
| Image build/runtime and registry artifact | `docker-operations` | `cicd-operations` owns producer trust, immutable promotion and attestation; provider pack owns provider registry/IAM envelope |
| Release pipeline and protected deployment | `cicd-operations` | Every target executor verifies its own plan fragment and final state; `reliability-operations` owns user-path acceptance and observation window |
| Active Directory DS OUs, users, computers, groups, membership, delegation and GPO objects/links | `identity-directory-operations` | `secrets-access-operations` owns privileged-session, JIT/revocation and break-glass controls; `windows-server-operations` owns host membership and client-side policy result |
| GPO-driven production configuration or security baseline | `identity-directory-operations` | Owning host/workload executor validates safe application; `reliability-operations` verifies the service path and observation window |

## Combined-operation rules

1. Normalize one operation ID and target profile, but retain a separate immutable plan fragment and digest for each control plane.
2. Produce a combined plan that names ordering, dependencies, shared abort criteria, recovery ownership and the digest of every fragment.
3. Classify the combined operation at the highest applicable risk. Approval and policy evaluation bind the combined digest and every target fingerprint.
4. Acquire locks in a documented stable order. Stop before mutation if any owner, capability, lock, credential scope, source freshness record or recovery proof is missing.
5. Do not let one module execute another module's API as a shortcut. The coordinator may sequence executors; it does not merge their authority.
6. Verify each control plane independently and then verify the external user path. Report partial verification honestly when any required evidence is unavailable.

Provider packs must not claim that a successful provider API response proves Kubernetes workload health, database recoverability, network reachability, access governance or release integrity. Specialist modules must not invent provider behavior or bypass provider ownership merely because the same resource appears in IaC.
