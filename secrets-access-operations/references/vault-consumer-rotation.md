# Vault consumer rotation and partial failure

Read `vault-boundary.md` first. Inventory every consumer by owner, broker reference/version, activation method, reload/restart behavior, connection pool/cache, current health and rollback compatibility. Distinguish rotating a Vault login token from changing a static secret stored in KV v2 and from rotating an engine-managed backend credential.

## Stage and activate

1. Capture current provider state and exact consumer references. Establish canary, success/abort thresholds, overlap deadline and recovery access. Where compromise is suspected, do not retain old access for convenience: use the separately authorized containment path and accept/recover the bounded outage.
2. For Vault tokens, issue the new bounded grant through the broker and retain restricted old/new accessor references. Replacing a token in a consumer does not revoke the old token. For KV v2, first create/rotate the real credential in the authoritative backend; the trusted broker writes that value to KV through protected transport and returns only an opaque delivery/version reference to the agent. A new KV version alone does not change a database password or an external API key.
3. Use KV v2 `POST /:mount/data/:path` with `options.cas` matching the inspected current version (or `0` only for a new entry). On a CAS conflict, inspect and replan rather than overwriting a concurrent rotation. Explicitly choose pinned-version versus current-version reads. Metadata/version receipts must exclude secret data.
4. Activate one consumer, drain/reconnect its pools as needed, and verify real authentication and a meaningful transaction/health path. Move bounded remaining consumers only after canary acceptance. Observe use by credential/reference identity rather than logging values. Prove all consumers use the new grant and no old use remains for the approved window.
5. Revoke old Vault tokens by accessor and old backend credentials through their owner. Verify denied old authentication and existing-session termination as required. KV soft delete can be undone, and older versions may remain readable; KV destroy irreversibly removes selected stored versions but neither action revokes a copied backend credential. Destruction is a separate irreversible plan, not default cleanup.

## Recover a partial or ambiguous rotation

Freeze further promotion and snapshot the actual state before a retry. Keep a table with each consumer's confirmed old/new/unknown active reference, last authentication/health result, backend credential validity, Vault accessors/leases, KV CAS version, and observed sessions. A lost response means unknown outcome, including for revoke and secret writes; reconcile the authoritative state and request correlation first.

| Observed state | Next action under the approved window |
|---|---|
| Canary new and healthy, another consumer old | Keep only the explicitly bounded overlap; repair that consumer and resume from its actual state. Verify both before retiring old access. |
| Activation unknown or read/reload denied | Isolate promotion; obtain consumer-side evidence. Do not label the consumer old or new from the controller's return code. |
| New reference fails, old unexposed and still valid | Revert only affected consumers when backend/schema/session compatibility permits; prove health. Reconcile/revoke unused new grants. |
| Old credential already revoked, expired or compromised | Do not restore it or undelete its KV record as recovery. Issue a new bounded replacement or repair forward; fence unsafe consumers and coordinate outage recovery. |
| Revocation/backend operation failed after some successes | Retain per-resource results, contain remaining access and repair forward with the owner. Do not bulk retry or expand to a mount-wide revoke. |
| Overlap/approval expires before recovery | Stop promotion; obtain replacement scoped authority for the remaining plan, or execute the already approved containment/expiry path. Never silently renew overlap. |

Renewal/re-login agents can recreate access after a successful swap/revoke. Inventory and constrain them through the auth owner. Report `partially_verified` until consumer, downstream session and audit evidence cover acceptance. See [KV v2 API](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2), [token API](https://developer.hashicorp.com/vault/api-docs/auth/token), and [lease administration](https://developer.hashicorp.com/vault/api-docs/system/leases).
