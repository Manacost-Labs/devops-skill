# Configuration routing and cloud-init

## Ansible

Ansible details live in focused references: [inventory and trust](ansible-inventory.md), [repeatability](ansible-repeatability.md), [rolling execution](ansible-rollout.md), and [partial-failure recovery](ansible-recovery.md). Use the Ansible workflow in `SKILL.md`; Terraform saved binary plans and state lineage are not Ansible features. This file retains the cloud-init bootstrap boundary.

## Cloud-init

Treat cloud-init as image bootstrap, not a general remote-execution channel. Validate schema, MIME/multipart structure, package/repository sources, users/keys, file permissions, service units, and secret references. Test on the exact distribution image and cloud-init version.

Determine provider user-data replacement behavior before changing it; some changes recreate instances while others affect only future boots. Cloud-init modules have per-instance/per-boot frequencies, so reruns can duplicate or corrupt state. Never use cleanup/reseed/rerun commands on production without an exact recovery plan and approval.

Verify cloud-init completion, logs with secrets redacted, expected files and permissions, package provenance, service readiness, and removal of temporary bootstrap access. Hand host hardening and service operation to the relevant host module.
