# Terraform/OpenTofu state and recovery depth

Platform 0.12.0 expands the existing iac-operations module to 0.5.0. Focused guidance now separates backend/state/lock identity, drift and exact saved plans, and partial-apply/persistence recovery. Ansible and cloud-init remain unchanged.

## Operational boundaries

Treat desired configuration, recorded bindings and actual infrastructure as separate evidence. Resolve the engine/provider/backend/workspace/account identities, preserve protected native state versions and usable recovery, and distinguish contention from a proven stale writer. A backend lock covers one cooperating state writer; overlapping states/controllers and provider jobs need separate fencing.

A saved binary plan binds exact reviewed execution inputs but reserves neither state nor resources. Rejected stale plans require a new reviewed plan/gate. A no-change plan with disabled refresh or reduced visibility is incomplete evidence. Refresh-only apply changes state; state restoration does not undo infrastructure or database writes. After a failed command, reconcile successful/failed/unknown addresses and actual provider effects before a forward fix, association or separately gated compatible recovery.

Admission retains core's selected mode/scoped authority, exact gate, locks, recovery and journal. Do not repeat user consent inside unchanged valid boundaries; do not lower production/state-surgery/destructive risk to fit the mode.

## Native CI

The two jobs **IaC / terraform state and recovery** and **IaC / tofu state and recovery** run real pinned CLIs on disposable GitHub-hosted Linux. They use official checksum-pinned release ZIPs, a checksum-locked offline local-provider mirror, separate temporary resources and an owned loopback HTTP backend with real LOCK/UNLOCK requests. No cloud credentials, live targets, custom secrets or privilege escalation are used. Missing tools, download/checksum errors or failed assertions fail CI, never skip it.

```sh
python tests/smoke_terraform.py terraform -v
python tests/smoke_terraform.py tofu -v
```

The fixture is Linux x86_64 / CPython 3.13 and pins Terraform 1.17.1, OpenTofu 1.13.2 and engine-specific local 2.5.3 packages: registry.terraform.io/hashicorp/local for Terraform, registry.opentofu.org/hashicorp/local for OpenTofu. The provider release bytes/hashes differ; no interchangeable-registry/package claim is made. CLI/provider bytes are downloaded from official release endpoints and checked against pinned SHA-256 values before use. The CLI derives its unpacked-package platform hash only from this verified offline mirror; each scenario then initializes with an unchanged readonly dependency lock.

Each engine covers saved-plan convergence, real deleted-file drift versus disabled-refresh blindness, refresh-only state persistence without resource repair, stale saved-plan rejection, foreign-lineage/older-serial push refusal, competing-process contention, nonce-enforced stale-lock handling, partial successful apply/taint followed by a fresh forward repair, rejected state uploads with error-snapshot recovery, an upload committed despite an error response, moved-address identity preservation, forget-versus-delete, explicit backend migration and the empty-state hazard of reconfiguration.

The native HTTP tests expose two engine/backend boundaries. Terraform 1.17.1 omits the nonce in a fresh force-unlock request and is rejected by the strict server; OpenTofu 1.13.2 supplies the nonce and releases only its exact synthetic lock. No missing-ID unlock is accepted. Both HTTP managers migrate the bindings while generating new destination metadata; tests record both lineage/serial pairs and verify identical binding objects and unchanged resource timestamps. Neither behavior is generalized to untested backends/versions.

Assertions inspect actual local objects, callback-free CLI exit/plan JSON, native lock ownership, backend snapshots/versions and pulled state. The partial-apply fixture deliberately uses an exceptional failing creation-time provisioner to expose nontransactional behavior; it is not a production configuration pattern. Synthetic `force-unlock -force` and automated migration flags are confined to owned fixture state and do not establish real stale-writer proof or production admission.

The toy HTTP service is bound only to loopback and has no TLS/authentication, durable storage, leases or HA. Its injected rejected/ambiguous writes test CLI recovery semantics, not production storage guarantees. No AWS/Azure/GCP backend, IAM/KMS, real infrastructure/data rollback, cross-engine state/plan compatibility, provider job cancellation or service availability is certified. Those require isolated target-specific rehearsals with the provider/data/reliability owners.

Run platform/skill validation, the full regression suite, deterministic release/export verification and secret scanning too. Runtime releases contain the new guidance, but exclude native tests, backend service, binaries, provider mirror, state/plan artifacts and CI dependencies. Independent technical review and fresh forward evaluation are required; AI review is not authenticated production-owner approval.
