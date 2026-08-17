# Bounded edge change playbooks

## DNS

Read the exact record by ID and verify zone, name, type, content, TTL, proxy status, and ownership. Capture the previous record and authoritative answer. Patch only intended fields. Verify authoritative and external resolution, proxy behavior, TLS, application health, and that the origin did not become directly reachable.

## Cache

Identify stale cache keys and custom-key headers. Prefer the narrowest supported purge: URL, cache tag, hostname, then prefix. Estimate refill load and origin capacity. Verify only intended objects were refreshed and watch origin errors, latency, and egress. Use purge-everything only with explicit zone-wide scope and refill controls.

## WAF and rate limits

Capture the entry-point ruleset, phase, version, rule IDs, order, actions, expressions, and exceptions. Test expressions with representative traffic and confirm plan entitlements. Prefer log/managed-challenge staging where policy supports it. For rate limits, record baseline, characteristics, counting behavior, period, threshold, mitigation timeout, and cached-request behavior. Verify blocked, challenged, allowed, and trusted automation paths.

## Access

Capture application paths, policy actions/order, Include/Require/Exclude selectors, session settings, IdP dependencies, service-token consumers, and emergency administrator path. Test named allowed and denied identities with the policy tester plus a live user path. Never broaden to Include Everyone or Bypass to resolve an authentication incident.

## Tunnel

Capture tunnel UUID, connector IDs/versions/health, ingress order, catch-all rule, public/private routes, DNS records, and upstream endpoints. Validate configuration before rollout. Keep at least one healthy connector and a known-good route. Verify Cloudflare-to-connector and connector-to-origin health; hand host firewall or `cloudflared` service changes to the owning module.

## Workers

Record configuration source, bundle digest, compatibility date/flags, bindings, routes/domains, secrets references, current version ID, deployment split, and storage dependencies. Upload and smoke-test a version before production promotion where supported. Use a bounded gradual deployment with abort criteria. Roll back to a known version ID, then separately assess external data compatibility.

## Origin protection

Prefer Tunnel when suitable. Otherwise require proxied DNS, valid Full (strict) TLS, and a coordinated origin control such as account-specific Authenticated Origin Pulls and/or an origin firewall accepting current Cloudflare ranges plus explicit partner paths. Add allow rules before deny rules, verify through Cloudflare, then verify direct-origin requests fail. Coordinate every origin-side change with the appropriate network, host, cloud, or container owner.
