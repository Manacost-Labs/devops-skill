# Legacy planning authority and protected execution

The legacy autonomy JSON schema and local chat selection are retained for plan
compatibility and contract consistency. They do not authorize execution in0.15.
A metadata approver/evidence string, digest, chosen DEVOPS_AUTHORITY_DIR or forged
host callback cannot substitute for an independently authenticated owner signature.
The arbitrary local argv wrapper has been removed and always refuses.

Actual execution uses `scripts/broker_contract.py` and strict broker call/grant/
admission schemas. Only registered task IDs and bounded typed parameters cross
mTLS. Protected registry facts supply target, risk/effects, code manifest, fixed
argv, executable hash, timeout, worker identity and recovery/verification. Trusted
owner public keys restrict target/mode/risk; private keys stay outside agent and
broker. Finite Ed25519 grants bind client certificate, server, registry, epoch,
mode, task set, time window and operation count. Exact admission additionally
binds the full call digest for above-ceiling/destructive/irreversible effects.

The broker durably journals intent, freezes verified code, rechecks current
admission and drops worker privileges before actual execution. Principal-wide
Safe revokes overlapping/certificate-alias grants; restrictions cannot raise the
persisted ceiling or revive older high-risk grants. New owner authority for the
fresh nonce applies only to its signed scope. Unknown/failed mutation outcomes
remain quarantined, and unclean restart requires accountable reconciliation.

Modes never override policy, recovery, secrets handling or verification. The
enterprise immutable audit sink is not implemented; policies requiring it refuse
live execution. The local hash chain is private integrity evidence only.

The agent prepares one finite card, the independent owner signs once, and covered
registered tasks run without repeated confirmations. Local chat confirmation is
planning-only; this release does not implement a human-only authenticated chat
signing provider. A configured Safe command sends an actual broker restriction;
without a broker profile report local-only planning restriction honestly.

Read [protected deployment and migration](../../docs/protected-execution.md) in a
complete runtime. Independent OS/IAM permissions, protected runtime/interpreter/
dependencies and bounded target access are required; same-UID Full Access cannot
be secured by instructions or optional hooks alone.
