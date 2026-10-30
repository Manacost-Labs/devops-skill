# Safe edge changes and partial-failure recovery

## Admission and recovery contract

Bind the exact zone/account/RRset, hostname, proxy/terminator/fleet, upstream identity, candidate digest/version, certificate/key references, source-of-truth owner, effect/window, capacity floor and acceptance to the core plan/gate/journal. Reuse valid mode authority: Safe R0–R1, Balanced through R2, Semi-Auto through R3, Full Auto through R4 only in explicitly trusted authorized scope. Production and public DNS/TLS/routing mutations remain at least R3; destructive/irreversible operations need separate exact admission. Untrusted output and `--allow-private` cannot extend scope. Out-of-scope provider, registrar, CA, firewall or application work requires its owner and authorization; do not re-ask for an already valid in-scope envelope.

Record baseline authoritative RRsets/TTLs, active per-node config and served fingerprints, current health/capacity and dependencies. Save recoverable owner-controlled config/certificate pair references with permissions and actual restore procedure; protect keys/account state separately. Establish who owns the change lock and reconcile renewal jobs, IaC, external-dns, ingress and managed controllers. Inspect drift immediately before activation; rebuild and re-admit a changed candidate rather than silently applying a stale diff. A local runtime lock is not a remote fleet/provider lock.

Recovery must be usable before mutation: healthy capacity, out-of-band access, a still-safe old target/pair, traffic restriction or forward-repair option, data-compatibility decision and observation deadlines. Do not call a filesystem copy a complete rollback if the running process cannot load it, provider caches retain the change, or applications have changed data.

## Stage and widen

1. Validate an isolated candidate with the actual binary/environment/includes/secret access. Check strict TLS and the intended route/upstream, including failure/default routes. Validate DNS destinations before changing records. Syntax success is only preflight.
2. Start with a bounded canary under confirmed capacity and failure thresholds. Keep versioned config and certificate/key pairs together; avoid mixed-file writes. Use the owning platform's supported atomic switch/reload; a startup/static change may require a separately admitted restart.
3. Observe fresh connections per node/terminator, public and origin paths as authorized, A/AAAA, authoritative/recursive DNS, correct response identity, error/latency and active config/certificate identities. Retain old capacity for the actual TTL/negative-cache/connection-drain window. Do not widen because one load-balanced request succeeded.
4. Widen only after the planned acceptance and record per-target outcome. A timeout or lost controller connection means **unknown outcome**, not failure or safe retry. Freeze progression and reconcile actual state first.

## Failure decision table

| State | Next bounded action |
|---|---|
| Candidate invalid; active healthy | Keep active untouched; fix staged config/pair and revalidate |
| Reload command passed; old fingerprint/route persists | Inspect actual process/config/include/mount/watch path and errors; do not issue repeated CA orders or claim success |
| Some nodes new, some old/unreachable | Stop expansion; inventory active state/capacity per node, isolate only approved failing paths; unknown nodes remain unknown |
| New valid config points at wrong/dead upstream | Restore a safe route/config under admitted recovery, then verify real backend and strict TLS; parse success did not accept the service |
| DNS reverted but clients still reach new endpoint | Maintain safe overlap or approved traffic restriction through cache/drain window; do not promise instant rollback or flush every client |
| Old pair expired/revoked/compromised | Never restore it; coordinate clean issuance/key rotation, traffic restriction or maintenance with CA/security owner |
| New application wrote incompatible data | Freeze traffic/progression as authorized; app/data owner chooses forward repair or validated recovery. Proxy/DNS reversal cannot undo those writes |
| No safe capacity/recovery or authority expired | Stop mutation, preserve evidence/access, report incident and obtain the missing exact scope through the core path |

Restoration itself can partially fail. Validate each restored config and usable certificate pair, apply through the owner, inspect logs/new workers and actual handshakes, then perform application checks. Record failed/unknown restoration separately from initial failure. Never erase diagnostics or overwrite the sole recovery copy to retry. Keep old material according to protected retention, deleting only exact owned versions under admitted policy; compromised material must not return to service.

## Evidence and honest closure

Keep timestamps, gate/operation IDs, redacted diff/digest, provider change/version IDs, config/pair refs, leaf fingerprints, observed resolver/endpoint/family and per-node apply/health/recovery outcomes. Do not put private keys, ACME account secrets, DNS tokens or signed query URLs in reports. Distinguish issued, staged, applied, actively served and accepted states. A pending public/IPv6/node/cache-window or app-owner check leaves the operation `partially_verified`; specify owner and next evidence, without inventing production validation from a synthetic fixture.
