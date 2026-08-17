# Access lifecycle gates

## Grant or elevation

- Bind principal, target, exact actions, reason, owner, start, expiry, and approval evidence.
- Prefer group/role assignment or brokered session over direct credential creation.
- Verify least privilege against intended tasks and incompatible duties.
- Confirm logging, session attribution, automatic expiry, and a recovery administrator path.
- Verify access with a bounded positive check and a meaningful denied-action check.

## Rotation

1. Inventory consumers by reference, never by secret value.
2. Create or activate the new version in the authoritative provider under dual control where required.
3. Update bounded references and canary consumers; observe authentication and service health.
4. Move remaining consumers, verify no use of the old version, then revoke it.
5. Record reference/version identifiers, timestamps, provider evidence, affected consumers, and rollback status without secret material.

## Revocation

- Identify dependent humans, workloads, sessions, tokens, keys, caches, and replicas.
- For compromise, contain promptly but retain a separately controlled recovery path.
- Revoke active sessions and derived credentials when supported; changing a source credential alone may be insufficient.
- Verify denied access, dependent service health, and absence of continued use in authoritative audit evidence.

## Break-glass

Require incident/change reference, named owner, dual approval, bounded scope, short expiry, monitored session, explicit closeout, credential/reference rotation when used, and independent post-use review. Provider execution must receive only opaque references and a validated v2 request.
