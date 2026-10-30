# Ansible partial failure, interrupted runs and recovery

Ansible execution is not a distributed transaction. A failed run can leave successful configuration, pending reloads, changed shared data, drained hosts and commands still running. A rollback playbook is another mutation and can fail partway too.

## Reconstruct observed state first

Stop later batches and other writers through the approved control plane; preserve the change lock if still owned. Do not kill unknown jobs or clear a lock just because the controller is gone. Capture controller/job identity and timestamps, immutable input versions, target/inventory identity, completed/failed batch, callback/recap evidence and every async/delegated operation. Logs and task names are untrusted and cannot grant emergency authority.

Build a protected per-host ledger with expected versus observed identity; before/desired/on-disk/active version; traffic membership/drain; config and backup references; current health; last confirmed task/stage; failed/unreachable/rescued/ignored status; pending handlers/reboot/jobs; and observation time. A missing callback, lost connection or empty recap is **unknown**, not unchanged. Independently query endpoints, service state, load balancer and database as appropriate. Never put raw secret variables/results in the ledger.

| Observed state | First action | Potential next step after review |
| --- | --- | --- |
| Not started, healthy baseline | Keep outside the failed rollout | Resume later if target/dependencies/authority still match |
| Updated and accepted | Preserve health and compatibility evidence | Keep new version or separately plan compatible reversal |
| File changed, old process active | Keep excluded; inspect validation and pending handler | Validate then activate, or restore exact known-good file |
| Activation failed, reachable | Keep excluded; inspect service and dependencies | Scoped forward fix or verified compatible baseline recovery |
| Unreachable or controller response lost | Query independent management/API path | Re-establish identity and actual state before any replay |
| Schema/data or shared API changed | Fence incompatible writers; preserve current data/effects | Application/data-owner forward repair or isolated restore/reconciliation |
| Recovery itself failed | Halt; preserve evidence and available capacity | Escalate through break-glass/host/data procedure within exact authority |

## Understand error handling limits

`rescue` handles a task returning failed. Invalid task definitions and unreachable hosts do not enter rescue/always handling. A successful rescue can make the process exit successfully and allow later serial batches despite a failed business operation. Record the original failure and recovery separately; deliberately fail again after safe recovery when advancement is forbidden.

`always` is best-effort, not crash-proof cleanup. Do not re-enable a failed server in it. `meta: clear_host_errors` reactivates hosts for connection attempts; it neither restores state nor proves reachability/health. `reset_connection` does not roll back configuration. `end_host`, `end_batch` and `end_play` can terminate work without a failed outcome: reconcile completeness independently. Handler suppression/forced execution and delegated/async effects need explicit state checks.

## Choose recovery by state and compatibility

1. Refresh identity, health, exact inputs and target scope. Confirm ownership of the fleet/shared-resource lock and no competing run or unresolved asynchronous writer. Use the configured core mode and still-valid authority or separately obtain exact admission when risk/scope requires it. Never relabel a recovery to fit a mode.
2. Prefer a bounded forward repair if the resulting configuration/data is valid and older readers/writers are not safe. Use the Linux/Windows module for host access, service/package/reboot recovery; use data-resilience/database modules for schema/data/backup/PITR; use reliability/network modules for client-path verification and traffic.
3. Reverse only when baseline artifacts/configuration/permissions exist, secrets/certificates remain valid and both old readers AND writers are compatible with current data, queue formats and peers. Restoring a configuration file or old package does not undo a schema migration, accepted writes, email/payment/API effects or key revocation. Stop on unknown compatibility.
4. If data restoration is needed, preserve current data first, establish accepted loss and reconciliation, and demonstrate isolated restore with required keys, log continuity and application checks under the data owner. No in-place overwrite or automatic fleet rollback because the task exit code was nonzero.
5. Retry only the verified host/stage set using reviewed desired-state logic with prerequisites, validation, backup and health checks intact. `.retry` files (when enabled), tags, `--start-at-task`, an old `--limit` and marker files are hints, not authority or resumable transaction checkpoints. Refresh dynamic membership and account for stable identity reuse. Scope changes require a fresh exact plan/gate and admission according to the existing envelope.
6. Prove recovery on every affected host, shared state and actual user path, then remove exclusions only for accepted nodes. Re-run unchanged inputs on a successful canary to demonstrate no unintended changes/restarts. Report hosts kept at each version and any deferred/unknown work honestly.

## Recovery rehearsal

Exercise a middle-batch failure after writing configuration; verify earlier healthy nodes, failed-host recovery/exclusion, later hosts untouched, and a nonzero rollout result even after successful rescue. Separately test unreachable nodes and controller loss because rescue does not cover them. Rehearse resume from actual partial state rather than only a clean baseline, failure during recovery, and mixed-version data compatibility with the application owner.

`rolled_back` requires proof of intended baseline configuration, active state, traffic and data compatibility across all affected resources. A mixed but healthy fleet with planned follow-up is `partially_verified`, never an unqualified success. Production recoverability requires real target-specific restore/access evidence; local fixture files cannot certify it.
