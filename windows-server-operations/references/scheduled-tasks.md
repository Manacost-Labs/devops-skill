# Scheduled tasks: definition, identity and actual result

Confirm exact TaskPath/TaskName, owner, host/build, principal/logon type/run level, registration ACL, action executable/arguments/working directory, triggers/time zone and settings. Query exact Get-ScheduledTask/Get-ScheduledTaskInfo and a bounded TaskScheduler Operational event interval. Arguments/XML/events can contain secrets; default evidence should omit their raw text.

Export the definition before change and store it as sensitive evidence. XML is executable configuration, not a harmless document: it can reference privileged commands, COM handlers, UNC paths and external data. `scripts/inspect-task-definition.ps1` reads a local offline definition with DTD/entities disabled, exposing only structural facts. It does not validate the whole XSD, resolve paths/identities or register/run anything.

## Identity and schedule

Password, S4U, interactive and service-account logon have different capabilities. S4U does not supply ordinary network credentials or encrypted-file access; changing it is not a universal credential repair. Check effective log-on-as-batch rights, deny rights/GPO, account status, gMSA support and required network/key/file access. Never store passwords in XML, task arguments or scripts.

RunLevel Highest is not automatically necessary. Verify task ACL and write permissions on executable, script, working directory, configuration, DLL/plugin search paths and parent directories; a privileged task running user-writable code is an escalation path. Separate Execute and Arguments correctly rather than concatenating an untrusted command line.

Inspect calendar/DST/time-zone behavior, missed-run policy, battery/network conditions, concurrency, retry/duration and overlap/idempotence. A wall-clock trigger without a zone is not automatically UTC. Avoid creating duplicate scheduled jobs during migration/retry.

## Change and acceptance

Preserve full definition, principal/credential references, ACL and dependencies. Exported XML does not include every credential needed for re-registration. Review the candidate offline, stage disabled where useful, validate with the actual scheduler/tooling and gate the exact change. Do not run an unfamiliar exported task as a validation technique.

After approval verify definition and identity, then authorize a bounded execution with the real data/side effects understood. Confirm actual job output/invariants, timestamps and event trail, not merely Task State Ready or LastTaskResult=0. “Has not run”, running and missed/failed states require interpretation. On failure preserve evidence before rerun; rollback must account for work already performed.

Sources: [export](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/export-scheduledtask?view=windowsserver2025-ps), [schema](https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-schema), [security contexts](https://learn.microsoft.com/en-us/windows/win32/taskschd/security-contexts-for-running-tasks), [logon types](https://learn.microsoft.com/en-us/windows/win32/taskschd/principal-logontype), [hardening](https://learn.microsoft.com/en-us/windows/win32/taskschd/task-security-hardening).
