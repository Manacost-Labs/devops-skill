# Bounded Ansible and cloud-init

## Ansible

Pin collection and role sources. Verify inventory origin, environment, groups, exact `--limit`, connection user, become policy, strategy, forks, serial size, and vault/secret references. Reject dynamic-inventory output that crosses the approved account or environment.

Run syntax validation and, where modules support it, check mode with diff against a small canary. Check mode is advisory: command/shell tasks, lookups, API calls, and custom modules may still be inaccurate or have side effects. Review task tags, handlers, `run_once`, delegation, rolling settings, failure thresholds, and rescue/always blocks before execution.

Prefer idempotent modules over shell. Bound fan-out with explicit hosts, serial batches, failure thresholds, and a stop point between batches. Keep one known-good management path for access, firewall, and network changes. Verify configuration syntax, service health, and the user path after each batch.

## Cloud-init

Treat cloud-init as image bootstrap, not a general remote-execution channel. Validate schema, MIME/multipart structure, package/repository sources, users/keys, file permissions, service units, and secret references. Test on the exact distribution image and cloud-init version.

Determine provider user-data replacement behavior before changing it; some changes recreate instances while others affect only future boots. Cloud-init modules have per-instance/per-boot frequencies, so reruns can duplicate or corrupt state. Never use cleanup/reseed/rerun commands on production without an exact recovery plan and approval.

Verify cloud-init completion, logs with secrets redacted, expected files and permissions, package provenance, service readiness, and removal of temporary bootstrap access. Hand host hardening and service operation to the relevant host module.
