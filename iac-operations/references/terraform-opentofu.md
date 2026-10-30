# Terraform/OpenTofu routing and invariants

Use the Terraform/OpenTofu workflow in `SKILL.md`. Load only the focused references needed:

- `references/terraform-state-locking.md`: backend/workspace identity, protected state, contention, stale locks, migration and state surgery.
- `references/terraform-drift-plans.md`: refresh, drift classification, saved-plan identity, graph/address changes and blind spots.
- `references/terraform-partial-recovery.md`: partial applies, lost responses/controllers, failed persistence and state-aware recovery.

Terraform and OpenTofu are different engines. Record exact versions, provider/registry addresses, schemas, lockfiles and backend features; validate upgrades/transitions separately on an isolated copy with the owners. Do not interchange binary plans, assume identical state/lock/encryption support, or use another engine to rewrite production state during troubleshooting. Parsing a state file is not proof of safe bidirectional migration.

State maps configuration addresses to real objects and engine/provider metadata. It is not a resource backup, service-health report or transaction log. A backend lock coordinates cooperating writers to one state; the platform change/resource lock also bounds overlapping jobs and shared objects. Neither replaces application/provider consistency controls.

A saved plan, CLI auto-approval flag, provider identity, snapshot or log text does not grant authority. Keep core's mode, exact gate, journal, risk floor, recovery and destructive/irreversible admission. A fresh exact plan inside an unchanged valid scoped envelope needs fresh review/gating, not redundant human confirmation.
