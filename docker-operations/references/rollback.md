# Releases and recovery after data changes

A release is image + rendered configuration + secret references + schema/file/queue formats + external dependencies. Record immutable current/candidate identities and every writer: API replicas, workers, cron/jobs, startup hooks and migration jobs. Tag names, container health and an old Compose file cannot establish data compatibility.

## Decide before rollout

Produce an application-owner-reviewed compatibility matrix: old/new reader and writer versus pre/post-migration data, queue payloads and object/file formats. Identify irreversible steps and the last safe point to switch back. Unknown compatibility blocks automatic rollback.

| Current facts | Permitted decision path |
|---|---|
| No persistent/external change; old config/dependencies still valid | Bounded image/config reversal with client verification |
| New schema/format remains proven compatible with old reader AND writer | Preserve latest data; reverse only compatible application/config layers |
| Old application incompatible; repair can preserve current data | Stop further rollout and choose reviewed forward repair with current-state backup |
| Isolated recovery required | Fence all writers, restore to a separate destination, reconcile later writes/effects, then approve cutover |
| Compatibility, writers or recoverable point unknown | Contain within existing authority; preserve evidence and report blocked recovery |

Use expand/backfill/switch/contract where the application supports it. Deploy additive schema first, support mixed versions, run a resumable bounded backfill with correctness checks, move reads/writes, then remove obsolete formats only after the reversal window closes. Separate migration leadership/locking from replica startup; every new replica running a migration is not safe serialization. Down scripts can be lossy and are not evidence of reversibility.

## Failed release after new writes

1. Record migration completion/partial progress, actual schema/data version, committed writes, queue offsets/in-flight jobs, external calls and active writers. A failed process can already have committed work.
2. Stop the rollout through its source owner. If authorized, fence ingress/jobs/writers without losing necessary management and evidence. Pausing a deployment does not stop all writes.
3. Preserve current data before attempted reversal. Choose compatible app reversal, forward repair or isolated restore based on the matrix, recovery proof, achieved recovery point and time.
4. For restore, identify writes after the recovery point. Replay/transform/reconcile only through a reviewed method, deduplicate queue/job effects and handle payments/emails/webhooks with their owners. Database restoration cannot undo an external effect.
5. Test the selected application/config against restored/reconciled data and intended user actions in isolation. Measure retrieval, restore, reconciliation, cutover and observation, and report any accepted loss.
6. Approve the exact overwrite/cutover through core, fence the losing side, switch once, and verify data/security/user behavior. Preserve the original until retention permits cleanup.

Compose `up` may preserve mounts while replacing containers; that does not revert their contents. Avoid `down -v`. Keep previous immutable images/configuration and recovery artifacts available, but never execute a generic “old image then restore database” sequence. Database recovery belongs to the declared engine/method module; unsupported application/queue/volume formats need their specialist owner. A new valid plan is required when target, schema, writes or recovery choice changes.

Sources: [Compose recreation preserves mounts](https://docs.docker.com/reference/cli/docker/compose/up/), [volume lifecycle](https://docs.docker.com/engine/storage/volumes/). The compatibility and writer-fencing procedure is a platform operational requirement, not a Compose rollback feature.
