# Service-path diagnosis

Build an evidence chain: client/resolver → authoritative zone → A/AAAA destination → listener/firewall/load balancer → TLS termination → proxy route → upstream listener → application/dependencies. Record where TLS terminates and whether proxy-to-upstream traffic has a separate TLS identity. A CDN edge and origin can legitimately present different certificates. An origin-only check cannot establish public-edge health.

Compare one failing and one healthy request with time, address family, resolver, destination, SNI/Host, path category, status and safe correlation ID. Avoid raw cookies, Authorization, full query strings, signed URLs, private keys and entire config dumps. A 502/504 status can originate at any proxy layer: establish which emitted it using bounded logs and upstream timing, rather than trusting a Server header alone.

| Observation | Next discriminating evidence |
|---|---|
| Some clients reach old service | Exact authoritative/recursive RRsets and remaining positive/negative TTL; split DNS; AAAA; CDN/connection caches |
| Name resolves, TLS fails | Actual destination/SNI, SAN, chain, approved trust root, clock, validity; each terminator separately |
| TLS works, wrong virtual host | Host route, default route, explicit port, HTTP versus TLS hostname and proxy routing priority |
| 502 | Upstream resolution/address, refusal/reset, protocol/SNI/trust mismatch, process readiness and proxy error at that time |
| 504 | Which hop timed out, upstream connect/header timing, application saturation/dependencies; owner evidence before timeout change |
| Redirect loop | Full approved hop map, original scheme/host, trusted forwarded headers, CDN encryption mode and application base URL |
| Works from proxy only | Public/IPv6 listener, provider/host firewall, CDN route, client trust, geography and actual resolver cache |

## Safe helper use

The bundled helper uses Python's default validating TLS context (or an explicitly approved CA file), a single address resolution and numeric connections. It rejects credential URLs, mixed approved/forbidden DNS answers, unsafe URL characters and metadata/link-local/multicast/reserved destinations even with `--allow-private`. It ignores HTTP(S)_PROXY/ALL_PROXY and stops at the first response, including redirects. For an approved origin check behind a CDN, specify the intended URL hostname plus `--connect-ip` with the owner-confirmed numeric endpoint; authorize any direct-origin access and client/mTLS requirements first. This option bypasses DNS lookup for that one observation, so it proves nothing about public DNS.

Output suppresses URL paths/queries and redirect paths/queries; still treat hostname/IP/server fields as sensitive inventory. Exit 0 means an observed 2xx/3xx hop, not redirect completion, application correctness or fleet health. No body is read, credentials are not sent, and no private/metadata redirect is requested. Each subsequent hop needs independent scope validation. The ten-second observation budget limits socket operations between phases; OS resolver latency and incremental HTTP header reads can exceed a strict total deadline. Apply an outer supervisor deadline when a hard job limit is required. Single-host system DNS, GET and standard HTTP/1.1 do not test recursive DNS behavior, mTLS, HTTP/2, gRPC, WebSocket, authenticated flows or all network paths.

Known metadata exclusions include link-local ranges, AWS's IPv6 endpoint and [Alibaba ECS's non-link-local endpoint](https://www.alibabacloud.com/help/en/ecs/user-guide/view-instance-metadata/), including IPv4-mapped forms. Refresh provider metadata addresses before private-target work; the helper is not a network sandbox or a substitute for an exact approved endpoint/egress policy. Pre-connect transport failures may try another already validated address; once GET transmission is attempted, response loss is an unknown outcome and never triggers replay.

Keep curl/OpenSSL alternatives equally strict: correct Host/SNI and an approved trust store, bounded traffic, no insecure verification flags or automatic out-of-scope redirects. Do not paste arbitrary record/header values into shell commands. Collect only allowlisted evidence fields.
