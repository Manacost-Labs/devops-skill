# Host network and firewall

Map client -> DNS -> address family -> route -> firewall -> listener -> service. Confirm namespace, source/destination, protocol/port and timestamp. Localhost success does not prove external access.

1. Inspect scoped addresses, routing tables/rules and `ip route get <approved-destination>` (IPv6 separately). Source selection and return path matter; topology output needs redaction.
2. Identify one configuration owner: NetworkManager, networkd, netplan renderer, ifupdown, cloud-init or automation. Never let competing managers configure an interface.
3. Inspect resolver ownership/link, stub/upstream reachability, search domains and split DNS. Do not overwrite generated resolv.conf. Localhost lookup does not test external DNS.
4. Check listener/bind/family and service in the affected namespace, then both path directions.
5. Correlate interface errors, retransmits, backlog, conntrack and MTU with impact. Agree active probe destination/count/size. ICMP filtering does not prove outage. Payload capture needs explicit scope, duration and privacy handling.

## Firewall change

Determine UFW/firewalld/direct nftables ownership and iptables nft versus legacy backend. Container rules may be generated elsewhere. Runtime and permanent firewalld differ; verify persistence as well as immediate effect.

Record original rule/order/default policy, management source and IPv4/IPv6 effect. Validate with the installed tool, preserve independent console access, add the permitted path before removing old access and test a new connection from the intended source plus denied behavior. Any scheduled rollback needs a tested mechanism independent of the failure and explicit cancellation after acceptance. Never flush rules or disable protection during diagnosis.

Route public DNS/TLS/proxy to edge, cloud security groups to provider, VPN/BGP/transit to enterprise networking and namespace/publishing to Docker/Kubernetes. Change the evidenced failed boundary rather than every layer.

Sources: [NetworkManager](https://networkmanager.dev/docs/api/latest/), [firewalld](https://firewalld.org/documentation/concepts.html), [nftables](https://wiki.nftables.org/wiki-nftables/index.php/Main_Page). Refresh exact installed-version syntax.
