# Cloud operation scope and evidence

The provider packs route a requested change to a bounded operation runbook. Read
only the relevant procedure, retain the original request and resource identities,
and refresh its exact official API reference before planning a live operation.

| Pack | IAM and access | Network | VM and asynchronous effects |
|---|---|---|---|
| [AWS](../cloud-aws/SKILL.md) | Customer-managed policy versions and an existing role attachment | Existing VPC security-group rules | Bounded EC2 launch, regional/zonal client-token scope, complete instance observation |
| [Google Cloud](../cloud-gcp/SKILL.md) | Project binding changes preserving conditions, policy version and etag | One classic VPC firewall rule | Instance insert and tag update, scoped Operations, numeric resource incarnation |
| [Azure](../cloud-azure/SKILL.md) | Existing-principal role assignment at an exact scope | One NSG rule | VM create/update, API-specific preconditions and ARM long-running operations |
| [Selectel](../cloud-selectel/SKILL.md) | Service-user roles through Selectel IAM | Security groups and port enforcement in a confirmed pool | Volume-backed Nova VM, exact project/pool/segment and supported API versions |

Each procedure covers preflight identity and ownership, quota and capacity,
concurrent writers, an observation deadline, response loss, partial effects and
recovery. Persist intent before dispatch. Keep request identifiers distinct from
idempotency guarantees; preserve the original identifiers after an uncertain
outcome. Inventory actual effects before retry or compensation, and retain
preexisting resources and changes made by another writer.

## Execution boundary

Live writes require a separately registered typed broker task and externally
signed authority under [protected execution](protected-execution.md). These packs
do not provision cloud tasks or credentials. A local planning gate, valid capture,
source check or helper exit code cannot issue authority. Missing task coverage
requires a blocked handoff with the concrete planned operation.

The saved-response inspectors run locally without cloud calls. Their checklists
describe a limited observation and do not replace the complete execution plan.
Capture provenance, timestamps, scope and artifact integrity need independent
evidence. All inspectors keep retry authority, full-plan verification and service
health verification false, including when their supported observation matches.

## Automated checks and limits

The existing platform CI discovers the four provider test suites on Linux and
Windows. It also validates manifest/source mappings and dependency closure, builds
the deterministic runtime archive and verifies the resulting package. Run the
same contract and regression checks from the repository root:

```text
python devops-platform-contracts/scripts/validate_platform.py
python -m unittest discover -s tests -v
```

Provider tests use synthetic native response shapes. They exercise ambiguous
outcomes, wrong scope or incarnation, malformed or incomplete observations,
terminal errors, input bounds and output redaction. The evaluation catalog also
contains narrative operational cases; those cases are review inputs rather than
evidence of live execution.

No provider account is queried or changed by these tests. Official documentation
checks and local fixtures leave installed CLI/API compatibility, actual IAM,
quotas, capacity, enforcement, application health and recovery to the confirmed
target's acceptance procedure. Managed container and database capabilities retain
their specialist routing boundaries.
