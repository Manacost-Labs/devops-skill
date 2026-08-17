# Operation ledger

```yaml
schema_version: "2.0"
operation_id: ""
policy_id: ""
target: ""
target_profile_digest: "sha256:"
environment: ""
risk: "R0|R1|R2|R3|R4"
plan_digest: "sha256:"
modules: []
actor: ""
approval_refs: []
changes: []
verification: []
rollback:
  attempted: false
  result: "not-required|verified|failed|not-safe"
  evidence_ref: ""
status: "verified|partially_verified|rolled_back|blocked"
started_at: ""
finished_at: ""
handoff: []
previous_hash: "sha256:"
record_hash: "sha256:"
```

Generate chain fields with `devops-platform-contracts/scripts/ledger_chain.py`; do not invent them. Export the completed record to the approved audit sink.
