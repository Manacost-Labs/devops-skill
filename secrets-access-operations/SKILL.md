---
name: secrets-access-operations
description: Govern secret references, workload identities, privileged access, JIT/JEA elevation, credential rotation and revocation, and break-glass workflows. Use for production access changes, secret lifecycle operations, least-privilege design, dual-control approval, and provider-specific access handoffs.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

# Secrets and Access Operations

Operate identities and secret references under the devops-core safety contract and platform contract v2. Never request, reveal, copy, log, test, or store a literal secret.

## Workflow

1. Confirm the resource owner, target, environment, identity type, requested action, bounded privileges, duration, justification, data classification, dependencies, and authoritative provider.
2. Accept only opaque references such as credential-broker, vault, OIDC, workload-identity, SSH-config, or approved profile references. If secret material appears, do not repeat it; redact evidence and direct the owner to rotate it through the authoritative system.
3. Prefer workload identity and short-lived, audience-bound credentials. For humans, use attributable JIT elevation and JEA or equivalent constrained administration instead of standing broad access.
4. Classify grants, rotation, revocation, and emergency access by actual blast radius. For R2-R4, require a validated v2 request, immutable plan digest, exact target/scope, expiry, approvals, separation of duties where required, and immediate pre-execution gate.
5. Stage rotation with dependency inventory, overlap only when necessary, reference update, consumer verification, and prompt revocation of the old credential. Never print a credential to validate it.
6. Record redacted authorization, actor, provider evidence, reference versions or identifiers, timestamps, changed principals/resources, verification, and revocation outcome. Return a contract-v2 status.

## Mandatory safeguards

- Deny literal secrets in prompts, files, commands, logs, evidence, and operation records. Treat pasted secrets as potentially compromised.
- Scope access by principal, resource, action, environment, session duration, network/device conditions, and expiry. Reject wildcard or broad-admin access without a separately approved bounded exception.
- Require dual control for production privileged access, root/break-glass use, high-impact revocation, and policy-defined R4 operations. Keep requester, approver, and executor separate where policy requires.
- Make break-glass time-bound, attributable, least-privilege, monitored, automatically expiring where supported, and independently reviewed. It does not waive target identity, recovery, or evidence.
- For emergency revocation, preserve a recovery administrator path and assess dependent workloads before removal unless immediate containment is explicitly authorized.
- Hand provider-specific IAM, vault, KMS/HSM, directory, or broker mutations to the matching provider executor with the validated request. Do not imitate missing provider capabilities.
- Stop on unknown identity ownership, unverified approver, changed plan, absent expiry, missing recovery path, or inability to preserve redacted evidence.

Read [references/access-lifecycle.md](references/access-lifecycle.md) for lifecycle gates and handoff requirements.
