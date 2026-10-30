# Terraform/OpenTofu state, backend identity and locks

## Establish ownership before initialization

Record engine/version, repository/root revision, backend type, exact endpoint/account/project/region, bucket/container/object key or remote workspace ID, CLI workspace and state lineage/serial/native version. A name such as production is not evidence of account or isolation. Inspect environment, CLI arguments, partial backend configuration, cached initialization, workspace prefixes/key layouts and provider aliases against the approved target. Do not create a missing workspace to make a command proceed.

Backend credentials control stored state; provider credentials control real infrastructure. Confirm both identities independently. Inventory cross-state consumers and shared objects: remote-state access can reveal the underlying snapshot, beyond intended outputs. Avoid two states owning the same real object; their separate backend locks cannot coordinate those writers.

Treat engine/provider-registry transitions as a separate reviewed change: selected versions alone do not establish identical packages or addresses. OpenTofu can rewrite Terraform registry lock entries; verify intended source, release bytes/signers and platform hashes before using a new lock. Mirrors need usable unpacked-package hashes as well as verified archive provenance; never remove readonly/checksum safeguards to silence a cache mismatch. Generate needed platform entries only from a reviewed origin or already verified mirror and review the lock diff.

The `.terraform/terraform.tfstate` initialization cache is not necessarily the managed-resource state and can hold backend settings/credentials. Saved plans can embed backend configuration too. Use protected credential references/environment, not literal secrets in backend arguments/files. Never publish raw state/pulls, plan/show JSON, backend caches, crash logs or recovery state. Sensitive flags only affect selected displays.

## Protect recovery and compatibility

Verify authenticated transport, encryption, restricted access, native versioning/snapshots and effective locking for the actual backend. Remote storage does not imply locking. Current Terraform S3 supports opt-in `use_lockfile` and deprecates DynamoDB locking; check OpenTofu's exact version/options separately. During transitions all writers need compatible lock coverage: old/new clients must not silently lock different mechanisms. Route cloud IAM/storage semantics to its provider owner.

Before state surgery/migration preserve the current backend-native object version, protected snapshot/checksum, lineage/serial, exact resource/provider bindings, encryption/key references and independently retrievable recovery path. Back up source and destination when either has state. An encrypted snapshot with unavailable keys is not recoverable. OpenTofu state/plan encryption is a separate engine feature: test rotation, fallback and restoration on an isolated copy; never silently fall back to plaintext or assume Terraform compatibility.

## Contention and stale locks

Keep native locking enabled and use bounded `-lock-timeout`. Identify the exact backend/workspace, lock nonce, operation, owner/executor/run, creation time, lease/version behavior and current controller/provider activity. Gather read-only remote-run/CI status, process ownership and long-running provider job evidence. Age, possession of an ID, local terminal exit or a failed CI job is insufficient stale-lock proof.

Prefer waiting for the owner or graceful cancellation followed by reconciliation. A first interrupt may allow completion/persistence; another interrupt/kill can lose the final write while provider jobs continue. Do not stop an unknown writer merely to obtain a quiet plan. Keep timeout/contention outcomes visible in the journal.

Force-unlock only the exact proven-stale lock on the confirmed state after fencing all possible writers and reconciling in-flight effects, with at least R3 admission under the existing core mode/authority. Unlocking is not rollback and cannot prevent an old executor returning; prove fencing through actual job/credential/backend controls. Never delete a lock object/table row or switch engines as a shortcut. Re-read the native state/version and make a fresh full plan afterward. Local filesystem locks and remote lock services have different recovery behavior; test the actual backend.

Verify the client/backend actually enforces the nonce. In native CI the pinned Terraform 1.17.1 HTTP client sends no lock payload from a fresh force-unlock process, so the strict fixture refuses even the supplied correct ID; pinned OpenTofu 1.13.2 sends it and can release only the matching lock. Do not relax the backend or substitute another engine to bypass this gap. Leave the operation blocked and hand off to the backend owner for a separately reviewed exact-identity recovery mechanism, with real stale-writer/fencing proof. This is a tested HTTP/version boundary, not a claim about all backends or future releases.

## Migration and binding changes

`init -reconfigure` accepts new backend settings without copying old state. An empty destination can therefore make existing resources appear unmanaged. `init -migrate-state` attempts a copy and can need confirmation; `-force-copy` is not a routine repair flag. Review source/destination identities, all workspaces, writer fencing/locks, protected versions, destination ownership, engine/encryption compatibility and post-copy verification. Retire old-writer access after cutover; do not let both locations become authoritative. After a lost copy response inspect both sides before retrying.

Migration does not universally preserve lineage/serial: metadata preservation depends on both state managers. Both pinned HTTP fixtures copy exact resource bindings but generate destination metadata. Record source/destination native versions, lineages and serials and prove object/binding equivalence; do not edit the new metadata to mimic the old one. Serial ordering is meaningful within a lineage, not across unrelated lineages. Invalidate old backend-bound plans and prepare fresh target/plan/gate evidence, with new admission if the destination exceeds the existing envelope.

For `state mv/rm/replace-provider`, import/moved/removed blocks and pushes, map exact addresses/indexes/module paths, provider aliases/schemas and real IDs. Prefer supported declarative moves/imports; review no accidental destroy/create or duplicate ownership. Forget/removal drops tracking and can leave the actual object active/billable, so later configuration may duplicate or collide with it. Import establishes an association, not configuration parity or health. Route provider/account-specific semantics to the owner.

`state push` lineage/serial checks protect against some overwrites, not against incorrect real-world state. Preserve them: no `-force`, editing lineage/serial or overwriting a newer native version to make restoration succeed. A higher serial can still describe the wrong objects. Before uploading an error snapshot reconcile current versions, original run outcome, real objects, lock, encryption and absence of intervening writers; gate the exact mutation and verify a full plan afterward.
