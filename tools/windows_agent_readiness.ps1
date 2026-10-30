# Run from the actual, fresh Codex execution identity. Makes no changes.
[CmdletBinding()]param(
    [Parameter(Mandatory=$true)][ValidatePattern('^S-1-5-21-(?:[0-9]+-){3}[0-9]+$')][string]$ExpectedAgentSid,
    [Parameter(Mandatory=$true)][string[]]$ProtectedCanaryFiles
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$reasons=New-Object 'Collections.Generic.List[string]'
if($identity.User.Value -cne $ExpectedAgentSid){$reasons.Add('wrong_execution_identity')}
# Deny-only Administrators membership still means an owner/admin identity under
# UAC. It is not a genuinely separate, unprivileged agent account.
$forbidden=@('S-1-5-32-544','S-1-5-32-548','S-1-5-32-549','S-1-5-32-550','S-1-5-32-551','S-1-5-32-578')
foreach($group in $identity.Groups){
    if($forbidden -ccontains $group.Value -or $group.Value -match '-(512|518|519)$'){$reasons.Add('privileged_group_membership')}
}
try {
    $dockerGroup=Get-LocalGroup -Name 'docker-users' -ErrorAction Stop
    if(@($identity.Groups | ForEach-Object Value) -ccontains $dockerGroup.SID.Value){$reasons.Add('docker_control')}
} catch [Microsoft.PowerShell.Commands.GroupNotFoundException] { }
catch {$reasons.Add('group_inventory_unavailable')}
if($ProtectedCanaryFiles.Count -lt 1 -or $ProtectedCanaryFiles.Count -gt 32){$reasons.Add('invalid_canary_list')}
# These are owner-created nonsecret canaries, never an issuer key/credential.
# Merely opening a handle proves a read/write breach without reading bytes or
# truncating/creating a file. Missing paths are incomplete evidence, not denial.
if($reasons.Count -eq 0){
    foreach($path in $ProtectedCanaryFiles){
        if(-not [IO.Path]::IsPathRooted($path)){$reasons.Add('invalid_canary_path');continue}
        foreach($mode in @([IO.FileAccess]::Read,[IO.FileAccess]::Write)){
            $handle=$null
            try{$handle=[IO.FileStream]::new($path,[IO.FileMode]::Open,$mode,[IO.FileShare]::ReadWrite);$reasons.Add('protected_canary_accessible')}
            catch [UnauthorizedAccessException] { }
            catch {$reasons.Add('canary_probe_incomplete')}
            finally{if($handle){$handle.Dispose()}}
        }
    }
}
$status=if($reasons.Count -eq 0){'identity_preflight_passed'}else{'blocked'}
@{status=$status;reasons=@($reasons | Select-Object -Unique);sid=$identity.User.Value;deployment_verified=$false;remaining=@('Native Hyper-V/Docker and target/disk denial','Managed policy and all tool surfaces','Broker grant/expiry/epoch refusals','Actual JEA capability and transport','Replay, disconnect and reconciliation')} | ConvertTo-Json -Depth 4
if($reasons.Count -ne 0){exit 3}
exit 0
