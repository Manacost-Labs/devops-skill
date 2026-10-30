# Docker and Kubernetes expansion in 0.8.0

Docker and Kubernetes remain separate executors among 23 modules. Docker owns its daemon/runtime/Compose layer; Kubernetes owns API workloads/controllers, Service/policy and claim-level intent. Neither can undo database commits, queue processing or external effects through an image/template reversal.

| Area | Decision support added | Evidence boundary |
|---|---|---|
| Failure/resources | Exit versus signal/OOM, previous instance, probes, scheduling/eviction, configured requests/limits versus measured pressure | Exit 137, Running and current low memory do not prove a cause or health |
| Network | Container DNS/listener/publication and Kubernetes DNS/Service/EndpointSlice/Pod/policy path | Correct resolution does not prove an endpoint/listener; policy presence does not prove CNI enforcement |
| Storage | Exact mount/claim/backing identity, bytes/inodes/access, attach/topology, growth and isolated restore | A volume or snapshot object is not an application-consistent backup |
| Update/recovery | Mixed reader/writer versions, serialized migrations, latest writes, forward repair versus compatible reversal versus isolated restore | Old image/configuration alone cannot reverse persistent or outside effects |

The existing Kubernetes profile installs both modules and dependencies. Read-only offline helpers consume one bounded Docker inspect array or exact UID-bound Pod object from stdin and omit raw environment, action/message and path/address content. They report selected observations/unknowns, never target authority, root-cause certainty, healthy service or safe rollback.

## Verification

Unit/adversarial checks cover identity/scope mismatch, missing metadata, current versus previous termination, unknown values, quantity types, redaction, duplicate/nonfinite/malformed JSON, input/output bounds and running both helpers from an installed profile. Compose regressions also distinguish long-form named volumes from host binds and reject literal secret fallbacks inside interpolation.

Two separate disposable GitHub Linux runner jobs use an explicitly local Docker endpoint and owned resources. The Docker job exercises real limit OOM versus SIGKILL, internal bridge DNS/HTTP and loopback-listener failure, named-volume persistence and a synthetic SQLite data-compatibility scenario. The Kubernetes job uses checksum-pinned kind 0.31.0/kubectl 1.35.0 and a digest-pinned 1.35.0 node image, explicit isolated kubeconfig/context/namespace and native Pods/Services/PVCs. It exercises backoff/previous exit, OOM, good and missing-endpoint Service paths, and persistence across replacement Pods.

The native crash fixture requires repeated exit 42 for the exact Pod/container and either sampled Waiting/CrashLoopBackOff or its UID/container-bound kubelet restart-BackOff event. A live run retained current/previous Terminated states while restart events corroborated backoff; the helper receives the untouched Pod and reports the state actually observed. Image-pull BackOff, another UID/container, missing events and wrong exits cannot substitute. This follows the [v1.35 Pod lifecycle](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) and [state/restart/event troubleshooting](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/) distinction; it does not claim that every live API snapshot exposes a Waiting reason.

Both data scenarios commit a pre-change row, make a separate synthetic backup, rename a column incompatibly and commit a new row. The old reader fails against new data. A separate restore can read the older point but lacks the new row; current data is preserved. Forward compatibility repair lets both readers see both rows. This demonstrates the choice/loss boundary; it is not a production SQLite recovery capability, a distributed migration framework or a generic down-migration recipe.

Resource cleanup checks daemon/object/cluster/namespace identity and ownership before exact deletion. These mutation fixtures must never run on an operating target; local regression imports and offline tests do not execute them.

Fixtures do not certify every Engine/Kubernetes version, Windows/rootless/Desktop/Swarm, real CNI/NetworkPolicy/mesh or cloud routing, node-pressure eviction, production CSI snapshots/attachment repair, distributed writers/queues/external reconciliation, engine-specific PITR or control-plane recovery. Rehearse the actual version/topology and application acceptance with its owners.
