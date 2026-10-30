# Four modes with authenticated finite authority

| Mode | Automatic ceiling in signed scope | Separate exact admission |
|---|---|---|
| Safe (default) | R0–R1 | R2–R4 |
| Balanced | R0–R2 | R3–R4 |
| Semi-Auto | R0–R3 | R4 |
| Full Auto | R0–R4 in a specifically trusted environment | Destructive/irreversible effects; hard denials remain blocked |

Production deployment remains R3. Sensitive, expensive or cross-tenant reads may
be R2+. A mode does not grant credentials, prove recovery or override policy.

## Switch through chat

Say “работай в Balanced” (or another mode). The agent discovers the actual target
and registered tasks and prepares one concrete scope card: mode, owner, target,
actions, effects, expiry, operation budget and recovery boundaries. Ask one grouped
question for genuinely missing facts. Ordinary already-authorized preparation
continues without repeated questions.

Local card confirmation selects a **planning preference only**. `PLANNING_SELECTED`
is not protected execution activation. An owner-controlled external issuer must
review and cryptographically sign the finite broker task grant. If no issuer is
connected, report that missing boundary honestly; do not simulate issuance by
calling a hook, inventing an approver, editing JSON or selecting another store.
This release supplies an offline owner signing helper, not an authenticated chat
identity provider. One owner signature covers ordinary registered tasks throughout
its finite scope/window/count, so subsequent covered steps need no new confirmation.

Native hook setup still needs real host review/trust or administrator-managed
configuration. Setup/callback markers prove only workflow observations. Instructions
alone never establish principal separation. See [native guard setup](hooks-setup.md).

## Restrict immediately

“Safe”, “работай в Safe” or “отмени допуск” needs no further approval. With the
protected runtime client profile configured, the helper sends an authenticated
broker restriction before changing local planning state. Without that profile it
reports only local planning restriction; it must not claim remote revocation.

Safe invalidates higher authority for the stable operating principal, including
certificate aliases and overlapping grants, across chats. Lower restrictions are
monotone. A fresh owner-signed grant bound to the new broker nonce can authorize
its own scope; old grants/admissions cannot restore cancelled higher authority.
Already admitted tasks require separate containment/reconciliation.

## Protected operation

The agent submits a registered task ID and bounded typed parameters. Target,
risk/effects, code hashes, fixed arguments, worker identity and recovery requirements
come from the protected registry. The broker validates mTLS identity, signer target,
mode/risk scope, real UTC expiry, policy and durable state before every launch.
Above-ceiling/destructive/irreversible work needs separate exact signed admission.

Unknown/failed effects freeze subsequent mutations. Query the original operation
receipt, inspect real state and recover under owner authority; allocating a new ID
or deleting the journal is not recovery. See [complete protected setup and client
examples](protected-execution.md).

## Migration

0.15 removes arbitrary local argv execution. Legacy planner approvals, unsigned
external-store records, session IDs, chat confirmation stdin and `DEVOPS_AUTHORITY_DIR`
are planning/consistency data, never broker authority. Reissue reviewed finite
crypto grants; do not silently migrate active permissions. No environment receives
new privileges by installation. Host/tool approvals are independent of these modes.
