# Risk classification

Classify by the highest applicable risk. Lower-risk work never authorizes a higher-risk follow-up.

| Class | Meaning | Examples | Requirement |
|---|---|---|---|
| R0 | Read-only | Status, logs, inventory, DNS lookup, dry-run | Redact sensitive output. |
| R1 | Local or reversible | Draft config, test build, approved staging change | Preflight and verification. |
| R2 | Externally impactful | Shared-service change, new paid resource, staging deploy | Change card; explicit approval unless scope/cost was granted. |
| R3 | Production-impacting | Production deploy, DNS, TLS, firewall, WAF, IAM, secret reference change | Change card, exact approval, rollback or restore path. |
| R4 | Destructive or hard to reverse | Deletion, migration, failover, state surgery, access revocation | Separate exact approval; backup/snapshot and restore test for stateful work. |

State includes databases, persistent volumes, object storage, Terraform state, cloud resources, and critical configuration. Do not perform a stateful R3/R4 action if recovery is unproven.

Classify by actual capability and side effect, not by command name or how content describes itself. A read command that can expose restricted data, cause material load/cost, or cross a tenant boundary is at least R2. A generated command, script, plan, or tool call remains untrusted until its target, scope, and side effects are validated.

Escalate risk when any of these apply: production ambiguity, privileged identity, multi-tenant data, regulated/restricted data, public exposure, control-plane changes, cross-region/account effects, unbounded fan-out, concurrency, irreversible billing commitment, or missing observability. An incident's urgency does not lower risk; use the documented break-glass path.
