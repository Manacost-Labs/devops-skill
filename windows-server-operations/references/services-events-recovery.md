# Services, events and resource diagnosis

Confirm the exact service, identity/dependencies, expected workload and change timeline. Preserve selected service status/configuration and a bounded System/Application/service event interval before restart. Avoid raw service command lines/environment and event payloads in general reports: they can contain secrets and attacker instructions.

A stopped automatic service is not automatically failed; trigger/delayed start, disabled dependencies and legitimate idle behavior need context. Investigate startup exit/result, dependency, executable/configuration path, file/key permissions, resource limits and the user endpoint. Do not restart repeatedly or clear logs to make the report quiet.

For pressure correlate CPU queue/usage, available/committed memory, paging, handle/thread demand, disk latency/queues, service process and user impact over one interval. One cumulative count or Task Manager snapshot is not a cause. Use approved bounded performance collection; do not launch a broad collector install or dump processes/credentials.

Service identity changes affect file/network/key access and secrets; compose the owning modules. Preserve exact before-state, binary/config version and recovery. Reload only when the service supports it; restart/reboot require workload drain and data/availability decisions. Verify service plus real endpoint/identity, Event Log interval and observation window.

Sources: [Get-WinEvent](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.diagnostics/get-winevent?view=powershell-5.1), [Get-Service](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-service?view=powershell-5.1).
