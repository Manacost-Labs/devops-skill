# Ansible repeatability and honest preflight

Idempotence means applying the same desired state again leaves an already-correct system unchanged. It does not mean suppressing a changed flag, nor does it prove service health or make a destructive action safe.

## Model desired state

Use fully qualified, version-appropriate modules for users, packages, files, templates and services. Specify exact package/artifact versions when reproducibility matters; `state: latest` and mutable URLs can change between review and execution. Record repository/signature provenance, dependency versions and OS-family differences. Do not force downgrades, purge data or reboot simply to produce a uniform recap.

Templates need deterministic content: avoid timestamps/random data on every render, unstable ordering and accidental newline/permission churn. Set owner/group/mode deliberately, validate candidate configuration with the service's actual parser before replacing/activating it, and use atomic replacement where supported. Check filesystem/container constraints rather than enabling unsafe writes to silence an error. Coordinate package-manager locks and active service maintenance with the host module.

For unavoidable command/shell/script work, define the actual state predicate, expected exit codes, `failed_when` and meaningful `changed_when`; prefer `command` with `argv` when no shell syntax is required. `creates`/`removes` are coarse file predicates, not proof that a migration or installation completed correctly. Test stale/partial markers and changed inputs. Never append `|| true`, ignore all errors or set blanket `changed_when: false` to obtain a green second run.

Reads can legitimately use `changed_when: false` when the command is independently reviewed as read-only. A successful status code is not necessarily readiness. Treat async launch separately from completion; poll the exact returned job ID within a deadline and record its terminal outcome. `poll: 0` is not a finished task, and async work can outlive the controller or batch. Account for it before a retry or recovery.

## Handlers and activation

Notify handlers only from real changes. Repeated notifications normally coalesce before a flush; handlers run in their definition order, not notification order. Give handlers unambiguous names/listeners and review included roles. Know exactly which service is restarted/reloaded and whether that disrupts capacity or access.

A health probe before the notified reload can validate the old running configuration. Validate candidate syntax, explicitly `meta: flush_handlers` at the reviewed activation boundary, then test the active configuration/version and user path. Flush runs pending handlers; scope/review all of them. A failed task may suppress a pending handler, leaving disk and running state different. `force_handlers` can activate bad configuration on a failed host; it is not a routine fix. Rescue must not flush an unvalidated change.

## Check/diff are observations, not a transaction

After trust review, run syntax validation, host/task/tag listing, and supported check/diff on an explicit canary with the exact inventory and variables. Unsupported modules can skip work; registered-variable conditions and dynamic includes may behave differently; `check_mode: false`, custom plugins, lookups and controller/API work can still perform real effects. Inspect module support and exceptions before calling preflight read-only. Secret tasks need diff suppression even during checks.

Check mode does not save an immutable executable plan and cannot predict runtime facts, races, remote dependencies or service health. Do not turn its recap into an approval artifact equivalent to a Terraform saved plan. Before real execution, revalidate the reviewed code, dependencies, protected input references, resolved targets and scope through the core gate.

Tags, `--skip-tags`, `--start-at-task`, `--step` and role/task includes can bypass prerequisites, validation, backup or health steps. Examine the exact effective execution path; a tag name such as `safe` grants no authority. Preserve critical checks when narrowing execution, and do not treat restarting at a task as rollback/resume logic.

## Demonstrate repeatability

1. In a matching disposable/staging environment, converge from the expected baseline. Capture changed hosts/tasks, validated content, active service state and health.
2. Re-run the identical reviewed inputs. Expect zero unintended changes, no extra reload/restart, and unchanged user-visible state. Verify content checksums, permissions and independent activation/restart evidence; recap alone can lie when flags are overridden.
3. Introduce a controlled drift in the sandbox. Confirm only that drift is repaired and only affected handlers run. Test invalid candidate configuration: original disk/active state must remain intact and the run must fail.
4. Exercise partial state (existing file/marker but incomplete change), unavailable dependencies and failed activation. Confirm stop/recovery behavior instead of just the happy path.

Some discovery/evidence tasks or deliberately time-bound actions have expected changes. List them explicitly and prove the underlying invariant; do not waive unexplained changes across the whole play. Report coverage limits when the test uses local synthetic hosts rather than actual SSH/WinRM, package managers or real services.
