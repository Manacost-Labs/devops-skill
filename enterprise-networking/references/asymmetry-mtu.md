# Diagnose asymmetric and size-dependent failures

Keep the exact flow tuple, both administrative owners and UTC timeline. A traceroute or successful small ping is a hypothesis aid, not proof of the reverse path or application health. Do not change sysctls, disable filtering or add broad routes while collecting evidence.

## Asymmetric traffic

1. Establish which direction fails: initiate a permitted application transaction from each side and inspect source/listener/NAT identity. Compare interface/rule counters and bounded capture from each endpoint with owner approval. Record whether SYN reaches the server and SYN-ACK returns to the expected interface; for UDP compare actual request/reply IDs.
2. Reconstruct the forward and reverse source/mark/VRF-aware FIB lookups, RPDB order, ECMP selection, recursive next hops and any NAT state. A different hop sequence can be legitimate; the failure is loss, unintended exposure or state incompatibility, not asymmetry alone.
3. Read `net.ipv4.conf.all.rp_filter`, the affected interface's `rp_filter`, and `src_valid_mark`. Linux uses the maximum of `all` and the interface value. Strict mode rejects a packet when the best reverse path differs from the incoming interface; loose mode still requires a route. Marks, policy tables and default-route reachability can change that test. Do not globally disable source validation as a generic repair.
4. Choose a bounded route/policy correction that preserves the approved security boundary. If intentional asymmetry needs adjusted source validation, obtain the owner-approved anti-spoofing design and narrow interface-specific change. Verify fresh allowed/denied sessions and return paths, not just a ping after disabling controls.

The native CI uses a real alternate return link and strict reverse-path filtering. It observes the reverse lookup changing to that link, confirms encrypted application-address ICMP fails, then restores the exact WireGuard route and confirms recovery while strict filtering remains enabled. It does not reproduce stateful middlebox/NAT or ECMP behavior.

## MTU and PMTUD

Inventory inner and outer address families, link MTUs, encapsulation layers, any PPPoE/VLAN/IPsec overhead, interface MTU/advmss, path PMTU and filtering of required ICMP messages on **both** paths. WireGuard IPv4 transport overhead is normally 60 bytes, IPv6 80 bytes before additional layers; nested tunnels need their own budget. A fixed 1420/1380 value is not universally correct.

Probe a controlled endpoint with a bounded packet-size sweep and DF/PMTU behavior appropriate to its OS. On Linux IPv4, `ping -M do -s N` carries N ICMP payload bytes; IP+ICMP normally add 28 bytes. Distinguish local `message too long`, received ICMP fragmentation-needed, timeout, and successful fragmented traffic. For IPv6 use its distinct header budget and Packet Too Big behavior, with the IPv6 owner/runbook; the native test does not validate IPv6.

Correlate failures with a real application transfer or throughput test and handshake/retransmission evidence. If small packets work and larger TCP stalls, inspect ICMP filtering and advertised MSS in both directions. MSS clamping affects TCP SYN negotiation only; it does not repair UDP or all existing connections. Do not assume lowering the tunnel MTU fixed a PMTUD blackhole without repeating transfers in both directions and reviewing the security/availability impact of the proposed change.

Stage a specific MTU/MSS change per interface/path; record old values and rollback threshold, preserve required ICMP and retest denied paths. The native CI proves the real encrypted **inner interface** MTU boundary: at 1380 bytes, IPv4 ICMP payload 1352 passes and 1353 fails without fragmentation. It does not claim a multi-hop PMTUD-blackhole, outer-fragmentation or TCP-MSS-clamping rehearsal. Target acceptance requires those additional measurements when relevant.

Official baseline: [Linux rp_filter, src_valid_mark and PMTU sysctls](https://docs.kernel.org/networking/ip-sysctl.html), [route MTU/advmss and contextual lookup](https://manpages.debian.org/bookworm/iproute2/ip-route.8.en.html), [WireGuard bring-up](https://www.wireguard.com/quickstart/). Refresh exact target-version semantics before mutation.
