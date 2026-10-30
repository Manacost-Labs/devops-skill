# Vault scope, preflight and evidence

These procedures cover HashiCorp Vault service tokens and KV v2 consumer references. Dynamic database/cloud credentials require the engine owner as well as Vault; Vault approval alone does not authorize mutations in that system. HCP, Enterprise namespaces/replication, auth plugins and server versions can alter the execution path. Discover the actual cluster and version rather than extrapolating from the native fixture.

## Establish the target and provider handoff

Record the accountable owner, cluster identity, namespace (including whether it is the root namespace), TLS name/trust, mount path and accessor, engine version, auth mount/role, principal/entity and policy references. Confirm auth-method, mount and role TTL ceilings, service versus batch token type, parent/orphan relationships, periodic renewal, consumers, derived leases, caches and existing backend sessions. Bind the planning dossier and finite requested window to these facts. Local v2 requests, planner/gate results and unsigned approval JSON are consistency/planning data, never execution authority. A mode envelope does not extend a credential's approved lifetime.

Resolve approval and recovery references before any grant, revocation or rotation. Production privileged access and break-glass retain dual control. A disconnected/sealed/wrong-namespace cluster, denied inspection, stale inventory or missing consumer owner is unknown state, not an empty inventory. Stop mutations and provide a handoff if facts or protected access are missing.

The installed module has no production Vault API executor or registered Vault task implementation. Read the installed core [autonomy rules](../../devops-core/references/autonomy-modes.md), [contract migration](../../devops-platform-contracts/references/contract-v2.md) and [protected deployment](../../docs/protected-execution.md). Actual execution accepts only registered task IDs and typed parameters over the separately protected mTLS broker, under externally signed finite authority and any separate exact admission required by policy. Target, risk/effects, fixed code, worker identity and recovery constraints come from its administrator registry; the agent cannot redefine them. Never route Vault through arbitrary argv, a shell fallback or new execution allowlists.

Use the planning dossier to prepare the accountable owner's provider/task handoff with:

- Exact cluster/namespace, mount/auth/role and principal references; bounded endpoint operations and affected resources.
- Planning policy/plan/operation bindings; required broker audience/registry/task scope, finite signed authority, separation-of-duties evidence, lock, recovery and stop conditions.
- Input/output secret references, approved recipient channel, and positive/denied-path acceptance checks.
- A per-step outcome record including ambiguous requests, revocation/renewal deadlines and the next safe action.

If the protected provider, registered task or authenticated external issuer is missing, return `blocked` with those missing capabilities and the safe next preparation step. Do not manufacture signatures, register a permissive task or claim that local gate success activates access. Existing valid signed authority can cover ordinary registered steps within its finite scope without repeated confirmation; it does not bypass hard denials or separate exact admission.

Require strict TLS, attributable execution, an approved audit sink and protected in-memory credential transport. The broker places values in request bodies/headers internally and suppresses secret-bearing responses before returning evidence. Never put token IDs, wrapping tokens, passwords, unseal/recovery shares or OTPs in chat, argv, files, debug traces or an operation digest. Accessors cannot authenticate but can enable revocation and reveal metadata: keep them in the restricted broker and expose opaque references. Lease IDs and secret paths can reveal identities; restrict/redact them too. The agent must not run a CLI that prints an issuance, lookup or unwrap response and then attempt to redact it afterwards.

## Evidence and completion

Record UTC observation times, discovered version, target fingerprint, owner/actor, approved role/policy and accessor/lease/version references, actual effective TTL/expiry, each consumer's activated reference, checks and rollback/containment result. Never retain full Vault JSON: even lookup-self includes the token ID. The provider returns an allowlisted metadata summary and outcomes, not arbitrary request/response bodies, error strings or secret hashes.

A successful API response proves only that step. Require observed intended access and meaningful denied access, consumer health, stopped old use and post-expiry/revocation checks. Poll within an approved bounded observation window; authorization failures, transport failures and absent audit data are distinct outcomes. Missing downstream, audit or renewal evidence yields `partially_verified`; unresolved target/authority/transport yields `blocked`. `rolled_back` requires observed recovery, and never means an exposed credential has become safe again.

## Official baseline

Reviewed 2026-10-30: [token API](https://developer.hashicorp.com/vault/api-docs/auth/token), [token semantics](https://developer.hashicorp.com/vault/docs/concepts/tokens), [leases](https://developer.hashicorp.com/vault/docs/concepts/lease), [KV v2 API](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2), [response wrapping](https://developer.hashicorp.com/vault/docs/concepts/response-wrapping), [lease administration](https://developer.hashicorp.com/vault/api-docs/system/leases), [generate-root API](https://developer.hashicorp.com/vault/api-docs/system/generate-root), and [root generation](https://developer.hashicorp.com/vault/docs/commands/operator/generate-root). Documentation currently defaults to a newer major; refresh the exact operation/version before a material change. Native CI pins Vault 1.20.4 using the [official release checksum file](https://releases.hashicorp.com/vault/1.20.4/vault_1.20.4_SHA256SUMS). This compatibility fixture is not a recommendation to deploy that version.
