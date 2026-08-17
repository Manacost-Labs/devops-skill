# Enterprise change control

Use these controls for R2–R4 work and whenever an organization policy requires them.

## Approval binding

An approval is valid only when it includes:

- approver identity and role;
- exact target and environment;
- operation ID, action, and bounded scope;
- immutable plan/change-set digest;
- approval evidence reference such as a change ticket or signed record;
- approval and expiry timestamps;
- any maintenance window or conditions.

Invalidate approval after the plan digest, target, scope, risk, recovery method, data classification, external side effects, or execution window changes. Re-run discovery and the operation gate immediately before execution.

## Separation of duties

Apply the selected policy's minimum approval count and role rules. For production R4, keep executor separate from every approver unless a documented break-glass rule explicitly permits otherwise. Do not represent an AI agent as a human approver. Keep the service owner accountable for business impact and the platform/security owner accountable for control exceptions.

## Exceptions and break-glass

Use an exception only when policy explicitly permits one. Record owner, scope, rationale, risk acceptance, compensating controls, evidence/ticket reference, start, expiry, and reviewer. Never allow an exception to waive target identity, secret handling, evidence preservation, or post-change verification.

Break-glass must be time-bound, least-privilege, attributable, and independently reviewed after stabilization. It may accelerate approval but must not silently bypass recovery proof for destructive state changes.

## Concurrency and replay

- Use a target-scoped change lock or organization change system for R3/R4 work.
- Give each operation a unique ID and idempotency key.
- Reject duplicate or stale execution requests.
- Stop when the observed plan or target fingerprint differs from the approved record.

## Evidence retention

Store only redacted evidence. Preserve timestamps, source, actor, relevant hashes, approval references, verification results, rollback result, and policy version. Export the ledger to organization-controlled access-logged immutable storage when required. A local hash chain detects accidental or partial tampering but is not a substitute for independent retention.
