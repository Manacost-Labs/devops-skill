# Dedicated disposable hosted Windows Server fixture. Never run on an operating target.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows' -or -not $env:RUNNER_TEMP) { throw 'disposable GitHub Windows runner required' }
$os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
if ($os.ProductType -notin 2,3) { throw 'Windows Server fixture required' }
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'elevated disposable runner required' }
$repo = Split-Path $PSScriptRoot -Parent
. (Join-Path $repo 'windows-server-operations/scripts/windows-evidence.ps1')
function Assert-Fixture([bool]$Condition,[string]$Message) { if (-not $Condition) { throw $Message } }
$parent = (Get-WindowsLocalEvidenceItem $env:RUNNER_TEMP).FullName.TrimEnd('\')
$tag = 'devops-' + [Guid]::NewGuid().ToString('N')
$root = [IO.Path]::GetFullPath((Join-Path $parent $tag))
Assert-Fixture ($root.StartsWith($parent+'\',[StringComparison]::OrdinalIgnoreCase) -and -not (Test-Path -LiteralPath $root)) 'owned new fixture path required'
New-Item -ItemType Directory -Path $root | Out-Null
$shareCreated=$false; $taskCreated=$false; $thumbprint=$null; $vhd=$null; $diskIdentity=$null
$cleanupFailures = [Collections.Generic.List[string]]::new()
function Get-OwnedFixtureDisk {
    $image = Get-DiskImage -ImagePath $vhd -ErrorAction Stop
    Assert-Fixture ($image.Attached -and $image.ImagePath -eq $vhd -and $image.Size -eq 96MB) 'owned VHD identity/size changed'
    Assert-Fixture ($image.DevicePath -match '^\\\\\.\\PhysicalDrive([0-9]+)$') 'unexpected VHD device mapping'
    $number = [int]$Matches[1]
    $disk = Get-Disk -Number $number -ErrorAction Stop
    Assert-Fixture (-not $disk.IsBoot -and -not $disk.IsSystem -and $disk.Number -gt 0 -and $disk.Size -eq 96MB) 'refuse nonfixture/boot/system disk'
    if ($script:diskIdentity) { Assert-Fixture ($disk.UniqueId -eq $script:diskIdentity) 'fixture disk immutable identity changed' }
    return $disk
}
try {
    # Actual NTFS allow/deny, descriptor restoration and non-destructive file recovery.
    $source=Join-Path $root 'source'; $backup=Join-Path $root 'backup'
    New-Item -ItemType Directory -Path $source,$backup | Out-Null
    $file=Join-Path $source 'payload.txt'
    [IO.File]::WriteAllText($file,'known-good-data')
    $expectedHash=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash
    $savedAcl=Get-Acl -LiteralPath $file
    $savedEvidence=Get-WindowsFileSecurityEvidence $file -IncludeSddl
    $deny=[Security.AccessControl.FileSystemAccessRule]::new($identity.User,[Security.AccessControl.FileSystemRights]::WriteData,[Security.AccessControl.AccessControlType]::Deny)
    $changed=Get-Acl -LiteralPath $file; $changed.AddAccessRule($deny); Set-Acl -LiteralPath $file -AclObject $changed
    $denied=$false
    try { [IO.File]::WriteAllText($file,'must-not-write') } catch { $denied=$_.Exception.GetBaseException() -is [UnauthorizedAccessException] }
    Assert-Fixture $denied 'native denied-write check did not deny'
    Set-Acl -LiteralPath $file -AclObject $savedAcl
    Assert-Fixture ((Get-WindowsFileSecurityEvidence $file).descriptor_sha256 -eq $savedEvidence.descriptor_sha256) 'descriptor rollback mismatch'
    & robocopy.exe $source $backup 'payload.txt' /COPY:DATS /R:0 /W:0 /XJ /NP /NFL /NDL /NJH /NJS | Out-Null
    Assert-Fixture ($LASTEXITCODE -lt 8) 'fixture backup copy failed'
    [IO.File]::WriteAllText($file,'damaged')
    & robocopy.exe $backup $source 'payload.txt' /COPY:DATS /R:0 /W:0 /XJ /NP /NFL /NDL /NJH /NJS | Out-Null
    Assert-Fixture ($LASTEXITCODE -lt 8 -and (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -eq $expectedHash) 'file restoration failed'
    Assert-Fixture ((Get-WindowsFileSecurityEvidence $file).descriptor_sha256 -eq $savedEvidence.descriptor_sha256) 'restored DACL differs'
    Write-Output 'OK: native NTFS deny, exact descriptor rollback and file-content/DACL restore'

    # Restrict the synthetic share to this runner identity; never open firewall/guest.
    Assert-Fixture (-not (Get-SmbShare -Name $tag -ErrorAction SilentlyContinue)) 'share name collision'
    New-SmbShare -Name $tag -Path $source -FullAccess $identity.Name -EncryptData $true -FolderEnumerationMode AccessBased -CachingMode None -Description $tag | Out-Null
    $shareCreated=$true
    $share=Get-SmbShare -Name $tag
    $shareAccess=@(Get-SmbShareAccess -Name $tag)
    Assert-Fixture ($share.Path -eq $source -and $share.EncryptData -and $shareAccess.Count -eq 1 -and $shareAccess[0].AccountName -eq $identity.Name) 'restricted SMB definition mismatch'
    Write-Output 'OK: restricted SMB share metadata and ACL; no remote-client access claim'

    # Register/export a disabled, least-privilege definition; never execute imported work.
    $action=New-ScheduledTaskAction -Execute (Join-Path $PSHOME 'powershell.exe') -Argument '-NoProfile -NonInteractive -Command "exit 0"'
    $principal=New-ScheduledTaskPrincipal -UserId $identity.User.Value -LogonType Interactive -RunLevel Limited
    $settings=New-ScheduledTaskSettingsSet -Disable
    $definition=New-ScheduledTask -Action $action -Principal $principal -Settings $settings -Description $tag
    Assert-Fixture (-not (Get-ScheduledTask -TaskName $tag -TaskPath '\' -ErrorAction SilentlyContinue)) 'task name collision'
    Register-ScheduledTask -TaskName $tag -TaskPath '\' -InputObject $definition | Out-Null
    $taskCreated=$true
    $task=Get-ScheduledTask -TaskName $tag -TaskPath '\'
    $xml=Export-ScheduledTask -TaskName $tag -TaskPath '\'
    $summary=Get-WindowsTaskXmlEvidence -Bytes ([Text.Encoding]::Unicode.GetBytes($xml))
    Assert-Fixture ($task.State -eq 'Disabled' -and $summary.action_types[0] -eq 'Exec' -and -not $summary.execution_authorized) 'task definition roundtrip failed'
    Write-Output 'OK: disabled Task Scheduler registration/export and safe structural inspection'

    # CurrentUser only, no trust-root import/binding. Export/import and actual key use.
    $cert=New-SelfSignedCertificate -DnsName 'fixture.invalid' -CertStoreLocation 'Cert:\CurrentUser\My' -KeyAlgorithm RSA -KeyLength 2048 -KeyExportPolicy Exportable -FriendlyName $tag -NotAfter (Get-Date).AddDays(1)
    $thumbprint=$cert.Thumbprint
    $certificatePath='Cert:\CurrentUser\My\'+$thumbprint
    $secret=[Security.SecureString]::new()
    $random=[byte[]]::new(32); $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($random); foreach($value in $random) { foreach($character in $value.ToString('x2').ToCharArray()) { $secret.AppendChar($character) } } } finally { $rng.Dispose(); [Array]::Clear($random,0,$random.Length) }
    $pfx=Join-Path $root 'fixture.pfx'
    Export-PfxCertificate -Cert $cert -FilePath $pfx -Password $secret -CryptoAlgorithmOption AES256_SHA256 -NoClobber | Out-Null
    Assert-Fixture ((Get-Item -LiteralPath $certificatePath).FriendlyName -eq $tag) 'certificate ownership changed'
    Remove-Item -LiteralPath $certificatePath -DeleteKey -Confirm:$false
    $restored=Import-PfxCertificate -FilePath $pfx -CertStoreLocation 'Cert:\CurrentUser\My' -Password $secret
    $evidence=Get-WindowsCertificateEvidence $restored
    Assert-Fixture ($restored.Thumbprint -eq $thumbprint -and $restored.HasPrivateKey -and $evidence.trust_name_revocation -eq 'not_verified') 'certificate/private-key roundtrip failed'
    $private=[Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($restored)
    $public=[Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPublicKey($restored)
    try {
        $data=[Text.Encoding]::UTF8.GetBytes('synthetic-key-use')
        $signature=$private.SignData($data,[Security.Cryptography.HashAlgorithmName]::SHA256,[Security.Cryptography.RSASignaturePadding]::Pkcs1)
        Assert-Fixture ($public.VerifyData($data,$signature,[Security.Cryptography.HashAlgorithmName]::SHA256,[Security.Cryptography.RSASignaturePadding]::Pkcs1)) 'restored key unusable'
    } finally { $private.Dispose(); $public.Dispose(); $secret.Dispose() }
    Write-Output 'OK: CurrentUser PFX export/import and restored-key signing; no service/trust claim'

    # New 96-MiB backing file only. Never select a disk by ambient number alone.
    $vhd=Join-Path $root 'fixture.vhdx'
    $commands=Join-Path $root 'create-vhd.txt'
    Assert-Fixture ($vhd -notmatch '["\r\n]' -and -not (Test-Path -LiteralPath $vhd)) 'unsafe VHD path'
    [IO.File]::WriteAllText($commands,"create vdisk file=`"$vhd`" maximum=96 type=expandable`r`nselect vdisk file=`"$vhd`"`r`nattach vdisk`r`nexit`r`n",[Text.Encoding]::ASCII)
    & diskpart.exe /s $commands | Out-Null
    Assert-Fixture ($LASTEXITCODE -eq 0) 'fixture VHD creation/attach failed'
    $disk=Get-OwnedFixtureDisk
    Assert-Fixture ($disk.PartitionStyle -eq 'RAW' -and $disk.UniqueId) 'fixture must be a new RAW disk'
    $script:diskIdentity=$disk.UniqueId
    Initialize-Disk -Number (Get-OwnedFixtureDisk).Number -PartitionStyle GPT | Out-Null
    $partition=New-Partition -DiskNumber (Get-OwnedFixtureDisk).Number -UseMaximumSize -AssignDriveLetter
    Get-OwnedFixtureDisk | Out-Null
    $volume=Format-Volume -Partition $partition -FileSystem NTFS -NewFileSystemLabel $tag.Substring(0,20) -Confirm:$false
    $volumePath=([string]$volume.DriveLetter)+':\proof.txt'
    [IO.File]::WriteAllText($volumePath,'owned-vhd-data')
    Assert-Fixture ([IO.File]::ReadAllText($volumePath) -eq 'owned-vhd-data') 'fixture filesystem I/O failed'
    Dismount-DiskImage -ImagePath $vhd
    Mount-DiskImage -ImagePath $vhd | Out-Null
    $disk=Get-OwnedFixtureDisk
    $dataPartition=Get-Partition -DiskNumber $disk.Number | Where-Object DriveLetter | Select-Object -First 1
    Assert-Fixture ($null -ne $dataPartition) 'fixture mount did not return'
    Assert-Fixture ([IO.File]::ReadAllText(([string]$dataPartition.DriveLetter)+':\proof.txt') -eq 'owned-vhd-data') 'VHD reattach persistence failed'
    Write-Output 'OK: exact backing-file VHD identity, NTFS initialization and detach/reattach data persistence'

    $audit=Get-WindowsServerEvidence -Limit 5
    Assert-Fixture ($audit.status -eq 'discovery_only' -and $audit.verification -eq 'not_assessed') 'native server audit failed'
    Write-Output 'OK: native Windows Server discovery preserves unknown/partial semantics'
} finally {
    if ($taskCreated) { try { $task=Get-ScheduledTask -TaskName $tag -TaskPath '\'; Assert-Fixture ($task.Description -eq $tag) 'task cleanup ownership drift'; Unregister-ScheduledTask -TaskName $tag -TaskPath '\' -Confirm:$false } catch { $cleanupFailures.Add('task cleanup failed') } }
    if ($shareCreated) { try { $share=Get-SmbShare -Name $tag; Assert-Fixture ($share.Path -eq (Join-Path $root 'source') -and $share.Description -eq $tag) 'share cleanup ownership drift'; Remove-SmbShare -Name $tag -Confirm:$false } catch { $cleanupFailures.Add('share cleanup failed') } }
    if ($thumbprint) { try { $path='Cert:\CurrentUser\My\'+$thumbprint; $owned=Get-Item -LiteralPath $path -ErrorAction SilentlyContinue; if ($owned) { Assert-Fixture ($owned.FriendlyName -eq $tag) 'certificate cleanup ownership drift'; Remove-Item -LiteralPath $path -DeleteKey -Confirm:$false } } catch { $cleanupFailures.Add('certificate cleanup failed') } }
    if ($vhd -and (Test-Path -LiteralPath $vhd)) { try { $image=Get-DiskImage -ImagePath $vhd; if ($image.Attached) { Get-OwnedFixtureDisk | Out-Null; Dismount-DiskImage -ImagePath $vhd }; Assert-Fixture (-not (Get-DiskImage -ImagePath $vhd).Attached) 'VHD remains attached' } catch { $cleanupFailures.Add('VHD cleanup failed') } }
    if ($cleanupFailures.Count -eq 0) {
        try {
            $resolved=(Get-WindowsLocalEvidenceItem $root).FullName
            Assert-Fixture ($resolved -eq $root -and $resolved.StartsWith($parent+'\',[StringComparison]::OrdinalIgnoreCase) -and (Split-Path $resolved -Leaf) -eq $tag) 'cleanup path escaped owned workspace'
            Assert-Fixture (-not (Get-ChildItem -LiteralPath $resolved -Recurse -Force | Where-Object { ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 })) 'refuse recursive cleanup through reparse point'
            Remove-Item -LiteralPath $resolved -Recurse -Force
        } catch { $cleanupFailures.Add('file cleanup failed') }
    }
    if ($cleanupFailures.Count) { throw ($cleanupFailures -join '; ') }
}
