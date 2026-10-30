# Enterprise networking depth

The enterprise-networking module maintains a concrete Linux stack: kernel WireGuard, FRRouting IPv4-unicast BGP, iproute2 routes/policy rules and nftables segmentation. The [implementation matrix](../enterprise-networking/references/supported-implementations.md) separates supported procedures from vendor/IPsec/managed-VPN handoffs and target-specific work. It preserves contract-v2 risk, exact authority, recovery, concurrency and evidence requirements; instructions and matching snapshots do not issue production authority.

The skill now covers source/mark/VRF-aware forward and reverse FIB lookup, RPDB priorities, route type/metric/nexthop changes, accepted versus advertised BGP prefixes, prefix-list attachment and propagation, nft rule/hook ordering and negative-flow checks, asymmetric paths with reverse-path filtering, and MTU/PMTUD/MSS diagnosis. Recovery procedures distinguish an exact policy reversal from unsafe restoration after partial effects or concurrent changes.

## Snapshot helper

`enterprise-networking/scripts/snapshot-audit.py` compares local native-shaped before/intended/observed JSON, preserving complete route fields and ordered policy/nft rules. It detects exact-prefix BGP inventory leaks, defaults/over-specifics outside the allowlist, changed next hops and changed ACL order. It rejects malformed/oversized/duplicate-key/nonfinite inputs and unsupported nft object kinds. It executes no snapshot content or commands. The [input and exit contract](../enterprise-networking/references/route-acl-analysis.md) documents its narrow supported subset.

Only nft handles/indexes, runtime metainfo and anonymous counter **values** are ignored. FRR comparison covers prefix inventory, not path attributes or best-path/kernel installation. `MATCHED` means only that supported snapshot comparison passed; authentic collection, freshness, peer health, actual packet verdicts and application acceptance require separate evidence. Do not treat the helper's digest as a platform operation digest or authorization.

## Native CI and limits

The always-on `enterprise networking` workflow runs **Networking / WireGuard FRR nftables recovery** for pull requests and main pushes on an ephemeral GitHub-hosted Ubuntu 24.04 runner. It installs signed-repository distro tools, records exact package/kernel versions, and runs real kernel/protocol tests in disposable network namespaces. Actions are pinned by immutable SHA; the job has read-only checkout permission, no persisted credentials, deployment credentials or production endpoints. It requires root/CAP_NET_ADMIN for owned namespaces; missing tools or kernel support are failures, not skips. Distro package resolution is recorded but is not a frozen reproducible package lock.

The native test exercises:

- Real encrypted traffic in both directions, WireGuard handshake and inner-MTU payload boundary.
- Actual nft first-match accept/drop ordering, denial counters, changed-rule detection, table-scoped restoration and preservation of an unrelated sentinel table.
- An alternate return route with strict Linux reverse-path filtering, observed loss, then exact route restoration and recovered traffic.
- Two actual FRR bgpd peers with explicit import/export filters, forbidden-prefix admission inside the isolated lab, helper detection and withdrawal after filter rollback.
- Actual WireGuard loss, BGP route withdrawal, tunnel restoration and control/data-plane reconvergence with the forbidden prefix still denied.

The fixture uses standalone bgpd without zebra; BGP-to-kernel integration is not tested. Static kernel routes and encrypted application-address ICMP are independent dataplane observations. The MTU test checks an IPv4 inner interface boundary, not a routed PMTUD blackhole or TCP-MSS clamp. IPv6, IPsec rekey/XFRM, vendor commit-confirmed semantics, HA/failover, BFD, EVPN/MPLS, NAT/conntrack asymmetry and multi-site redistribution need separately owned implementation-specific rehearsals. Lab timer budgets do not establish production RTO.

Run full cross-platform regressions, platform/changed-skill validation, deterministic export/package verification and secret scanning as well as native CI. Independent scenario evaluation covers operational decisions and handoffs; neither AI technical review nor synthetic tests impersonate an authenticated production approver.
