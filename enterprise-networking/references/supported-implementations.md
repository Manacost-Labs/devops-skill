# Maintained implementation boundary

| Layer | Maintained procedure | Evidence boundary |
|---|---|---|
| VPN | Linux kernel WireGuard with `wg` and iproute2 | Exact interface/peer public identity, endpoint and AllowedIPs; application traffic plus latest handshake/transfer changes. Interface UP alone is insufficient. |
| Routing | Linux iproute2 IPv4 unicast routes and routing-policy database | All relevant tables/rules and source-specific lookup; ECMP/VRF/NAT require additional target-specific interpretation. |
| BGP | FRRouting 8.4-compatible IPv4 unicast prefix lists, neighbor policies and JSON inspection | Explicit import/export filters and observed route withdrawal. Native CI uses standalone bgpd without zebra, so it does not prove BGP-to-kernel installation. |
| Segmentation | Linux nftables ordered filter chains | Owning table, family, hook, priority, default policy, ordered expressions and both allowed/denied traffic. Helper supports table/chain/rule JSON only. |

The disposable Ubuntu 24.04 native CI records actual distro package versions and kernel release on every run; apt uses configured signed distro repositories, not a new third-party repository or a moving downloaded executable. This is a compatibility test of those recorded packages, not a reproducible package lock or proof for every Debian/Ubuntu release. Detect the target's kernel/tool versions and refresh matching official docs. Do not infer compatibility from the distribution name alone.

Read-only discovery, after confirming the exact namespace/host and permitted topology exposure:

```sh
uname -r
ip -Version
wg --version
nft --version
vtysh -c 'show version'
ip -j -4 route show table all
ip -j -4 rule show
ip -j link show
nft -j list ruleset
vtysh -c 'show bgp ipv4 unicast summary json'
vtysh -c 'show bgp ipv4 unicast json'
wg show wg0 latest-handshakes
wg show wg0 transfer
```

These are examples for a confirmed target, not permission to query another administrative domain. Avoid `wg showconf` and `wg show ... dump`: they can disclose private or preshared keys. Export configuration through the approved secret-aware owner; keep keys as opaque references. Treat public keys, endpoints, route maps and prefix inventories as sensitive topology where policy requires it.

On production FRR, identify integrated configuration ownership, active daemons, zebra/kernel installation, configuration management and concurrent automation. The test's `bgpd -S -Z` bypasses run-as checks and disables FIB installation only within disposable namespaces; it additionally points `-z` to a private unused ZAPI socket, preventing attachment to the runner's host zebra through a shared filesystem socket. Network namespaces alone do not isolate that filesystem path, and `-Z` alone is not the fixture's isolation boundary. Never copy that launch into a real service. A syntax check does not prove applied policy or dataplane acceptance.

Handoff implementations outside this boundary with confirmed device/OS/version, exact source/destination prefixes, management path, owner and evidence required. In particular: strongSwan/IPsec needs IKE/CHILD_SA, selectors/XFRM and rekey-specific recovery; managed VPN needs the provider module; Junos/IOS/RouterOS need their own candidate/commit-confirmed and rollback procedure. Do not translate Linux commands by analogy. IPv6, HA gateways, dynamic endpoint failover, BFD, route reflection and multi-site redistribution need separate native rehearsals before a support claim.

Official baseline, refreshed 2026-10-30:

- [WireGuard CLI and key handling](https://www.wireguard.com/quickstart/).
- [FRR 8.4 BGP options and policies](https://docs.frrouting.org/en/stable-8.4/bgp.html), [configuration ownership](https://docs.frrouting.org/en/stable-8.4/basic.html).
- [iproute2 routes](https://manpages.debian.org/bookworm/iproute2/ip-route.8.en.html), [policy rules](https://manpages.debian.org/bookworm/iproute2/ip-rule.8.en.html).
- [nftables chain and hook evaluation](https://wiki.nftables.org/wiki-nftables/index.php/Configuring_chains).
