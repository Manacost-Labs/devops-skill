# Service path diagnosis

Investigate in this order and preserve evidence at each boundary:

1. DNS: expected record, resolution, propagation and target.
2. TLS: hostname, expiry, chain, protocol, redirect behavior.
3. Listener/firewall: proxy listener, host firewall, cloud security boundary.
4. Proxy: syntax, route match, upstream target, headers and timeouts.
5. Upstream: local TCP/HTTP health, application logs, container/service status.

For 502, confirm the upstream is reachable and speaks the expected protocol. For 504, distinguish upstream timeout from proxy timeout and application slowness. Do not change DNS or timeout values before locating the failure layer.