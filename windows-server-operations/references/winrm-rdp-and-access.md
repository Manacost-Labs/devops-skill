# WinRM, RDP and operator access

Confirm listener, exact authentication/transport, certificate binding, firewall/effective policy, intended operator and real client route. Preserve a known-good session plus an independently proven console or alternate recovery path. Two WinRM/RDP sessions on one route do not recover a disconnected host.

Use the approved secure transport/authentication for the topology. Kerberos-protected WinRM and HTTPS have different prerequisites; diagnose SPN/name/time/chain and double-hop delegation rather than enabling Basic, TrustedHosts wildcards, CredSSP or broad inbound RDP incidentally. Never disable NLA, certificate/host identity validation or firewall to get a successful connection.

Before change record effective GPO, local policy, operator group/logon rights, listener/key and rule state; verify recovery administrator/credential references. Stage narrow candidate, preserve a tested reversal, and open a new authorized session plus denied test before retiring old access. JEA/JIT, credential rotation and delegation compose with secrets-access/directory owners.

Sources: [WinRM security](https://learn.microsoft.com/en-us/powershell/scripting/security/remoting/winrm-security?view=powershell-7.5).
