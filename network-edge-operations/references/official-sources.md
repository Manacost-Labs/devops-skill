# DNS, TLS and proxy official sources

Last verified: 2026-10-30. Refresh exact CA/provider/client/proxy behavior before mutation, especially renewal, DNSSEC, file watching and reload semantics. Documentation is not proof of actual account rights, live configuration or fleet acceptance.

- [DNS protocol and authoritative answers](https://www.rfc-editor.org/info/rfc1035/) and [negative caching, RFC 2308](https://www.rfc-editor.org/rfc/rfc2308.html).
- [TLS service identity and SAN validation, RFC 9525](https://www.rfc-editor.org/rfc/rfc9525.html).
- Let's Encrypt [challenge types](https://letsencrypt.org/docs/challenge-types/), [integration and renewal design](https://letsencrypt.org/docs/integration-guide/), [current rate limits](https://letsencrypt.org/docs/rate-limits/) and [separate staging trust/accounts](https://letsencrypt.org/docs/staging-environment/).
- Nginx [configuration/test/reload workflow](https://nginx.org/en/docs/beginners_guide.html), [HTTPS and certificate chains](https://nginx.org/en/docs/http/configuring_https_servers.html) and [proxy headers, timeout and upstream semantics](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).
- Caddy [automatic HTTPS and durable state](https://caddyserver.com/docs/automatic-https) and [validate/reload/force behavior](https://caddyserver.com/docs/command-line).
- Traefik [file provider and parent-directory mount/watch caveats](https://doc.traefik.io/traefik/reference/install-configuration/providers/others/file/) and [dynamic certificates](https://doc.traefik.io/traefik/reference/routing-configuration/http/tls/tls-certificates/).
- [CoreDNS authoritative file plugin](https://coredns.io/plugins/file/).
- [Alibaba ECS metadata endpoint and SSRF boundary](https://www.alibabacloud.com/help/en/ecs/user-guide/view-instance-metadata/).

Source-only native CI uses immutable images for CoreDNS and Nginx/Caddy/Traefik, generated private-PKI certificates and owned internal networks. It observes real DNS answers, strict TLS rejection, actual served certificate rotation, proxy failures and recovery. It does not contact public ACME/DNS providers or prove public issuance/renewal, DNSSEC/recursive cache propagation, managed/CDN controls, IPv6 routing or production fleet behavior. See source-checkout `docs/network-edge-depth.md` for exact coverage and limits. Synthetic manual pair rotation is distinct from automatic ACME renewal.
