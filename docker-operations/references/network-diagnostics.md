# Diagnose the actual container network path

Record source container/full ID and network namespace, destination/name/port/protocol, address family, resolver, daemon/host and time. Separate container-local, peer network, published host port and external edge paths. A test from the host is not the container's test.

| Hop | Evidence to discriminate |
|---|---|
| Name resolution | Exact name/search suffix, expected network alias, A/AAAA answers, resolver reachability and cache/TTL |
| Network membership | Both full container IDs on intended network IDs, driver, IPAM/subnets and overlapping host/VPN routes |
| Listener | Process binds expected port/address; container localhost is its own namespace |
| Peer request | Name versus direct peer address, TCP connect versus application/TLS response |
| Published port | Actual host address/family/port mapping, host listener/NAT/firewall and intended client source |
| Edge/downstream | Proxy target, TLS SNI/name/chain, HTTP path and dependency ACL; route to the relevant owner |

User-defined bridges provide name-based discovery; default bridge behavior differs. Docker embedded DNS commonly uses 127.0.0.11 on custom networks. A resolver at 127.0.0.1 means the container's loopback, not the host. Inspect the actual daemon/platform configuration before assuming host gateway addresses or Desktop behavior.

Prefer the application's existing bounded probe where possible. Exec, a temporary diagnostic container, packet capture and `--network container:...` join/observe a sensitive namespace and can send traffic; name the target, approved image digest, identity, capabilities, destinations, deadline and cleanup first. Never run an untrusted image with host networking or the Docker socket to “test connectivity.”

Distinguish DNS NXDOMAIN/timeout, TCP refused/timeout, TLS failure and application 4xx/5xx. Small requests succeeding while larger ones stall can justify scoped MTU/path investigation, not automatic network recreation. Check host conntrack/NAT, VPN/subnet overlap and daemon firewall behavior with the host owner. Test representative permitted and prohibited paths after changes; do not flush firewall rules or publish all interfaces as diagnosis.

Sources: [network overview/DNS](https://docs.docker.com/engine/network/), [bridge isolation and publication](https://docs.docker.com/engine/network/drivers/bridge/).
