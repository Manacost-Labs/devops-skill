# AD replication and SYSVOL diagnosis

Read for a replication alert, a DC serving different policy, or missing SYSVOL/NETLOGON. Identify the exact writable DCs, naming contexts, sites, topology, relevant interval, and last known good state. Keep the first pass read-only and bounded to approved servers; raw reports expose topology and principals.

## Separate the two replication paths

AD replication carries the Group Policy Container (GPC), directory objects and links. DFS Replication carries the Group Policy Template (GPT) in SYSVOL. Success in one path does not establish success in the other. An accessible SYSVOL share does not prove up-to-date policy contents.

For each named DC, collect `Get-ADReplicationPartnerMetadata -Target <exact-dc> -Partition <exact-naming-context> -PartnerType Inbound`, `Get-ADReplicationFailure -Target <exact-dc> -Scope Server`, and, for one affected object, `Get-ADReplicationAttributeMetadata -Object <exact-dn> -Server <exact-dc>`. Capture attempted/successful replication times, result codes, failure counts, originating version/time/invocation identity and the naming context. A success before the incident or no returned partners is insufficient. USNs are local to a DC: do not compare their raw values across servers as convergence evidence. Reconcile the chosen object's actual attributes and originating metadata across the relevant replicas, after the normal schedule and within an explicit deadline.

Use `repadmin /showrepl <exact-dc>` and `dcdiag /s:<exact-dc> /test:Replications /test:SysVolCheck /test:NetLogons` when applicable to the installed build. Preserve native exit codes and per-test results. Attribute DNS locator, time/Kerberos, RPC/firewall, unavailable partners and naming-context failures to their owner; do not erase the symptom by forcing synchronization. A forest-wide summary is context, not evidence that this object or GPO converged.

## SYSVOL branch

On each relevant DC inspect SYSVOL and NETLOGON share availability, DFSR service state and bounded DFS Replication events. Investigate 2213 (paused recovery), 4012 (content freshness), and 4614 without subsequent 4604 (initial synchronization not completed); correlate times and current folder state rather than treating an old event ID as a current diagnosis. Confirm whether the domain uses DFSR; do not apply legacy FRS BurFlags recipes to DFSR.

For the exact GPO GUID, compare `Get-GPO -Guid <guid> -Domain <dns-domain> -Server <dc>` user and computer AD/SYSVOL versions on every relevant DC, and inspect that DC's explicit `\\<dc>\SYSVOL\<domain>\Policies\{<guid>}\GPT.INI` and required policy files. A domain DFS path can select a different DC. Matching version counters alone do not prove matching contents or client application; compare protected hashes of the affected files when diagnosing suspected divergence.

Stop policy changes when AD/GPT disagree, a partner is unknown, initial sync is incomplete, or no authoritative healthy copy is established. Preserve copies and metadata before a separately approved recovery. Never delete the DFSR database, set an authoritative flag, edit GPT.INI, change freshness thresholds or use `/syncall` as routine repair. Authoritative/non-authoritative SYSVOL recovery and forest/DC disaster recovery require an exact R4 topology-specific plan, a proven backup, directory owner and independent recovery access.

Official sources refreshed 2026-10-30: [replication metadata](https://learn.microsoft.com/en-us/powershell/module/activedirectory/get-adreplicationpartnermetadata?view=windowsserver2025-ps), [replication failure](https://learn.microsoft.com/en-us/powershell/module/activedirectory/get-adreplicationfailure?view=windowsserver2025-ps), [object metadata](https://learn.microsoft.com/en-us/powershell/module/activedirectory/get-adreplicationattributemetadata?view=windowsserver2025-ps), [missing SYSVOL/NETLOGON troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/windows-server/networking/troubleshoot-missing-sysvol-and-netlogon-shares).
