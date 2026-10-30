# Cloudflare operations depth and verification scope

Cloudflare operations 0.4.0 adds detailed Access policy/path precedence and reusable-policy consumers, WAF phase/order and complete-update semantics, local/remote Tunnel ownership with independent configuration/connector/DNS effects, and Worker version/deployment/external-data compatibility. Every product has explicit conflict, unknown-response, partial-change and compatible recovery decisions. Core 0.7 protected tasks, finite signed authority and production risk floors remain the execution boundary; no generic provider write executor or new global hook exception is added.

The offline `state-guard.py` compares operator-supplied target-bound snapshots. It preserves ordered lists, detects native revision changes even on unchanged neighboring objects, distinguishes former/intended/partial/third states and refuses stale compensation. It does not interpret Cloudflare policy expressions, acquire a provider lock, guarantee snapshot completeness or authorize retry. No client-side fingerprint is described as atomic CAS.

The optional `capture-readonly.py` verifies the exact zone/account and GETs one fixed product endpoint. It ignores ambient proxies, follows no redirects, retains default TLS verification, bounds response bytes/socket inactivity and suppresses raw provider errors. It refuses contradictory returned object identities, malformed product shapes, duplicate/non-finite JSON and known credential fields, and writes a new private receipt exclusively. It records one response with pagination metadata; it is not a complete inventory, a redactor or an effective-policy test. Native managed runtime policy may require an administrator-registered observation task rather than a direct invocation.

## CI and live evidence matrix

The independent **Cloudflare / offline recovery and API transport** jobs run on Python 3.13.5 on Ubuntu and Windows for every PR/push to main. They require no Cloudflare token and never skip for absent credentials. They exercise actual loopback HTTP transport plus deterministic adversarial snapshots: all four product payloads, mixed partial effects, lost-response reconciliation, wrong target/inventory, version-only/third-writer drift, stale compensation, ordered rules/ingress, invalid API response identity/schema, redirects, oversized/duplicate/non-finite responses and safe error output. Synthetic HTTP returns test data; it never contacts the real provider or claims provider behavior.

| Acceptance area | Repository evidence | Live account status |
|---|---|---|
| Version/configuration conflicts and partial effects | Offline state comparisons and negative controls | Not run: account unavailable |
| API request/response handling | Unit tests and real loopback GET/redirect/error transport | Not run: no live token/profile |
| Access effective path, IdP/session and allow/deny behavior | Detailed procedure and evaluation cases | Not run: account/test identities unavailable |
| WAF expression/phase/order and rate-limit enforcement | Detailed procedure and synthetic ordered snapshots | Not run: provider entitlement/traffic unavailable |
| Tunnel connector propagation, origin and DNS recovery | Detailed procedure and partial-effect fixtures | Not run: account/connectors unavailable |
| Worker deployment/split and compatible recovery | Detailed procedure and synthetic version/binding snapshots | Not run: real version/runtime/storage observations unavailable |

The [test-account drill](../cloudflare-operations/references/test-account-drill.md) is a concrete phase-by-phase live procedure with prerequisites, identities, failure injection, acceptance/evidence and owned cleanup. An operator must provision a disposable non-production account/zone and register the exact admitted mutation tasks before running it. No public CI workflow stores provider write credentials or auto-deploys a PR into an account. Missing live phases remain `partially_verified`, even when all repository checks pass. Do not fill this matrix with synthetic receipts or treat an API HTTP 200 as recovery proof.
