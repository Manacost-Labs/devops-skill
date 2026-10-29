# Offline Pod evidence

Collect one exact v1 Pod in a protected authorized session using explicit kubeconfig/context/namespace and a finite request timeout. Record API/CA/cluster identity, authenticated subject, Pod UID, version, collection time and command outcome separately. Raw Pod objects can contain command arguments, literal environment values and tenant metadata; do not paste the full object into chat/logs.

`python scripts/inspect-pod-state.py --namespace NAMESPACE --name POD --uid POD_UUID` reads at most 1 MiB of UTF-8 JSON from stdin. It accepts one v1 Pod object, compares namespace/name/UID, and does not contact the cluster or verify artifact authenticity/freshness. UID/name agreement is only an artifact consistency check.

Selected output includes phase, whitelisted reason codes, current AND previous container states, readiness/restarts, admitted per-container/pod-level resource declarations and selected conditions. Regular, init and ephemeral status groups stay separate. Missing status/spec matches remain partial; each output group is capped at 32 and truncation is explicit. Unknown enum text is suppressed. Messages, env, arguments, annotations, image strings, addresses and claim/secret references are omitted.

Quantities are preserved as declarations, not converted into measured headroom or universal effective ceilings. The helper does not inspect nodes, events, EndpointSlices, policies or storage, and cannot establish a root cause from phase/reason alone. Absence of a current OOM is not evidence about every previous instance or node.

Exit 0 means snapshot summary only; verification remains not assessed. Malformed/oversized/duplicate-key/nonfinite/mismatched input yields generic unknown and exit 2 without raw errors. Bound collector and pipe duration externally; byte bounds cannot time out an unfinished stdin stream. Keep original evidence protected for approved contextual analysis.
