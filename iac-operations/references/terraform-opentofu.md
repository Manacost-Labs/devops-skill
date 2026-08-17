# Terraform and OpenTofu operations

## Plan identity

Record CLI version, dependency lockfile digest, repository commit, root module, workspace, backend fingerprint, provider identity, variable sources, environment variables by name only, refresh mode, target/replace/import options, and state lineage/serial. A saved plan is valid only for this complete identity.

Create a binary saved plan for execution, render a redacted review form, and hash the binary artifact. Store it as a restricted artifact because plans can contain sensitive values. Approve the binary-plan digest, not copied terminal text. Before apply, confirm the digest, target identity, source revision, dependency lockfile, state lineage/serial, and approval window still match. Apply only the saved plan.

## State and locking

Use a remote backend with encryption, access control, versioning where supported, and locking. Do not disable locking. Diagnose contention through the backend and execution owner. Before force-unlock, prove the exact lock is stale and no writer remains.

Treat state as restricted. Never print, attach, or commit raw state. Before backend migration, state push, state remove/move, import batches, or lineage repair, create a backend-native version/snapshot, record its digest/reference, and test recovery where risk requires it. Verify lineage, serial, resource addresses, provider bindings, and remote-object identity before and after.

`import` only associates an existing object with an address; it does not prove configuration parity. After import, run a full reviewed plan and reconcile configuration without overwriting live settings unintentionally. Prefer declarative import blocks when supported and reviewed.

## Drift and recovery

Use a normal refresh-backed full plan for drift detection with read-capable credentials. Classify drift as expected, unauthorized, provider-computed, or configuration debt. Do not auto-apply unexpected drift. Refresh-only operations still mutate state and require state controls.

Terraform/OpenTofu has no universal rollback. Choose among a reviewed forward fix, reapplying known-good configuration, provider-native rollback, or restoring state only when remote objects still match. Never restore old state merely to make a plan quiet.

## Dangerous patterns

- Unreviewed modules, providers, provisioners, or external data sources can execute code or disclose data.
- `-target`, disabled refresh, ignored changes, and insufficient read permissions can hide impact.
- Resource renames can appear as destroy/create unless moved blocks or exact state moves are reviewed.
- Provider upgrades can alter schemas and plans; pin and review them separately.
- Backend reconfiguration can select a different state. Confirm fingerprints before accepting migration prompts.
