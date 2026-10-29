# Controller rollout is not data reversal

Capture desired and running image/config digests, deployment source, controller UID/revision, hooks/migration Jobs, operators/CRDs, schemas/file/queue versions, external effects and all active writers. Review old/new reader AND writer compatibility against pre/post-change data before choosing strategy.

## Prepare the release

Use additive schema and compatible mixed-version readers/writers when possible. Separate and serialize migrations; Jobs may retry and applications must handle partial completion/idempotency. Startup/init hooks can run on every replacement Pod. Backfill must be bounded, resumable and validated before contracting old schema. A successful migration Job or Deployment rollout is not proof all application semantics remain reversible.

Plan controller-specific behavior:
- Deployment surge/unavailable and scheduling headroom, connection draining, probes, termination and revision retention.
- StatefulSet ordered/parallel policy, partition/update strategy, per-ordinal readiness and storage identity; a template revert can require targeted recovery of a stuck bad Pod after the desired template is corrected. Do not automatically delete all ordinals.
- DaemonSet/node capacity and unavailable limits; Job retry/duplicate effects; operator reconciliation and upgrade/restore contracts.
- PDB concerns voluntary eviction paths; it is not a universal shield for controller rollouts, node failure or pressure eviction.

## Choose recovery from facts

| Data/effects now | Decision |
|---|---|
| Old app/config proven compatible with current data and dependencies | Reverse the owned source/template only, preserving latest data; verify actual revision and client path |
| Incompatible change, current data recoverable by repair | Reviewed forward repair, with a before-repair backup and explicit abort criteria |
| Restore needed | Fence every writer, isolate a compatible restore, reconcile post-point writes/queue/external effects, then approve exact cutover |
| Missing compatibility, migration state or recoverability | Stop automatic undo; preserve evidence and escalate to application/data owner |

Deployment undo restores its Pod template, not all ConfigMaps/Secrets, hooks, Jobs, CRDs, PVC bytes or external services. Helm history and Git reversion also do not reverse database commits or outside effects. A paused rollout can leave replicas, workers and CronJobs writing.

After failure, record actual schema/migration progress and newest writes first. Prevent further conflicting changes through the source owner; suspend/fence only within approved scope. Preserve current data even if an older backup is selected. Test a compatible application and restored data in isolation. Account for lost/new writes, queue redelivery, duplicate side effects, keys and endpoint dependencies. Reconcile through an application-owned method rather than blindly replaying messages.

Cutover needs one active writer set, exact target/plan digest, recovery point/loss acceptance, measured full recovery time, data/security checks and user-path observation. A route reversal after new writes is a new recovery decision. Database recovery uses the declared engine/method module; filesystem/queue/application formats need their own owner. Never restore etcd to undo an application release.

Sources: [Deployment rollback scope](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/), [StatefulSet update/forced rollback](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/), [Job retries](https://kubernetes.io/docs/concepts/workloads/controllers/job/), [disruption boundaries](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/). Compatibility, reconciliation and writer fencing are platform requirements, not controller guarantees.
