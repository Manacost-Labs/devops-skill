# Synthetic command-boundary regression; never connects to a real domain.
param([string]$PlanPath, [string]$MutationTrace,
    [ValidateSet('valid','valid-zero','valid-mixed','null','bool','string','negative','nan','infinite','decimal','local-mismatch','dc-mismatch','stale')][string]$Scenario,
    [ValidateRange(-1,3)][int]$CounterField = -1)
$ErrorActionPreference = 'Stop'
# Resolve PowerShell 5.1's file-hash module before mocking module imports.
$null = Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256
$global:directoryFixture = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json
$global:directoryMutationTrace = $MutationTrace
$global:directoryVersionScenario = $Scenario
$global:directoryCounterField = $CounterField
$global:directoryOuDn = 'OU=Fixture,DC=directory-lab,DC=test'
function Import-Module { param($Name,$ErrorAction) }
function Get-ADDomain { param($Server)
    [pscustomobject]@{DNSRoot=$global:directoryFixture.domain_dns; ObjectGUID=[guid]$global:directoryFixture.domain_guid; DistinguishedName='DC=directory-lab,DC=test'}
}
function Get-ADDomainController { param($Identity,$Server)
    [pscustomobject]@{IsReadOnly=$false; Domain=$global:directoryFixture.domain_dns; HostName=$Server; NTDSSettingsObjectDN=('CN=NTDS,'+$Server)}
}
function Get-ADObject { param($Identity,$Server)
    foreach ($node in $global:directoryFixture.servers) {
        if ([string]$Identity -eq ('CN=NTDS,'+$node.host)) { return [pscustomobject]@{ObjectGUID=[guid]$node.ntds_guid} }
    }
    throw 'Unexpected synthetic object query'
}
function Get-ADReplicationPartnerMetadata { param($Target,$Partition,$PartnerType)
    $success = Get-Date
    if ($global:directoryVersionScenario -eq 'stale') { $success=$success.AddHours(-1) }
    [pscustomobject]@{LastReplicationResult=0; ConsecutiveReplicationFailures=0; LastReplicationSuccess=$success}
}
function Get-ADReplicationFailure { param($Target,$Scope) }
function Test-Path { param($LiteralPath,$Path,$PathType)
    if ($LiteralPath -and ([string]$LiteralPath).StartsWith('\\')) { return $true }
    Microsoft.PowerShell.Management\Test-Path @PSBoundParameters
}
function Get-ADOrganizationalUnit { param($Identity,$Server,$Properties)
    [pscustomobject]@{Description=('DevopsSkillDisposable:'+$global:directoryFixture.lab_id); DistinguishedName=$global:directoryOuDn}
}
function Get-ADUser { param($Identity,$Server,$Properties)
    [pscustomobject]@{Description=('DevopsSkillDisposable:'+$global:directoryFixture.lab_id); Enabled=$false; adminCount=0; memberOf=@(); servicePrincipalName=@(); primaryGroupID=513; sIDHistory=@(); DistinguishedName=('CN=Fixture,'+$global:directoryOuDn)}
}
function Get-ADOptionalFeature { param($Identity,$Server)
    [pscustomobject]@{EnabledScopes=@('CN=Partitions')}
}
function Get-GPO { param($Guid,$Domain,$Server)
    $values = @([int32]1,[int32]1,[int32]2,[int32]2)
    $invalid = $true
    switch ($global:directoryVersionScenario) {
        'valid-zero' { $values=@([int32]0,[uint32]0,[uint64]0,[int64]0); $invalid=$false }
        'valid-mixed' { $values=@([uint16]1,[int64]1,[uint64]2,[byte]2); $invalid=$false }
        'null' { $bad=$null }
        'bool' { $bad=$true }
        'string' { $bad='1' }
        'negative' { $bad=[int32]-1 }
        'nan' { $bad=[double]::NaN }
        'infinite' { $bad=[double]::PositiveInfinity }
        'decimal' { $bad=[decimal]1 }
        'local-mismatch' { $values[1]=2; $invalid=$false }
        'dc-mismatch' { if ($Server -eq $global:directoryFixture.servers[1].host) { $values=@(3,3,4,4) }; $invalid=$false }
        default { $invalid=$false }
    }
    if ($invalid) {
        if ($global:directoryCounterField -eq -1) { $values=@($bad,$bad,$bad,$bad) }
        else { $values[$global:directoryCounterField]=$bad }
    }
    [pscustomobject]@{Description=('DevopsSkillDisposable:'+$global:directoryFixture.lab_id); Id=[guid]$global:directoryFixture.gpo_guid; User=[pscustomobject]@{DSVersion=$values[0]; SysvolVersion=$values[1]}; Computer=[pscustomobject]@{DSVersion=$values[2]; SysvolVersion=$values[3]}}
}
function Stop-DirectoryMutation {
    Add-Content -LiteralPath $global:directoryMutationTrace -Value 'unexpected_mutation'
    throw 'Read-only preflight attempted a mutation'
}
function Remove-ADObject { Stop-DirectoryMutation }
function Restore-ADObject { Stop-DirectoryMutation }
function Set-GPRegistryValue { Stop-DirectoryMutation }
function Restore-GPO { Stop-DirectoryMutation }
function Backup-GPO { Stop-DirectoryMutation }
& (Join-Path $PSScriptRoot 'check_identity_directory_lab.ps1') -PlanPath $PlanPath -ReadOnly
exit $LASTEXITCODE
