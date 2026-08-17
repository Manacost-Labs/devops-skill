# Contract v2

Contract v2 binds infrastructure execution to a validated target, immutable plan, time-bounded authority, recovery evidence, and observable acceptance criteria.

## Executor input

Require operation ID, objective, target profile and fingerprint, environment, owner, data classification, confirmed facts, constraints, selected capabilities, risk, exact plan digest, state/destructive/external-effect flags, recovery evidence, verification criteria, execution identity, idempotency key, change lock, the selected policy ID/version/effective digest, and any approvals or exception. Every approval carries the same effective policy digest as the request.

## Policy binding

The request field `policy` contains `id`, contract `version`, and `digest`. Calculate the digest as SHA-256 over UTF-8 JSON of the fully resolved policy, using sorted keys and separators `,` and `:` with no insignificant whitespace. The resolved policy includes inherited parent semantics, so a parent change invalidates the digest. Approval field `policy_digest` must equal the request digest and the gate's freshly calculated digest.

The gate accepts only registered policy basenames from its own `policies/` directory: `default-policy.json` and `enterprise-policy.json`. Reject absolute paths, path separators, symlinks, unregistered files, inheritance cycles, unknown fields, malformed policy types, and any child policy that weakens its parent. Use `operation_gate.py --policy <registered-name> --print-policy-digest` to obtain the reviewed effective digest before approval.

From the repository root, run these self-checks after changing a policy, schema, template, or gate:

```powershell
python devops-platform-contracts/scripts/operation_gate.py --policy default-policy.json --print-policy-digest
python devops-platform-contracts/scripts/operation_gate.py --policy enterprise-policy.json --print-policy-digest
python devops-platform-contracts/scripts/operation_gate.py --request devops-platform-contracts/templates/operation-request.json --policy default-policy.json --at 2026-08-17T10:15:00Z
python devops-platform-contracts/scripts/operation_gate.py --policy ../unregistered-policy.json --print-policy-digest
```

The first two commands must print stable reviewed digests, the template must return `ALLOWED`, and the unregistered-path probe must return controlled `BLOCKED`.

## Executor output

Return discovery provenance, decision, actual change digest, actor/tool identity, timestamps, exact resources changed, risk, rollback result, verification evidence, final status, and handoff. Never return hidden assumptions or literal credentials.

## Compatibility

- Treat v1 operation requests as planning-only input. Do not authorize R2–R4 execution from a v1 request.
- Require modules in a v2 profile to depend on `devops-core >= 0.2.0` and `devops-platform-contracts >= 0.2.0`.
- Allow modules to add constraints; never let them weaken the selected policy.
- Reject unknown execution-contract fields, missing policy bindings, digest mismatches, unregistered policy files, and malformed or weaker inherited policies.

## Trust statement

The platform supplies guardrails and evidence contracts; it does not certify compliance, prove that external identities are genuine, or make local files tamper-proof. Enterprise deployment must integrate an identity provider, change-management system, credential broker, policy owner, protected source control, and immutable audit sink.
