# TLS certificate lifecycle and recovery

## Diagnose the certificate actually served

Map client → CDN/load balancer → ingress/proxy → TLS upstream, including every IPv4/IPv6 endpoint and fleet member. Perform a fresh connection with the intended SNI (TLS hostname) and verify the SAN identity, validity against a trusted clock, leaf fingerprint/serial, issuer, intermediate chain and approved trust roots. Do not use the legacy Common Name as a substitute for SAN validation or disable verification to obtain a green result. Record public leaf fingerprints and key references; never copy private keys/account credentials into evidence. Browser caches, reused TLS sessions and a single healthy load-balanced node can hide a stale deployment.

Classify expiry/not-yet-valid, wrong SAN/SNI, missing intermediate, untrusted private CA, mismatched certificate/key, unsupported algorithm/client compatibility and upstream mTLS separately. A supplied private CA file must come from the approved trust owner, not an error page. Check revocation/CT policy where the target requires it; a generic successful handshake does not prove those controls. Verify private key/certificate public-key equality with algorithm-neutral SPKI/public-key comparison; an RSA-only modulus recipe does not cover EC/EdDSA keys. Do not print key material. Keep fullchain ordered leaf then intermediates; sending a root does not make an untrusted issuer trusted.

## Renewal and issuance

Inventory the actual issuer/ACME client version, account and endpoint, certificate lineage and SANs, renewal scheduler/timer, last attempt/next due, owner, credential references, storage/mounts, permissions, durable ACME account state, deploy/reload hooks and monitoring thresholds. Confirm whether Caddy/Traefik/another controller already owns renewal. Do not run competing clients or erase ACME state to force issuance. Account storage and DNS API credentials are secrets; do not mount them into unrelated validation containers.

Inspect CAA, relevant A/AAAA and authoritative/recursive challenge answers, clock, outbound CA reachability and rate-limit/retry instructions before requesting another order. A failed deployment should normally reuse the valid issued pair, not create repeated new orders. Refresh the actual CA limits and renewal/ARI support; never hardcode current quotas or assume revocation resets a limit. Test client configuration with the CA's staging endpoint first when applicable; staging accounts and roots differ and staging certificates must never replace production certificates.

| Challenge | Required route and ownership |
|---|---|
| HTTP-01 | CA-reachable TCP 80 and exact challenge path/content on every selected A/AAAA/frontend; inspect redirects, auth/WAF and proxy route. Do not disable the entire WAF/auth boundary or expose the application to fix one challenge path |
| DNS-01 | Exact `_acme-challenge` authority/delegation and least-privileged TXT update credential; preserve concurrent challenge values, wait for authoritative visibility and relevant caches, remove only this order's value. Wildcards require appropriate DNS validation |
| TLS-ALPN-01 | Actual TLS 443 terminator and supported temporary ALPN response; ordinary TLS passthrough/another proxy may prevent the ACME client from answering. Coordinate the terminator owner |

A local challenge response or successful staging order does not prove CA-visible production validation. Use bounded attempts and stop on repeated rate/auth/propagation failures. Do not change delegation/CAA or create broad DNS credentials under a routine renewal approval. Avoid outage-producing manual stop/start issuance unless that downtime and recovery route are explicitly in scope.

## Stage and activate a pair

1. Obtain an owner-controlled versioned directory or secret version with certificate, fullchain and matching key, minimum permissions and approved algorithm/SAN/expiry. Verify pair, chain and trust without mutating active paths. A renewal is not complete until the served certificate is verified.
2. Build an exact candidate referencing an immutable **pair**. Do not overwrite cert and key independently while a watcher/reload can observe a mixed version. Use the target's supported atomic switch of the parent/config/secret reference; confirm container mount, file watcher and reconciliation behavior. Test candidate with actual runtime identity, includes and private-key read permissions.
3. Preserve the current active config and usable prior pair refs, ownership and restoration procedure. Coordinate renewer/deployer locks and invalidate stale candidates. Stage on a canary, validate, then reload/restart only as supported for the actual proxy/version and admitted service window.
4. Inspect fresh strict-TLS handshakes and leaf fingerprints at every relevant endpoint/terminator, plus application health, error rates and logs. Record which nodes still serve the old pair and which routes remain unchecked. Observe new connections and existing connection drain separately. Never widen from an unverified/mixed outcome.

## Failure and recovery

If validation fails, leave active references untouched. If activation is partial, freeze progression, inspect per-node disk references **and actual served fingerprints**; restore or repair only the confirmed affected nodes with a fresh plan. A successful reload signal/command is not proof the master accepted the new config or every worker/node serves it. Keep healthy capacity and an out-of-band route.

Restore a prior certificate/key pair only when it is still valid, trusted, uncompromised and suitable for current names/policy. Expired, revoked or compromised old keys cannot become a recovery target. For key compromise, involve the security/CA owner: replace key material and affected account/DNS credentials as indicated, deploy a clean pair, coordinate revocation and audit remaining endpoints. Revocation is a separate irreversible action with explicit admission and may disrupt clients; do not erase the only usable recovery route blindly. If no safe pair exists, use an approved maintenance/traffic restriction or forward repair, never disable TLS validation. A client-side trust-store change, public issuance, revocation and DNS credential rotation each retain their responsible owner and scope.
