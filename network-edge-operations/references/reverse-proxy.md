# Reverse proxy diagnosis and staged changes

## Route and trust model

Identify actual binary/version, process identity, service/container/ingress owner, effective configuration path/includes/provider, mounts, generated source, active listeners and upstream endpoints. A file on disk is not necessarily the running config. A configuration dump can contain credentials: extract allowlisted route/TLS/timeout fields and protect raw artifacts. Dynamic provider configuration may override or merge with a local file.

Trace scheme/port, TLS SNI, HTTP Host, route priority, path rewriting/trailing slashes, upstream protocol, upstream SNI/CA, readiness and response identity. Do not assume an HTTP app speaks HTTPS, a DNS name points to the intended backend, or an IP upstream has a valid IP SAN. Preserve upstream verification with correct name/trust; `insecureSkipVerify` is not a repair. For mTLS, inventory both peer identity and secret references/rotation owners. A port-open test proves neither protocol nor application readiness.

Trust `Forwarded`/`X-Forwarded-*` only from exact approved proxy/LB CIDRs and their documented append/overwrite behavior. At the public trust boundary, strip/overwrite client-supplied identity/scheme headers as needed; do not trust `0.0.0.0/0`, arbitrary hop counts or an upstream's claim of being a proxy. Confirm real client IP and scheme without spoofing into privileged paths. Correct trusted proxies and canonical URL settings before changing redirects; restrict arbitrary Host/default-vhost routes. Keep CDN-to-origin authentication/network restrictions, admin APIs and dashboards private. Direct-origin probing needs separate approval if it bypasses that boundary; do not open it publicly for convenience.

## Discriminate 502 and 504

Correlate the emitting hop's safe error logs/timings with the exact backend and application logs. A 502 can mean connection refusal/reset, stale DNS/service discovery, no healthy backend, invalid upstream response or HTTP/TLS/SNI/trust mismatch. A 504 can mean connect/header/read timeout, queue saturation or a slow database/dependency. Compare proxy-local and outside observations using the same identity/path; check address family and network owner evidence. Diagnose resource pressure with host/container/reliability owners rather than restarting the fleet.

Check upstream keep-alive/DNS cache behavior against the actual version and discovery owner before changing resolver settings. For uploads, WebSocket, streaming and gRPC, identify body limits, buffering, protocol upgrade/HTTP2 and separate connect/header/idle timeouts. Preserve authentication, body-size and rate limits unless a concrete admitted requirement changes them. Increasing every timeout hides a sick dependency and can exhaust connections. GET retries and upstream failover can duplicate business effects when routes are not idempotent; preserve retry semantics and involve the app owner before broadening them.

## Engine-specific application

### Nginx

Use the running binary, intended prefix/config, includes, environment and worker identity to test the exact staged candidate (`nginx -t` with the confirmed config/prefix). Validate certificate/key access under the service runtime. An arbitrary default-config test says nothing about another config. Reload through the admitted service/container owner only after successful validation; observe master error logs, new workers, fresh TLS and application responses. A delivered reload signal may still leave the old config active. Preserve old config and pair references; a graceful reload preserves existing requests but worker/connection drain and resource capacity still need observation. Do not restart merely to prove that reload happened.

### Caddy

Confirm adapted effective config, service environment, data/config directories, automatic-HTTPS owner and storage permissions. Use actual-version `caddy validate --config <candidate>` (and the proper adapter for a Caddyfile), then supported reload to the protected local admin endpoint. File-based cert/key changes with otherwise unchanged config may require the documented forced reload; verify the served fingerprint instead of assuming re-reading occurred. Keep the admin endpoint private. Do not delete persistent data/ACME account state, run a competing ACME client or deploy staging certificates. Automatic HTTPS may perform network issuance or listener setup: validation/rehearsal must deliberately isolate or disable issuance for synthetic tests, not accidentally contact a public CA. Reloading a manually managed synthetic pair does not validate automatic renewal.

### Traefik

Separate install/static configuration (entrypoints, providers and other startup settings; normally requires an owner-approved restart) from dynamic routing/TLS configuration. Verify exact-version commands and provider behavior; do not invent a generic `check-config` validation command. Preflight dynamic changes in an isolated instance with no live provider credentials, Docker socket or public CA reachability, then use a canary and actual-route checks. Parse success does not prove a router/service/TLS pair was accepted: inspect provider errors and active route/fingerprint evidence.

For the file provider, mount/watch the parent directory and use a supported atomic replacement; replacing a single bind-mounted file or breaking the watched link can leave stale configuration. Observe debounce/provider errors and allow a bounded reconciliation window before claiming activation. For Docker/Kubernetes/managed providers, change their authoritative source through the owning module; do not patch generated output. Preserve certificate resolver state and use its documented concurrency/storage model; never share incompatible ACME storage writers or expose the dashboard/API. Manual certificate rotation and ACME resolver renewal are different paths.

## Acceptance

Verify every intended virtual host/path/method class, denied/default route, redirect scheme, trusted-client-IP behavior, upstream identity, strict TLS chain/SAN/expiry, both address families and required protocol behavior. Use approved bounded health requests; some GET endpoints have side effects. Syntax validation plus reload plus HTTP 200 from a default route is insufficient. For a failure after partial rollout, use [actual-state recovery](change-recovery.md), preserving healthy capacity and application/data ownership.
