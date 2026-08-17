# Private pilot boundary

This document describes a proposed portfolio and small-hosting pilot. It contains no assertion that a live deployment has occurred and intentionally contains no domain, IP address, account identifier, credential reference, customer data, or infrastructure inventory.

## Repository boundary

| Public skill platform | Private environment overlay |
|---|---|
| Reusable modules, schemas, policies, validators, synthetic fixtures, tests | Approved target profiles, inventory, access-profile names, change records, redacted evidence |
| Demonstrates engineering controls | Establishes authority for a particular environment |
| Safe to clone and run without infrastructure access | Access-controlled and never copied into the public repository |
| Never authorizes a real operation | May authorize a bounded operation only after owner approval and the operation gate |

The public engine must remain useful without the private overlay. The private overlay may reference a reviewed release of the public engine, but it must not modify or weaken platform safety contracts.

## Proposed pilot

1. Confirm the service owner, operator, maintenance window, data classification, and communication path.
2. Create a non-secret target profile using opaque access references. Validate it and record its digest.
3. Perform bounded read-only discovery. Redact evidence and separate observed facts from assumptions.
4. Document the current deployment, DNS/TLS path, monitoring, backups, and rollback path without exposing them publicly.
5. Prove backup recovery in an isolated environment before any stateful production change.
6. Exercise a staging or disposable-host deployment with an immutable artifact and explicit rollback.
7. Define user-path checks, alerts, observation window, and incident handoff.
8. For each live R2-R4 change, generate an exact plan digest, obtain time-bounded owner approval, run the gate immediately before execution, and stop on drift.

## Portfolio evidence

Safe public evidence may include a sanitized architecture diagram, validator output, synthetic gate decisions, test results, and an anonymized incident or rollback narrative. Do not publish screenshots or logs containing hostnames, IPs, usernames, customer data, tokens, cookies, SSH material, internal repository URLs, or security-control details useful to an attacker.

Use the project name publicly only with the service owner's permission. Otherwise describe it as a small hosting-service pilot. Claims should distinguish `designed`, `simulated`, `tested in staging`, and `verified on production`; never collapse them into “production-ready.”

## Exit criteria

The pilot is complete only when the owner can review evidence for target identity, access boundaries, tested recovery, deployment rollback, external user-path health, monitoring and alert delivery, and an agreed operational handoff. Missing live evidence results in `partially_verified`, not `verified`.
