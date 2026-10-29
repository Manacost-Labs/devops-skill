# Target and capability baseline

Confirm OS ProductType, edition/build and server role rather than trusting a hostname/banner. Windows Server 2019/2022/2025 are procedural baselines, not a claim that all roles/features or support lifecycles match. Treat Windows desktop as out of module scope unless separately requested.

Record Server Core/Desktop Experience, PowerShell 5.1 versus 7, remoting transport, module/cmdlet availability and whether compatibility remoting returns deserialized objects. Use native role tooling for the detected build; never auto-install a feature or change execution/remoting policy just to run discovery.

Collect narrowly: UTC/boot identity, relevant roles, data/volume identity, expected service and impact window. Stopped automatic services may be trigger-start/unused; pending-reboot markers are incomplete signals, not authorization. Missing permissions or missing cmdlets mean unknown. Do not infer a healthy backup, certificate binding or task from presence alone.

For bootstrap confirm named operators, least privilege, independent console/recovery, narrow remote-management policy, time sync, maintenance/recovery ownership and service acceptance. Stage access-sensitive changes separately. Domain controllers do not have the same local-account semantics as member servers; route directory intent to its owner.
