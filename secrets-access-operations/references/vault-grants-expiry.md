# Vault short-lived grants and expiry verification

Read `vault-boundary.md` first. Operations below are broker API intents, never instructions to print or paste a token.

## Issue a bounded grant

1. Choose an existing attributable auth role for the recipient. Prefer workload identity; changes to auth roles/policies are separate approved mutations. Inspect effective policies, identity-group policies and namespace, not just the requested policy names. Avoid root, broad defaults or child-token creation rights unless specifically required.
2. For a broker-issued service token, bind the token role and `POST /auth/token/create/:role_name` to exact policies, finite `ttl`, `explicit_max_ttl`, renewal policy, recipient and approved scope. Role settings can override requested options; check the returned effective grant through protected metadata. Periodic tokens can live indefinitely when renewed unless bounded appropriately; ordinary max TTL and login lifetime are not interchangeable. Batch tokens have different revocation properties and no accessor: do not promise per-token manual revocation for them.
3. Have the trusted broker deliver the credential directly to the approved recipient. If response wrapping is used, bound `X-Vault-Wrap-TTL` separately, verify expected creation path and recipient, unwrap once through the protected channel, and treat unexpected prior unwrap as possible interception. A wrapping token is itself secret material. Wrapping TTL limits delivery, not the lifetime of the credential inside; an unwrapped grant retains its own expiry.
4. Verify actual effective policy/type/TTL/renewability through a redacted provider summary. Perform one approved operation and one relevant out-of-scope operation through the recipient context. Check attribution and audit delivery before reporting the grant verified. On timeout after issuance, reconcile by broker request/operation ID and restricted accessor inventory before retrying; creating a second grant can leave the first active.

Do not select an audience field invented for the token API. Bind JWT/OIDC audience and claims at the actual auth role/issuer, where applicable; generic service tokens are bearer credentials, not universally audience-bound sessions.

## Prove expiration

1. Record issue time, returned effective lifetime, `expire_time`/explicit ceiling, allowed renewal behavior, downstream lease deadlines and the observation window. Use actual provider metadata; requested TTL and local wall-clock arithmetic alone are insufficient.
2. Before expiry, verify the bounded positive path. Identify Vault Agent/Proxy caches, renewal daemons, external schedulers and the original login path. Pause renewal/reissuance only within approved scope; otherwise monitor its actual operation and report the limitation. A token may expire while the same principal logs in again.
3. After the effective deadline plus bounded processing allowance, verify the old reference cannot use Vault and cannot renew. Have an authorized provider inspect that token by restricted accessor; distinguish invalid/absent token from denied inspection or cluster failure. Correlate authoritative audit evidence and check whether a fresh login has issued replacement authority.
4. For dynamic credentials, confirm lease revocation and denied authentication in the target service, plus termination/expiry of existing sessions with the engine owner. KV v2 values do not receive revocable secret leases; token expiry stops future Vault reads, not use of a previously fetched static password.

If a grant remains usable, stop dependent promotion and investigate renewal, clock/cluster/namespace mismatch and reissuance. Contain or revoke with the approved provider, preserve recovery access and report the exact residual authority. Never treat a failed network request as proof of denied authorization. See [token semantics](https://developer.hashicorp.com/vault/docs/concepts/tokens), [token API](https://developer.hashicorp.com/vault/api-docs/auth/token), [wrapping](https://developer.hashicorp.com/vault/docs/concepts/response-wrapping), and [leases](https://developer.hashicorp.com/vault/docs/concepts/lease).
