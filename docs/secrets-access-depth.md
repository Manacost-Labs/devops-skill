# Vault access lifecycle scope and evidence

Secrets-access-operations 0.4.0 adds concrete HashiCorp Vault service-token and KV v2 procedures. It covers finite grants and wrapped delivery, observed expiration, consumer rotation, partial and ambiguous recovery, exact token/lease revocation, reissuance and existing-session containment, emergency grants and generated-root handoff. It requires core/contracts 0.7.0 or newer and follows their protected execution boundary: local v2 plans/gates are consistency data; actual execution uses registered task IDs and typed parameters over mTLS with externally signed finite authority. Risk, recovery, separate exact admission and separation-of-duties retain their existing owners. See [protected execution](protected-execution.md).

The skill supplies procedures and an explicit provider contract. It does not bundle a production Vault executor, registered Vault tasks or real broker integration. Organization-owned protected providers perform secret-bearing operations internally and return finite structured metadata and opaque references. Missing protected transport, registered tasks or signed authority is a blocked handoff; arbitrary argv and new execution allowlists are not supported. Other stores/brokers require their own provider procedures.

## Native CI

The **Vault / grants rotation revocation expiry** job downloads Vault 1.20.4 from the official release host, checks its committed SHA-256 before extraction/execution, verifies the running server's version and uses an owned dev-mode in-memory server on a random IPv4 loopback port. The server has no production address or credential inputs. A random synthetic root token reaches only its child-process environment; `-dev-no-store-token` disables token-helper persistence, server output is discarded, and a private temporary home prevents use of operator configuration. API values, wrapping tokens and synthetic user passwords remain in fixture memory. HTTP proxy settings and redirects are disabled, and responses/errors are bounded and never printed.

Real Vault API checks exercise:

- A finite nonrenewable grant with an explicit lifetime ceiling, intended access and denied unrelated access.
- Response wrapping and one-time unwrap, with wrapping lifetime distinct from the enclosed grant.
- Two token consumers split between old/new references after an injected delivery failure, resumed activation, exact old-token revocation and continued new access.
- KV v2 CAS conflict rejection, version-pinned reads, reversible soft deletion and retention of a previously copied value.
- Accessor revocation of a parent and its derived token.
- Successful fresh userpass login after revoking an old session, then denial of login after deleting that synthetic user while an existing session remains active until separately revoked.
- A restricted finite emergency token, denied unrelated access, explicit closeout and surviving recovery access.
- Actual expiry followed by denied access, denied renewal and no remaining accessor lookup.

An unavailable download, checksum mismatch, unsupported platform, failed server startup or failed API assertion fails the job. Native checks do not silently skip. The fixture also supports an explicitly invoked Windows x86_64 run with its own official archive checksum. Ordinary regression discovery executes bounded unit checks without downloading/launching Vault; the separate native CI job supplies actual-engine evidence.

## Limits

The partial consumer delivery failure is injected in the fixture's in-memory reference map. Authentication on both sides and revocation are actual Vault operations; no application process, pool reload, distributed deployment controller or business transaction is claimed. KV deletion demonstrates storage semantics and retained copied data, not revocation of an external password. Native tests do not configure a database/cloud secrets engine, terminate real backend sessions, test batch/periodic tokens, renewal agents, audit-device durability, TLS/mTLS, namespaces/replication/HA, workload identity federation, production broker integration, or root-generation quorum/recovery. Procedures and independent forward evaluations cover these decisions; target-owner rehearsals supply operational proof.

Vault 1.20.4 is a fixed compatibility fixture, not a supported-production-version recommendation. The official documentation defaults to a newer major; refresh the exact server/engine/auth API before a real change. The release-time freshness mapping checks source ownership, age and capability coverage; it cannot prove provider semantics.

Run full platform/skill validation, cross-platform regressions, package/export verification and secret scanning alongside the native job. Test fixtures and downloaded executables are source-only and do not enter runtime archives. Report `partially_verified` when downstream, audit or consumer evidence is missing; AI technical review does not impersonate an authenticated production approver.
