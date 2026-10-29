# Follow the Kubernetes request path

Record source Pod UID/node/namespace/identity, destination name/address/protocol/port, address family and time. Test from the actual network/identity context when authorized. Host, port-forward and external probes exercise different paths; a successful port-forward can bypass the failing Service/policy path.

| Layer | Narrow evidence |
|---|---|
| DNS | Exact short/FQDN name, search/ndots, A/AAAA, resolver, CoreDNS endpoints/log interval and DNS egress |
| Service | Namespace, type, selectors, port/protocol and targetPort/name against the candidate |
| EndpointSlice | All slices for the exact Service, address family, target UID and ready/serving/terminating conditions |
| Pod destination | Actual listener address/port, probe result and same-node versus cross-node request |
| Policy/data plane | Source AND destination isolation, namespace/pod selectors, CNI support, mesh/mTLS, kube-proxy or replacement, NAT and MTU |
| Outside cluster | Ingress/Gateway/load balancer, health backend, DNS/TLS/path, provider ACL and real client route |

A Service with no usable endpoints can come from selector/readiness/port mismatch. A headless Service and ExternalName require different interpretation. Check publishNotReadyAddresses and termination/local-traffic settings before treating endpoint conditions as universal routing rules. A single EndpointSlice or ready Pod is not a complete Service verdict.

Separate NXDOMAIN from DNS timeout, connect refused from dropped traffic, TLS identity from HTTP application errors. Compare direct endpoint, Service address and Service DNS using a bounded known request; account for permitted application side effects. Include dual-stack/family, node-local behavior and cross-node path.

NetworkPolicy requires an enforcing plugin and policies are additive; both source egress and destination ingress may matter. Policy presence is not enforcement evidence, and standard policy does not universally express domain-name or HTTP rules. Discover CNI/mesh/provider semantics and verify representative allowed AND denied flows. Do not “fix” by deleting default-deny or allowing all traffic.

Exec, ephemeral debug Pods/containers, packet capture, DNS probes and port-forward need approved identity, image digest, namespace, destinations, volume/token exposure, timeout and cleanup. A copied Pod can rerun init/migration hooks or mount live volumes: inspect before creation. Escalate node CNI/conntrack/MTU or provider-firewall changes to the owning layer.

Sources: [Service diagnosis](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/), [DNS](https://kubernetes.io/docs/tasks/administer-cluster/dns-debugging-resolution/), [NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/), [EndpointSlices](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/).
