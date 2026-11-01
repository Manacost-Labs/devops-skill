# Protected Windows endpoint preparation

Read the full runtime's docs/windows-protected-execution.md before configuring
an endpoint. Platform 0.16 provides a worker-only PSRP bridge, finite-task JEA
foundation, owner bundle preparation/bootstrap and read-only caller probe. It
does not install AD tasks, create identities/keys or certify deployment.

Use a fresh standard-user Codex identity without target/hypervisor/broker control.
An independent owner protects runtime/target code/state and credential paths,
provisions scoped connector/run-as identities and supplies external signed broker
authority. A flag, supplied hash or current admin password cannot replace it.
Never use default DC virtual-account admin rights, general commands, auth fallback,
skipped TLS validation or writable installer code.

Each task is a bounded fixed-target slice with pre-write drift checks. Keep both
Linux and Windows receipts/latches after failure or lost replies. Client death
does not prove remote execution stopped; reconcile the original operation ID.
Reboot requires owner reconciliation/re-enrollment before another write.

Service account creation, forest features, DC promotion, policy processing and
recoveries remain separately authorized capabilities. Report partially_verified
until actual target/identity/deny/recovery evidence exists. Hosted fixtures are
not domain tests.
