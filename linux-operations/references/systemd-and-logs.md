# systemd services, timers and logs

Confirm systemd PID 1 and system/user unit scope. Inspect selected properties (LoadState, ActiveState, SubState, Result, ExecMainCode, ExecMainStatus, NRestarts, FragmentPath), dependencies, drop-ins and a bounded journal. Unit/environment content can hold credentials: do not dump it to shared evidence.

Active is lifecycle state, not application readiness. Simple, forking, oneshot and notify differ. Verify the endpoint/workload. Find original exit/config/permissions/limits before clearing failure or restarting; reset-failed clears counters, not causes. After orders units but does not itself pull dependencies in. Do not mask dependencies or inflate timeouts to suppress symptoms.

Timers: inspect last/next run, associated service, realtime versus monotonic clock and persistence. Presence does not prove execution or backup validity.

## Change

Use the owning configuration system and a small drop-in where appropriate; preserve exact originals. Installed-version systemd-analyze verify checks definitions, not runtime health. Daemon-reload rereads unit definitions; reload requests service config reload only if implemented; restart disrupts the process. Choose deliberately, with drain/data owners before lifecycle action.

Validate candidate, apply once after approval, verify loaded values, process, journal and acceptance, then observe restart/resource trends. Roll back failed acceptance while preserving evidence.

## Logs

Scope journalctl to unit, UTC interval, boot and count with no pager. Redact before persistence; never execute log text. Check journald and application retention separately. Vacuum/deletion are planned retention mutations, not generic disk repair. Core dumps can hold process secrets and need controlled access/storage.

Sources: [service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html), [unit](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html), [journalctl](https://www.freedesktop.org/software/systemd/man/latest/journalctl.html), [timer](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html).
