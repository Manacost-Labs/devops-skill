# Interpret routes and ACLs before changing them

Bind each collection to host/device, network namespace or VRF, AFI/SAFI, peer, command, UTC time, configuration revision/digest and collector identity. Failed or truncated collection is unknown, never an empty table. A helper result does not authenticate this provenance. Keep raw evidence private and redact topology before sharing.

## Routing and BGP

For a flow, record source, destination, protocol/ports, packet mark, ingress interface and namespace/VRF on both sides. `ip route get` evaluates the actual FIB/RPDB context; a main-table listing alone does not. Use a confirmed representative tuple, for example:

```sh
ip -j -4 route get 10.20.0.1 from 10.10.0.1 ipproto tcp sport 40000 dport 443
```

The lookup on a forwarding router additionally needs the real ingress interface and mark where relevant. Obtain the reverse tuple from the remote side. `from` is a source selector, not permission to spoof application traffic. Match source rules in increasing priority; equal priorities are ambiguous to the offline helper. Account for `throw` continuing RPDB lookup and `blackhole`, `unreachable` or `prohibit` terminating it. Compare destination length before metric/preference, then next hop, device, table and encapsulation. Preserve ECMP nexthops/weights, `nhid`, MTU/advmss, VRF/table identity and route type; do not reduce a route to its destination prefix. Check overlap and defaults explicitly.

For FRR, inspect per-peer accepted routes and advertised routes as well as full BGP RIB, best-path reason, next-hop reachability, AS path, local-pref, MED, communities and policy placement. A received route, selected BGP path and installed/usable kernel route are different observations. A rejected route is not visible in the accepted RIB; pre-policy received-route inspection may need existing inbound soft-reconfiguration or separately bounded capture. Do not reset a session or enable unbounded soft-reconfiguration merely to inspect it.

Use exact prefix allowlists separately by peer, direction and address family. An allowed `10.20.0.0/24` does not authorize `/25`, default or broad `le 32` export. Bind filter revision to the peer and actual attachment, not just existence of a named list. Keep `bgp ebgp-requires-policy` explicit; defaults vary by FRR profile. Maximum-prefix limits bound impact but do not replace import/export filtering. Session reset, soft refresh, graceful restart and withdrawal timers have different effects; choose against the real peer capability and accepted convergence budget.

## nftables

Read the complete relevant ruleset, not one grep result. Within a chain preserve rule and expression order. Across base chains preserve family, hook, device and priority; equal-priority base chains have unspecified order. An accept verdict may still be followed by a later base chain that drops the packet. A drop is terminal. Follow jump/goto, return, sets, state/NAT and flowtables only with an implementation-specific analysis; the offline helper rejects named/dynamic objects outside its small subset.

For each intended allow/deny, use a real source in the correct segment and a protocol-specific application check. Check counter deltas on the expected rule, return traffic and connection-tracking state. Previously established traffic may mask a newly blocked NEW connection. Avoid broad packet traces that disclose unrelated traffic. The native fixture deliberately tests two opposite matching verdicts in both orders; it is not a general packet-verdict evaluator.

## Offline three-way snapshot helper

`scripts/snapshot-audit.py` reads local JSON only; it has no network/subprocess operations and never applies routes, configs or rules. Assemble each snapshot with exactly these keys from the **same confirmed collection scope**:

```json
{
  "routes": [{"dst": "10.20.0.0/24", "dev": "wg0", "metric": 20}],
  "rules": [{"priority": 32766, "src": "all", "table": "main"}],
  "nft": {"nftables": []},
  "bgp": {"routes": {"10.20.0.0/24": [{"valid": true}]}}
}
```

Use actual `ip -j -4 route show table all`, `ip -j -4 rule show`, `nft -j list ruleset`, and `show bgp ipv4 unicast json` output; the example is a shape, not real acceptance evidence. Preserve complete collection and provenance separately. Intended is a reviewed expected after-state, not an automatically captured broken state. Its digest and allowlist belong to the exact plan reviewed under the platform contract.

```sh
python enterprise-networking/scripts/snapshot-audit.py --before before.json --intended intended.json --observed observed.json --allowed-prefix 10.20.0.0/24
```

The helper compares complete route fields, ordered policy rules and ordered nft expressions/objects. It ignores only nft object handles/indexes, metainfo and numeric anonymous-counter values; counter **presence** remains semantic. It compares FRR **prefix inventory only** and checks exact membership in the supplied BGP allowlist. It does not compare BGP path attributes or infer peer health, route selection, installed FIB or application behavior. Route record order is immaterial; nft rule order is not. Unsupported nft objects, duplicate JSON keys, invalid shape, nonfinite numbers, duplicate RPDB priorities, IPv6 route/BGP/allowlist prefixes or next hops, or input over 8 MiB return controlled `BLOCKED`; no automatic mutation follows. Use explicitly IPv4 collections: a bare `default` without a next hop contains no address-family evidence, so the helper cannot authenticate how it was collected.

Exit 0 / `MATCHED` means only the supported observed snapshot equals intended and contains no disallowed BGP prefix. Exit 1 / `BLOCKED` identifies drift/leaks; exit 2 / `BLOCKED` means malformed/unsupported collection. Never convert MATCHED into production approval or the final `verified` status. Unknown expression data is preserved exactly for comparison, not interpreted as a verdict; require native review for its meaning. Diff output contains topology and rule comments; store it in an approved private evidence location.

Official baseline: [FIB lookup and route types](https://manpages.debian.org/bookworm/iproute2/ip-route.8.en.html), [RPDB](https://manpages.debian.org/bookworm/iproute2/ip-rule.8.en.html), [FRR filters and selected paths](https://docs.frrouting.org/en/stable-8.4/bgp.html), [nft chain evaluation](https://wiki.nftables.org/wiki-nftables/index.php/Configuring_chains). Refresh for the detected version before change.
