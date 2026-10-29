# Security policy and state boundaries

## RBAC

Map subject to Role/ClusterRole and bindings. Flag wildcard verbs/resources/API groups, secret read, pod exec/attach/port-forward, workload creation that can mount service-account tokens, escalation/bind/impersonate, node/proxy, certificate signing, webhook, and RBAC write paths. Prefer namespace Roles, resource names where practical, short-lived identities, and separate read/deploy/admin roles. Verify both intended allow and intended deny cases.

## Pod Security Standards

Inventory namespace `enforce`, `audit`, and `warn` labels, exemptions, workload security contexts, host namespaces, privileged mode, capabilities, hostPath, seccomp, user IDs, and volume types. Stage with audit/warn, remediate, canary, then enforce the approved PSS level/version. Preserve an independently controlled recovery path; do not exempt an entire namespace without scoped rationale and expiry.

## NetworkPolicy

Confirm the CNI implements required policy semantics. Build an ingress and egress dependency map including DNS, API server, identity, telemetry, registries, databases, and external APIs. Start with a canary and explicit selectors. Verify allowed and denied flows from representative pods. Coordinate cloud security groups, service mesh, ingress, egress gateways, and external firewalls with their owners.

## Persistent volumes

Record PVC/PV/StorageClass/CSI driver, access/volume modes, reclaim policy, binding, topology, snapshots, application consistency, and owner. Scaling or deleting StatefulSets, PVCs, PVs, snapshots, or namespaces can destroy or orphan data. Require a fresh approved snapshot/backup and isolated restore evidence for destructive R4 work. A CSI snapshot object alone is not restore proof.

Use `references/storage-diagnostics.md` for identity/attach/mount/capacity diagnosis and `references/stateful-release-recovery.md` before a data-changing update or reversal. ReadWriteOnce does not serialize application writers. Backup and restore decisions include schema/file/queue compatibility, latest writes and external effects.

## Control plane

For managed Kubernetes, use the provider's documented backup/restore and upgrade contracts through the provider owner. For self-managed clusters, coordinate etcd snapshot consistency, encryption keys, certificates, manifests, version compatibility, and restore testing with the control-plane owner. Do not claim that GitOps manifests or workload backup can restore cluster identity, RBAC, CRDs, or etcd state.
