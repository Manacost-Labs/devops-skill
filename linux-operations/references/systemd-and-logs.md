# systemd and logs

Use `systemctl status UNIT --no-pager` and `journalctl -u UNIT --since "..." --no-pager` to establish evidence. Inspect unit overrides with `systemctl cat UNIT` and validate changed units with `systemd-analyze verify PATH` where applicable.

For unit changes: save the previous file, edit the smallest override, run `systemctl daemon-reload`, then start/reload only the intended unit. Capture status and the relevant local health endpoint afterward.

A restart loop, OOM kill, permission error, expired certificate, missing secret reference, or unavailable dependency requires diagnosis; repeated restarts alone are not remediation. Configure log retention/forwarding with `reliability-operations`; never erase logs merely to silence disk pressure.