# Source-only offline/read-only domain-lab preflight. Never mutates AD/GPO.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PlanPath,
    [switch]$ReadOnly,
    [switch]$Execute
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Require($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Read-Document([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    Require (-not $item.PSIsContainer -and -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'Document must be a regular file'
    Require ($item.Length -le 65536) 'Document exceeds size limit'
    $bytes = [IO.File]::ReadAllBytes($item.FullName)
    Require ($bytes.Length -le 65536) 'Document exceeds size limit'
    return @{ Bytes = $bytes; Text = [Text.Encoding]::UTF8.GetString($bytes).TrimStart([char]0xfeff) }
}

function Check-Guid($Value) {
    $parsed = [guid]::Empty
    Require ([guid]::TryParse([string]$Value, [ref]$parsed) -and $parsed -ne [guid]::Empty) 'Exact nonempty GUID required'
}

function Check-VersionCounter($Value) {
    $integer = $Value -is [sbyte] -or $Value -is [byte] -or $Value -is [int16] -or $Value -is [uint16] -or $Value -is [int32] -or $Value -is [uint32] -or $Value -is [int64] -or $Value -is [uint64]
    Require ($integer -and $Value -ge 0) 'GPO version counter must be an observed nonnegative integer'
}

$result = [ordered]@{
    status = 'partially_verified'; execution = 'not_run'; object_recovery = 'not_run'
    gpo_recovery = 'not_run'; replication = 'not_run'; effective_policy = 'not_run'
    delegated_identity_allow_deny = 'not_run'; sysvol_fault_recovery = 'not_run'
}
try {
    if ($Execute) { throw 'Directory mutation requires a registered immutable broker task and signed R4 admission; this harness never executes mutations' }
    $planDocument = Read-Document $PlanPath
    $plan = $planDocument.Text | ConvertFrom-Json
    $keys = @('schema_version','lab_id','domain_dns','domain_guid','servers','ou_guid','object_guid','gpo_guid','backup_parent','script_sha256','timeout_seconds')
    Require ((@($plan.PSObject.Properties.Name | Sort-Object) -join ',') -eq (($keys | Sort-Object) -join ',')) 'Unexpected or missing plan field'
    Require ($plan.schema_version -eq '1.0') 'Unsupported plan schema'
    Require ($plan.lab_id -cmatch '^directory-lab-[a-z0-9-]{8,40}$') 'Unique lab identifier required'
    Require ($plan.domain_dns -cmatch '^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+test$') 'Only an explicitly isolated .test domain is accepted'
    Require (($plan.timeout_seconds -is [int] -or $plan.timeout_seconds -is [long]) -and $plan.timeout_seconds -ge 30 -and $plan.timeout_seconds -le 900) 'Timeout must be 30..900 seconds'
    foreach ($key in @('domain_guid','ou_guid','object_guid','gpo_guid')) { Check-Guid $plan.$key }
    Require ([guid]$plan.gpo_guid -notin @([guid]'31b2f340-016d-11d2-945f-00c04fb984f9',[guid]'6ac1786c-016f-11d2-945f-00c04fb984f9')) 'Default GPOs are never fixture targets'
    Require (@($plan.servers).Count -eq 2) 'Exactly two owner-prepared DCs required'
    $serverNames = @()
    $serverGuids = @()
    foreach ($server in $plan.servers) {
        Require ((@($server.PSObject.Properties.Name | Sort-Object) -join ',') -eq 'host,ntds_guid') 'Invalid server fields'
        Require ($server.host -cmatch '^[a-z0-9][a-z0-9-]{0,62}\.[a-z0-9.-]+$' -and $server.host.EndsWith('.' + $plan.domain_dns)) 'DC must be an explicit FQDN in the lab domain'
        Check-Guid $server.ntds_guid
        $serverNames += $server.host
        $serverGuids += ([guid]$server.ntds_guid).ToString()
    }
    Require (@($serverNames | Select-Object -Unique).Count -eq 2 -and @($serverGuids | Select-Object -Unique).Count -eq 2) 'DC identities must differ'
    Require ($plan.script_sha256 -cmatch '^[a-f0-9]{64}$' -and (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant() -eq $plan.script_sha256) 'Plan must bind the reviewed script digest'
    Require ([IO.Path]::IsPathRooted($plan.backup_parent) -and -not $plan.backup_parent.StartsWith('\\')) 'Backup parent must be a protected local absolute directory'
    $parent = Get-Item -LiteralPath $plan.backup_parent -Force
    Require ($parent.PSIsContainer -and -not ($parent.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'Backup parent must be a real directory'
    $backupDirectory = Join-Path $parent.FullName $plan.lab_id
    Require (-not (Test-Path -LiteralPath $backupDirectory)) 'Backup destination must be new; preserve previous evidence'
    if (-not $ReadOnly) {
        $result.execution = 'plan_validated_only'
        $result | ConvertTo-Json -Depth 5
        exit 0
    }

    Import-Module ActiveDirectory -ErrorAction Stop
    Import-Module GroupPolicy -ErrorAction Stop
    $dc = $plan.servers[0].host
    $domain = Get-ADDomain -Server $dc
    Require ($domain.DNSRoot -ieq $plan.domain_dns -and $domain.ObjectGUID -eq [guid]$plan.domain_guid) 'Live domain identity mismatch'
    $marker = 'DevopsSkillDisposable:' + $plan.lab_id
    foreach ($server in $plan.servers) {
        $controller = Get-ADDomainController -Identity $server.host -Server $server.host
        Require (-not $controller.IsReadOnly -and $controller.Domain -ieq $plan.domain_dns -and $controller.HostName -ieq $server.host) 'Expected writable lab DC missing'
        $ntds = Get-ADObject -Identity $controller.NTDSSettingsObjectDN -Server $server.host
        Require ($ntds.ObjectGUID -eq [guid]$server.ntds_guid) 'Live DC identity mismatch'
        $replicas = @(Get-ADReplicationPartnerMetadata -Target $server.host -Partition $domain.DistinguishedName -PartnerType Inbound)
        Require ($replicas.Count -gt 0) 'No replication partners observed'
        foreach ($replica in $replicas) {
            Require ($replica.LastReplicationResult -eq 0 -and $replica.ConsecutiveReplicationFailures -eq 0 -and $replica.LastReplicationSuccess -gt (Get-Date).AddMinutes(-15)) 'Replication baseline is not healthy and recent'
        }
        Require (@(Get-ADReplicationFailure -Target $server.host -Scope Server).Count -eq 0) 'Replication failures exist'
        Require (Test-Path -LiteralPath ('\\' + $server.host + '\SYSVOL\' + $plan.domain_dns)) 'SYSVOL unavailable'
        Require (Test-Path -LiteralPath ('\\' + $server.host + '\NETLOGON')) 'NETLOGON unavailable'
    }
    $ou = Get-ADOrganizationalUnit -Identity ([guid]$plan.ou_guid) -Server $dc -Properties description
    Require ($ou.Description -ceq $marker) 'OU lacks exact live disposable marker'
    $user = Get-ADUser -Identity ([guid]$plan.object_guid) -Server $dc -Properties description,adminCount,memberOf,servicePrincipalName,primaryGroupID,sIDHistory
    Require ($user.Description -ceq $marker -and -not $user.Enabled -and -not $user.adminCount -and @($user.memberOf).Count -eq 0 -and @($user.servicePrincipalName).Count -eq 0 -and $user.primaryGroupID -eq 513 -and @($user.sIDHistory).Count -eq 0) 'User is not a disabled nonprivileged disposable fixture'
    Require ($user.DistinguishedName.Substring($user.DistinguishedName.IndexOf(',') + 1) -ieq $ou.DistinguishedName) 'User must be directly inside exact fixture OU'
    $recycle = Get-ADOptionalFeature -Identity 'Recycle Bin Feature' -Server $dc
    Require (@($recycle.EnabledScopes).Count -gt 0) 'Recycle Bin must already be enabled before fixture deletion'
    $gpo = Get-GPO -Guid ([guid]$plan.gpo_guid) -Domain $plan.domain_dns -Server $dc
    Require ($gpo.Description -ceq $marker -and $gpo.Id -notin @([guid]'31b2f340-016d-11d2-945f-00c04fb984f9',[guid]'6ac1786c-016f-11d2-945f-00c04fb984f9')) 'Dedicated nondefault disposable GPO required'
    $versions = @()
    foreach ($server in $plan.servers) {
        $copy = Get-GPO -Guid ([guid]$plan.gpo_guid) -Domain $plan.domain_dns -Server $server.host
        foreach ($counter in @($copy.User.DSVersion, $copy.User.SysvolVersion, $copy.Computer.DSVersion, $copy.Computer.SysvolVersion)) { Check-VersionCounter $counter }
        Require ($copy.User.DSVersion -eq $copy.User.SysvolVersion -and $copy.Computer.DSVersion -eq $copy.Computer.SysvolVersion) 'Local GPC/GPT versions differ'
        $versions += "$($copy.User.DSVersion):$($copy.Computer.DSVersion)"
    }
    Require (@($versions | Select-Object -Unique).Count -eq 1) 'GPO versions differ across DCs'
    $result.replication = 'observed_fixture_baseline_only'
    $result.execution = 'readonly_preflight_completed'
    $result.observed_at = [DateTime]::UtcNow.ToString('o')
    $result | ConvertTo-Json -Depth 5
    exit 0
} catch {
    $result.execution = 'refused_or_incomplete'
    $result.error = $_.Exception.Message
    $result | ConvertTo-Json -Depth 5
    exit 2
}
