# Windows services, Event Logs, and recovery

For a failing service, gather `Get-Service`, `Win32_Service` start mode/path/dependencies, and bounded recent System/Application Event Logs before restart. Determine whether restart can interrupt data, jobs, or dependencies. Preserve the service configuration and previous binary/config version before change.

Use the smallest recovery: reload application configuration if supported, restart one service, then verify its local endpoint and new events. A reboot is not a generic service fix; it requires separate change control.