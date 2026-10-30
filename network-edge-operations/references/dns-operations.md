# DNS diagnosis, caches and cutover

## Establish authority and the client view

Identify the exact FQDN, zone boundary, account/provider, primary/secondary authorities, registrar/delegation owner, intended RRset and resolver/view used by affected clients. A recursive resolver answers from a cache or follows delegation; an authoritative server owns a zone's answer. An answer at one recursive resolver is not proof of authoritative state or worldwide propagation. Use approved resolvers and bounded queries, compare TCP/UDP where transport/truncation is suspect, and collect RCODE, AA/AD flags, answer/authority sections, TTL and observation time. AD is a resolver assertion, not independent local DNSSEC validation.

Compare parent NS/glue with child apex NS/SOA and answers from every authoritative server. Stale secondary serials, lame delegation, unreachable UDP/TCP 53, glue errors and inconsistent authority can produce intermittent failures. Do not change registrar NS/glue or disable DNSSEC as a first diagnostic step. Parent/child ownership and their different cache lifetimes require coordinated plans. A recursive trace is sensitive to its execution network and cannot replace the failing client's view.

Trace A **and AAAA**, each CNAME hop, aliases/provider flattening behavior, split-horizon/private zones and search suffixes. Preserve hostname identity while probing a numeric endpoint. A working IPv4 path does not accept an IPv6 route; a stale AAAA can explain only some clients failing. Confirm CNAME coexistence/provider-specific apex rules before edits. Never delete an entire RRset or unrelated TXT entries to remove one stale value.

## Interpret failures before mutation

| Result | Meaning and next check |
|---|---|
| NXDOMAIN | Name does not exist in that view; inspect authoritative answer and SOA negative-cache lifetime, delegation/view/typo |
| NOERROR with no requested type (NODATA) | Name exists without that RRtype; do not interpret as NXDOMAIN or delete other types |
| SERVFAIL | Resolver could not complete/validate; compare authoritative reachability, DNSSEC validation, signatures/clock and delegation; never infer missing name |
| Timeout/truncated response | Client-to-resolver versus resolver-to-authority transport, TCP fallback, firewall, EDNS/MTU and authority load |
| Inconsistent positive answers | Authority/serial/view mismatch, geo/weighted routing, recursive caches, stale serving or separate A/AAAA paths |

For DNSSEC, distinguish parent DS, child DNSKEY and signed RRsets/RRSIG validity; validate with the responsible DNS/DNSSEC owner and the actual resolver. Expired signatures, stale DS after key rotation or broken trust chains need a coordinated repair with recovery access. Do not remove DS, rotate signing keys or restore a stale signed zone under an ordinary A-record plan. These can break the whole zone and cross destructive/irreversible admission boundaries. CAA controls certificate issuance; inspect effective issuer/challenge policy through aliases before changing CA or deleting restrictions.

## Bounded record changes

Capture exact old RRset, TTL, zone/account/version/serial where available, owner, target endpoint health, DNSSEC/CAA/delegation dependencies and conditional-update/transaction support. Exclude secret TXT payloads from public evidence. Check concurrent controllers (external-dns, IaC, provider automation); use their source of truth or coordinate a lock, not an unmanaged patch that is immediately reconciled away. Refresh state and invalidate the candidate after drift.

For a planned cutover, lower TTL **in advance** and wait out the previous TTL before relying on the shorter one. Negative caches use the SOA-derived negative TTL; creating a name does not immediately erase earlier NXDOMAIN caches. Provider edge caches, resolver serve-stale/minimums and long-lived client connections can extend the observed transition. Establish a supported overlap/drain window and keep both destinations safe for traffic; DNS weights do not prove uniform client distribution. Avoid a DNS cutover when only a proxy fix is needed.

Validate candidate destinations, IPv4/IPv6, TLS identity and application/data compatibility before the provider-owner applies the exact record diff through the core gate/journal. Preserve unrelated records; prefer conditional updates and a small canary where provider semantics support it. Observe every authority and representative recursive/client vantages over the agreed window. Record mixed old/new traffic and health separately.

Rollback restores the approved prior RRset only if the old destination is still safe and compatible with current data. Reverting DNS does not flush existing caches or sessions. Keep both sides operational or restrict traffic through an approved owner-controlled path until the actual cache/drain window passes. If old service/data is incompatible, freeze progression and coordinate forward repair or data recovery; never direct traffic to it merely because it was the previous IP. Registrar transfer, delegation, DNSSEC and zone deletion require separate owner-specific recovery, not the ordinary record rollback recipe.
