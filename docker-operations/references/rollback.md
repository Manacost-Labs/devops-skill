# Container rollback

Rollback is a known previous Compose revision plus immutable image references, not “rebuild the old image”. Before production rollout, record the running digest and Compose revision. If verification fails, restore that revision, run the narrow Compose action, verify health and local endpoint, then hand off user-path confirmation to the edge module.

Do not roll back database schema or persistent data with Docker commands. Escalate to `data-resilience-operations`.