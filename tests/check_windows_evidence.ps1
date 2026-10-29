[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$ScratchRoot)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
. (Join-Path $repo 'windows-server-operations/scripts/windows-evidence.ps1')
function Assert-True([bool]$Condition,[string]$Message) { if (-not $Condition) { throw $Message } }

$root = Get-WindowsLocalEvidenceItem $ScratchRoot
Assert-True ($root.PSIsContainer -and $root.Name.StartsWith('windows-unit-')) 'owned scratch root required'
$path = Join-Path $root.FullName 'descriptor.txt'
[IO.File]::WriteAllText($path,'synthetic fixture')
$descriptor = Get-WindowsFileSecurityEvidence -LiteralPath $path -IncludeSddl
Assert-True ($descriptor.effective_access -eq 'not_evaluated' -and $descriptor.sacl -eq 'not_collected') 'descriptor must not assert effective access'
Assert-True ($descriptor.descriptor_sha256 -match '^[0-9a-f]{64}$' -and $descriptor.owner_sid -match '^S-') 'native descriptor identity/hash missing'
Assert-True ([string]::IsNullOrEmpty((Get-WindowsFileSecurityEvidence -LiteralPath $path).owner_group_dacl_sddl)) 'SDDL should be opt-in'
foreach ($bad in @('Registry::HKEY_LOCAL_MACHINE\x','C:\example:stream','\\server\share\file')) {
    $rejected = $false
    try { Get-WindowsLocalEvidenceItem $bad | Out-Null } catch { $rejected = $true }
    Assert-True $rejected 'nonlocal/provider/stream path accepted'
}

$xml = '<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Principals><Principal id="p"><UserId>secret-marker</UserId><LogonType>S4U</LogonType><RunLevel>HighestAvailable</RunLevel></Principal></Principals><Triggers><BootTrigger/></Triggers><Actions Context="p"><Exec><Command>secret-marker</Command><Arguments>secret-marker</Arguments></Exec></Actions></Task>'
$summary = Get-WindowsTaskXmlEvidence -Bytes ([Text.Encoding]::UTF8.GetBytes($xml))
Assert-True ($summary.principal_count -eq 1 -and $summary.action_types[0] -eq 'Exec' -and $summary.logon_types[0] -eq 'S4U') 'task structure mismatch'
Assert-True (-not $summary.schema_validated -and -not $summary.execution_authorized) 'task parser cannot grant execution'
Assert-True (($summary | ConvertTo-Json -Depth 8) -notmatch 'secret-marker') 'task content leaked'
$invalidEnum = $xml.Replace('HighestAvailable','secret-marker').Replace('S4U','secret-marker')
$hidden = Get-WindowsTaskXmlEvidence -Bytes ([Text.Encoding]::UTF8.GetBytes($invalidEnum))
Assert-True (($hidden | ConvertTo-Json -Depth 8) -notmatch 'secret-marker') 'invalid enum leaked'
foreach ($badXml in @('<!DOCTYPE Task [<!ENTITY x SYSTEM "file:///C:/never-read">]><Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">&x;</Task>', '<Task xmlns="urn:wrong"/>', '<Task>', ('x'*262145))) {
    $rejected = $false
    try { Get-WindowsTaskXmlEvidence -Bytes ([Text.Encoding]::UTF8.GetBytes($badXml)) | Out-Null } catch { $rejected = $true }
    Assert-True $rejected 'invalid/DTD/oversized XML accepted'
}

$rsa = [Security.Cryptography.RSA]::Create(2048)
$certificate = $null
try {
    $request = [Security.Cryptography.X509Certificates.CertificateRequest]::new('CN=fixture.invalid',$rsa,[Security.Cryptography.HashAlgorithmName]::SHA256,[Security.Cryptography.RSASignaturePadding]::Pkcs1)
    $certificate = $request.CreateSelfSigned([DateTimeOffset]::UtcNow.AddDays(-2),[DateTimeOffset]::UtcNow.AddDays(-1))
    $evidence = Get-WindowsCertificateEvidence $certificate
    Assert-True ($evidence.time_state -eq 'expired' -and $evidence.has_private_key) 'certificate metadata mismatch'
    Assert-True ($evidence.service_key_access -eq 'not_verified' -and $evidence.trust_name_revocation -eq 'not_verified') 'certificate helper overclaimed trust/key use'
} finally { if ($certificate) { $certificate.Dispose() }; $rsa.Dispose() }

# Mock every host probe; no workstation service/registry/share/task collection occurs.
$script:Desktop = $false
$script:AfterIdentity = 0
function Get-CimInstance {
    [CmdletBinding()] param([string]$ClassName,[string]$Filter,[int]$OperationTimeoutSec)
    if ($ClassName -eq 'Win32_OperatingSystem') { return [pscustomobject]@{ProductType=$(if($script:Desktop){1}else{3});Version='10.0.26100';BuildNumber='26100';Caption='Synthetic Server'} }
    $script:AfterIdentity++
    if ($ClassName -eq 'Win32_LogicalDisk') { return [pscustomobject]@{DeviceID='X:';FileSystem='NTFS';Size=$null;FreeSpace=$null} }
    return [pscustomobject]@{Name='trigger-start-candidate';State='Stopped';StartMode='Auto';PathName='secret-marker';StartName='secret-marker'}
}
function Get-WinEvent { [CmdletBinding()] param($FilterHashtable,$MaxEvents) return [pscustomobject]@{TimeCreated=[DateTime]::UtcNow;Id=1;RecordId=5;ProviderName='fixture';Message='secret-marker'} }
function Get-NetFirewallProfile { [CmdletBinding()] param() throw 'secret-marker collection denied' }
function Get-NetTCPConnection { [CmdletBinding()] param($State) 1..4 | ForEach-Object { [pscustomobject]@{LocalAddress='127.0.0.1';LocalPort=$_} } }
function Get-SmbShare { [CmdletBinding()] param() throw 'secret-marker missing role' }
function Get-ScheduledTask { [CmdletBinding()] param() return [pscustomobject]@{TaskName='fixture';State='Disabled';Actions='secret-marker'} }
function Get-Disk { [CmdletBinding()] param() return @() }
function Test-Path { [CmdletBinding()] param($LiteralPath) return $false }
$audit = Get-WindowsServerEvidence -Limit 2
$json = $audit | ConvertTo-Json -Depth 8
Assert-True ($audit.status -eq 'discovery_only' -and $audit.verification -eq 'not_assessed') 'audit overclaimed verification'
Assert-True (($audit.sections | Where-Object name -eq 'firewall_profiles').status -eq 'unknown') 'denied probe was not unknown'
Assert-True (($audit.sections | Where-Object name -eq 'listeners').truncated) 'truncation lost'
Assert-True ($null -eq ($audit.sections | Where-Object name -eq 'volumes').entries[0].size_bytes) 'unknown capacity became zero'
Assert-True ($json -notmatch 'secret-marker') 'sensitive native content leaked'
$script:Desktop = $true; $script:AfterIdentity = 0
Assert-True ((Get-WindowsServerEvidence).status -eq 'unsupported_target') 'workstation accepted as server'
Assert-True ($script:AfterIdentity -eq 0) 'workstation discovery continued after identity'
Write-Output 'OK: native descriptor, safe XML, in-memory certificate and failure-aware mocked host evidence'
