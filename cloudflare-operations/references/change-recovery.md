# Conflict detection and recovery after partial effects

Preserve the current core autonomy, risk floors and protected execution/journal contract. Existing valid authority may cover a new exact plan inside its envelope; changed target, scope or effects need the appropriate admission. These helpers inspect data and never grant authority, acquire a provider lock or execute provider writes.

## Per-effect record

Before changing anything, record account/zone, owner, configuration source, object ID, current native version/deployment ID where available, canonical configuration fingerprint, full ordered snapshot, exact request digest, intended result, dependencies and observable acceptance. Record each object separately as `not_started`, `launch_intent`, `response_received`, `outcome_unknown`, `observed_intended`, `observed_before`, `conflict`, or `verified`. Record immutable provider IDs and external-effect receipts where available. A client timeout or missing journal outcome means unknown, not failed.

Serialize the actual writers using the source-of-truth owner's mechanism. If no documented provider atomic conditional write exists, a read-compare-write still has a race: do not invent `If-Match`, version parameters or transactional batches. Stop conflicting writers, narrow the change and compare the exact object immediately before each effect and each compensation. A native version can change while configuration returns to its former value; that history still matters.

After disconnect, 429, 5xx, process failure or partial batch completion, stop progression and re-read before retry. Respect documented rate-limit delay for read-only recovery; do not automatically replay a mutation on a retryable HTTP class. Reconstruct actual object versions, associations/order, routes, traffic and external effects. An idempotency key in a local record does not make an unsupported provider operation idempotent.

| Observation | Decision |
|---|---|
| Exact former version/configuration, no unknown external effects | May prepare a bounded resume; re-admit the exact plan as required |
| Intended configuration and new provider version | Verify it; a lost response is not a reason to repeat it |
| Some intended, some former objects | Partial operation: preserve functioning capacity and reconcile each effect |
| Third configuration, unexpected version or incomplete read | Conflict/unknown: stop writes and involve the other owner |
| Recovery candidate incompatible with present data/resources | No automatic reversal; choose owner-led forward repair or proven isolated recovery |

Compensate only still-owned effects whose present exact fingerprint matches the operation's recorded applied state. Apply inverse operations in dependency order chosen from the actual path, not blindly in reverse command order. Successful compensation needs new version IDs, complete effective configuration and service/security acceptance. If compensation fails, preserve the stable subset, prevent further rollout, keep evidence and escalate. Do not label a failed restore `rolled_back`.

## Offline snapshot guard

From the source/runtime root, use `python cloudflare-operations/scripts/state-guard.py preflight before.json current.json`, `reconcile before.json intended.json current.json`, or `rollback-preflight applied.json current.json`. Inputs are local reviewed snapshots, not raw API responses. Exit 2 means invalid/ambiguous input; exit 3 means drift/conflict/partial state. Exit 0 is a comparison result, not permission or service acceptance. `before_configuration` is an observation and never asserts a retry is safe.

The strict snapshot shape is:

```json
{
  "schema_version": 1,
  "product": "waf",
  "account_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "zone_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "objects": [{
    "resource": "zone-ruleset",
    "id": "synthetic-ruleset",
    "revision": "17",
    "configuration": {"phase": "http_request_firewall_custom", "rules": []}
  }]
}
```

Use exact native revisions when present; for Access/no documented revision, use a canonical fingerprint of the complete observed configuration and label that limitation in the effect record. Normalize all compared snapshots consistently, excluding only reviewed provider-generated timestamps; include all material fields, ordered policy/rule/ingress lists and settings relevant to scope. Keep unchanged neighboring objects too: a revision change there must block. `intended` contains the planned configuration with the same inventory; a newly created object is a separate effect that cannot be compared until its identity is known. Unknown server-assigned IDs, incomplete pagination or missing settings cannot be filled with guesses.

The guard checks target/inventory, full revision/configuration digests and before/intended/third-state classifications. It neither validates Cloudflare expressions/policy semantics nor proves snapshots are complete, authentic, recent or taken under an exclusive lock. All comparisons depend on operator-controlled evidence; hashes alone prove neither recovery nor identity. Keep configuration/PII evidence private and out of the repository. Known literal credential fields are rejected, but this is not a complete secret scanner or redactor.
