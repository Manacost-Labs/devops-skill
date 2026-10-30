# Deployment, interruption and partial-release recovery

## Admit and stage the actual release

Bind the immutable admitted payload, source/workflow/run/attempt, configuration/secret versions, target/resource IDs, exact argv/plan digest, batch schedule, finite window, lock, recovery and acceptance thresholds. Use the existing core mode/scoped authority and immediate operation gate/journal for each mutation. Production remains at least R3 and destructive/irreversible data effects retain separate exact admission; changing a covered plan is not itself a reason to repeat envelope consent.

Inspect actual healthy capacity, quorum/dependencies, mixed-version reader AND writer/schema/queue compatibility, migration ownership, backups/restore, traffic and external effects with target/data/reliability owners. Choose a named canary, a fixed observation interval and explicit promotion barriers. A matrix that launches every environment at once or a `needs` dependency without health evidence is not a safe staged rollout.

Use a shared target/resource lock across every relevant workflow/repository/controller, plus remote fencing and an idempotency key bound to target, release and intended effect. GitHub concurrency is only a scheduling control. Drain/activate/verify one admitted batch, prove real active digest/configuration and user-path health, then return only accepted nodes to traffic. Do not silently shrink missing hosts or promote on skipped/ignored/cancelled/unknown results. Keep dynamic target expansion within exact reviewed identities.

Idempotence requires observing actual external state, not just finding a completed local marker. An API timeout may hide a completed deployment/payment/migration. Query by actual operation/idempotency key and inspect target/effect state before replay. A new run attempt must not silently mint a fresh key for the same unresolved effect, reuse stale outputs or assume cancelled jobs made no changes.

## Stop and reconstruct after failure

Stop later promotion and overlapping writers through the approved control plane, preserve lock ownership where valid and keep failed targets excluded. A job cancellation/timeout or lost log cannot cancel every remote operation. `always()` cleanup must not re-enable failed traffic, delete recoverable data or declare rollback complete. Preserve relevant source/artifact/plan, logs, target observations and protected current-data/backup references.

Build a per-target/effect ledger: expected versus observed identity; old/intended/on-disk/active digest and configuration; traffic/capacity/health; actual migration/schema/writes; outstanding provider/job IDs; external effects/idempotency keys; original failure and attempted recovery outcomes; timestamps and unknowns. Capture independently from target/provider/data systems when runner evidence is missing. No raw credentials or full environment dumps.

| Partial outcome | First step | Next reviewed choice |
| --- | --- | --- |
| Upload/stage only | Verify target bytes/config and no activation/effects | Retry bounded activation after current admission/health checks |
| Some nodes accepted, one failed | Preserve successes and exclusion; reconcile remaining nodes | Scoped forward repair or compatible per-node reversal |
| API response lost or runner cancelled | Inspect actual request/idempotency/job and target state | Observe/fence/resume only after unknown effects are resolved |
| Schema committed, code failed | Preserve current data and fence incompatible writers | Application/data-owner forward repair or isolated restore/reconciliation |
| Old binary exists but old writer/queue unknown | Prove compatibility against current data/peers | No automatic rollback until evidence and admission hold |
| Recovery failed | Halt; retain current data, capacity and protected evidence | Owner-led exact recovery with remaining authorized scope |

## Rollback is a separate state-aware mutation

Use a previously accepted immutable digest only after proving compatibility with current configuration, secrets/certificates, peers, schema, queues and readers/writers. Reverting a Git commit or image does not undo migrations, accepted writes, object replacement, key revocation or payments/messages. Preserve newest data first and establish accepted loss/reconciliation before any restore. A backup's existence or a successful cleanup job is not usable recovery evidence.

Prefer a bounded forward repair where current data/state is valid and older code is unsafe. Hand Terraform/state to IaC, containers/clusters/hosts to their modules, database restore to data-resilience/database, traffic/network to its owner and observation to reliability. Do not bypass their locks/owners by embedding destructive commands in a rollback workflow.

Rerun only reconciled target/effect subsets with required validation/backup/health steps intact. Recheck current source/artifact/attempt/target, expiry, locks and exact admission. Retain the earlier failed attempt and unknowns in the ledger; a green rerun must not erase them. `rolled_back` requires observed baseline active state, traffic and data compatibility across the affected scope; mixed/unknown state is `partially_verified` or `blocked` until resolved.
