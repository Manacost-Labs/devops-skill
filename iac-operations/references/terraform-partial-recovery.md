# Terraform/OpenTofu partial-apply recovery

An apply is not a transaction. A failed command/controller can leave successful resources, tainted replacements, provider jobs still running, lost responses and an unpersisted final state. Reverting configuration or state does not undo infrastructure, accepted writes or external effects.

## Stop writers and reconstruct outcomes

Stop new applies and overlapping controllers/states through approved coordination. Preserve the change lock if owned; inspect native lock ownership and actual provider jobs before unlocking. Protect the original plan/digest, engine/provider/input/source versions, backend/workspace fingerprint, before/latest native state versions, current/error snapshots, CLI outcome, timestamps and request/job IDs. Never expose raw state or secrets in public tickets/artifacts.

Build a per-address ledger: prior/intended/provider ID/account/region; create/update/delete/replace/import/move outcome; actual binding/schema; active jobs; dependencies/data effects; observation time and unknowns. Missing output or a failed response is unknown, not evidence no object exists. Reconcile through provider-native reads and application/data owners before replay, association or replacement.

| Failure shape | Reconcile first | Recovery boundary |
| --- | --- | --- |
| Later task/resource failed | Persisted bindings, successful actual objects and failed/tainted identity | Fresh full plan and bounded forward repair, preserving successes |
| Response/controller lost | Provider job/request IDs, eventual state and candidate object IDs | Observe/wait or owner-led association; no blind replay |
| Backend persistence failed | Remote versions, local error snapshot, successful effects and other writers | Exact protected state-persistence recovery after fencing |
| Saved plan rejected | Actual lineage/serial/version and current source/input ownership | New reviewed/gated plan; never force old state/plan |
| Binding absent, object exists | Unique state/controller/account ownership and desired configuration | Reviewed association/import plus full plan |
| Object/data truly deleted/changed | Restore evidence, current writes and reader/writer/schema compatibility | Provider/data recovery, not state-file reversal |
| Backend cutover uncertain | Both native versions/locks/workspace maps and active writers | One authoritative owner before further writes |

## Failed persistence and recovery state

After remote persistence failure the engine can leave local recovery state, commonly `errored.tfstate`, despite successful resource effects. Its filename/existence does not establish freshness or correctness. Immediately protect its access and encrypted recovery reference; preserve checksum, lineage/serial and object IDs alongside current backend-native versions. A successful resource message does not prove backend commit; a lost upload response can conceal a successful commit.

Fence/reconcile all writers and provider jobs, compare error snapshot, latest backend state and real objects, then review/gate an exact recovery. If the backend already contains the same state, verify it rather than blindly pushing. On intervening-writer/lineage/serial conflict, stop instead of `state push -force`. Any gated push/native restore must preserve engine/encryption compatibility and ownership, followed by a protected pull and full refreshed plan. Do not discard the only error snapshot or retry apply first to erase the error.

## Forward repair versus reversal

Prefer a fresh plan against reconciled state and reality. Explain every remaining action, preserved successful object, taint/replacement and dependency/data effect. Creation-time provisioner failure can taint an object after side effects; clearing taint/replaying the script is not proof those effects were reversed. Provisioners are exceptional code execution, not recommended configuration management.

Use earlier configuration only when compatible with current infrastructure/data, and review its newly computed plan. Do not reuse an old binary plan as rollback. Restoring state rewrites bindings and can orphan/duplicate advanced resources; backend versioning is not a database/storage backup. Account for newer writes, queues, schemas, reader AND writer compatibility, credentials/keys and external payments/messages before destructive recovery, with application/data/provider owners and separate exact admission.

Reconcile orphan ownership/account/billing/attachments/data/health and other controllers before cleanup. No prefix-based mass deletion, state removal to hide a plan, bypassed lifecycle protection or broad targeted destroy. Route database/storage restores, cloud jobs, access/networking and service acceptance to specialist modules.

## Admission and completion

Keep core's mode/scoped authority, exact plan/argv/digest, immediate gate, lock, journal and usable recovery evidence. Production mutation remains at least R3; state surgery/backend migration/destructive replacements retain R4 where applicable. Do not relabel risk or ask repeatedly inside unchanged valid bounds; identity/scope/irreversible-effect/window changes can require separate admission.

Verify native versions/lineage/serial, exact bindings/schemas and actual objects, a full refreshed plan and application/data/service health. Report successful/failed/unknown addresses, orphans/jobs and protected state/recovery references. Use `partially_verified`/`blocked` for unresolved identity/persistence/data; `rolled_back` requires proof of the actual baseline and data compatibility. A zero plan alone is insufficient.
