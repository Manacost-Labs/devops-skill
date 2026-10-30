# Independent owner bootstrap. Default is validation only; generates no keys.
[CmdletBinding()]param(
    [Parameter(Mandatory=$true)][string]$Bundle,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$ExpectedManifestSHA256,
    [switch]$Apply
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
function Require-Owner($Condition){if(-not $Condition){throw 'Owner bootstrap refused invalid or unavailable prerequisites'}}
function Read-OwnerBytes([string]$Path,[int]$Maximum){
    $stream=[IO.FileStream]::new($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try{
        Require-Owner ($stream.Length -gt 0 -and $stream.Length -le $Maximum)
        $bytes=[byte[]]::new([int]$stream.Length);$offset=0
        while($offset -lt $bytes.Length){$count=$stream.Read($bytes,$offset,$bytes.Length-$offset);Require-Owner ($count -gt 0);$offset+=$count}
        return ,$bytes
    }finally{$stream.Dispose()}
}
function Get-OwnerHash([byte[]]$Bytes){
    $algorithm=[Security.Cryptography.SHA256]::Create()
    try{return ([BitConverter]::ToString($algorithm.ComputeHash($Bytes))).Replace('-','').ToLowerInvariant()}finally{$algorithm.Dispose()}
}
function Read-OwnerData([byte[]]$Bytes){
    $parseErrors=$null;$tokens=$null
    $ast=[System.Management.Automation.Language.Parser]::ParseInput([Text.Encoding]::UTF8.GetString($Bytes).TrimStart([char]0xfeff),[ref]$tokens,[ref]$parseErrors)
    Require-Owner (@($parseErrors).Count -eq 0 -and $ast.EndBlock.Statements.Count -eq 1)
    $pipeline=$ast.EndBlock.Statements[0]
    Require-Owner ($pipeline -is [System.Management.Automation.Language.PipelineAst] -and $pipeline.PipelineElements.Count -eq 1)
    $expression=$pipeline.PipelineElements[0].Expression
    Require-Owner ($expression -is [System.Management.Automation.Language.HashtableAst])
    return $expression.SafeGetValue()
}
function Assert-RealTree([string]$Path){
    $current=Get-Item -LiteralPath $Path -Force
    while($current){Require-Owner (-not($current.Attributes -band [IO.FileAttributes]::ReparsePoint));$current=$current.Parent}
}
function Protect-Directory([string]$Path,[Security.Principal.SecurityIdentifier]$Identity,[Security.AccessControl.FileSystemRights]$Rights){
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $admins=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
    $acl.SetOwner($admins)
    foreach($sid in @($admins,[Security.Principal.SecurityIdentifier]::new('S-1-5-18'))){
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    }
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($Identity,$Rights,'ContainerInherit,ObjectInherit','None','Allow'))
    Set-Acl -LiteralPath $Path -AclObject $acl
}
try {
    $bundleItem=Get-Item -LiteralPath $Bundle -Force
    Require-Owner $bundleItem.PSIsContainer
    Assert-RealTree $bundleItem.FullName
    $manifestPath=Join-Path $bundleItem.FullName 'owner-manifest.json'
    $manifestItem=Get-Item -LiteralPath $manifestPath -Force
    Require-Owner (-not $manifestItem.PSIsContainer -and $manifestItem.Length -le 65536)
    $manifestBytes=Read-OwnerBytes $manifestPath 65536
    Require-Owner ((Get-OwnerHash $manifestBytes) -ceq $ExpectedManifestSHA256)
    $manifest=[Text.Encoding]::UTF8.GetString($manifestBytes) | ConvertFrom-Json
    $expected=@('schema_version','endpoint_name','connector','run_as_gmsa','module_root','state_root','files')
    Require-Owner ((@($manifest.PSObject.Properties.Name | Sort-Object) -join ',') -ceq (($expected | Sort-Object) -join ',') -and $manifest.schema_version -ceq '1.0')
    Require-Owner ($manifest.endpoint_name -cmatch '^DevopsBound-[a-z0-9-]{6,64}$')
    Require-Owner ($manifest.connector -cmatch '^[a-zA-Z0-9_.-]+\\[a-zA-Z0-9_.-]+$' -and $manifest.run_as_gmsa -cmatch '^[a-zA-Z0-9_.-]+\\[a-zA-Z0-9_.-]+\$$')
    $programRoot=[IO.Path]::GetFullPath($env:ProgramFiles).TrimEnd('\')+'\'
    $dataRoot=[IO.Path]::GetFullPath($env:ProgramData).TrimEnd('\')+'\'
    $moduleRoot=[IO.Path]::GetFullPath($manifest.module_root)
    $stateRoot=[IO.Path]::GetFullPath($manifest.state_root)
    Require-Owner ($moduleRoot.StartsWith($programRoot,[StringComparison]::OrdinalIgnoreCase) -and $stateRoot.StartsWith($dataRoot,[StringComparison]::OrdinalIgnoreCase))
    # New direct children only: no writable intermediate tree or overwrite.
    Require-Owner ([IO.Path]::GetDirectoryName($moduleRoot).TrimEnd('\') -ieq $programRoot.TrimEnd('\'))
    Require-Owner ([IO.Path]::GetDirectoryName($stateRoot).TrimEnd('\') -ieq $dataRoot.TrimEnd('\'))
    Require-Owner (-not(Test-Path -LiteralPath $moduleRoot) -and -not(Test-Path -LiteralPath $stateRoot))
    Assert-RealTree $env:ProgramFiles;Assert-RealTree $env:ProgramData
    $files=@($manifest.files.PSObject.Properties)
    $snapshots=@{}
    $totalBytes=0
    Require-Owner ($files.Count -ge 3 -and $files.Count -le 128)
    foreach($file in $files){
        Require-Owner ($file.Name -cmatch '^(?:[a-zA-Z][a-zA-Z0-9-]*\.(?:ps1|psm1|psd1|psrc))$' -and $file.Value -cmatch '^[a-f0-9]{64}$')
        $path=Join-Path $bundleItem.FullName $file.Name
        $item=Get-Item -LiteralPath $path -Force
        Require-Owner (-not $item.PSIsContainer -and -not($item.Attributes -band [IO.FileAttributes]::ReparsePoint))
        $bytes=Read-OwnerBytes $path (4*1024*1024)
        $totalBytes+=$bytes.Length;Require-Owner ($totalBytes -le 16*1024*1024)
        Require-Owner ((Get-OwnerHash $bytes) -ceq $file.Value)
        $snapshots[$file.Name]=$bytes
    }
    Require-Owner ($manifest.files.PSObject.Properties.Name -ccontains 'DevopsEndpoint.psm1' -and $manifest.files.PSObject.Properties.Name -ccontains 'endpoint.psd1' -and $manifest.files.PSObject.Properties.Name -ccontains 'DevopsBoundRole.psrc')
    $config=Read-OwnerData $snapshots['endpoint.psd1']
    Require-Owner ($config.StatePath -ceq $stateRoot -and $config.BootId -ceq '__OWNER_CURRENT_BOOT__')
    foreach($task in $config.Tasks.Values){Require-Owner ($manifest.files.PSObject.Properties.Name -ccontains $task.File)}
    if(-not $Apply){@{status='prepared_not_installed';endpoint=$manifest.endpoint_name;requires=@('Independent elevated owner','Existing scoped gMSA and connector','Protected HTTPS listener and source firewall','Fresh standard-user Codex context; privileged agents stopped','Effective JEA allow/deny and remote outcome acceptance')} | ConvertTo-Json -Depth 4;exit 0}
    $owner=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    Require-Owner ($owner.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
    # An opaque gMSA reference is required; no standing admin password is used.
    $runAsSid=([Security.Principal.NTAccount]::new($manifest.run_as_gmsa)).Translate([Security.Principal.SecurityIdentifier])
    $connectorSid=([Security.Principal.NTAccount]::new($manifest.connector)).Translate([Security.Principal.SecurityIdentifier])
    Require-Owner ($runAsSid.Value -cne $connectorSid.Value)
    Require-Owner ((Get-Service -Name WinRM).Status -eq 'Running')
    $https=@(Get-ChildItem WSMan:\localhost\Listener | Where-Object {$_.Keys -contains 'Transport=HTTPS'})
    Require-Owner ($https.Count -eq 1)
    Require-Owner (-not(Get-PSSessionConfiguration -Name $manifest.endpoint_name -ErrorAction SilentlyContinue))
    $null=New-Item -ItemType Directory -Path $moduleRoot
    Protect-Directory $moduleRoot $runAsSid ([Security.AccessControl.FileSystemRights]::ReadAndExecute)
    $null=New-Item -ItemType Directory -Path $stateRoot
    Protect-Directory $stateRoot $runAsSid ([Security.AccessControl.FileSystemRights]::Modify)
    # Reject unexpected content after protection, before writing any privileged
    # file. Installation never adopts a pre-populated coordination tree.
    Require-Owner ([IO.Directory]::GetFileSystemEntries($moduleRoot).Length -eq 0 -and [IO.Directory]::GetFileSystemEntries($stateRoot).Length -eq 0)
    foreach($file in $files){
        $destination=Join-Path $moduleRoot $file.Name
        [IO.File]::WriteAllBytes($destination,$snapshots[$file.Name])
        Require-Owner ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $file.Value)
    }
    $configPath=Join-Path $moduleRoot 'endpoint.psd1'
    $boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
    $configText=[IO.File]::ReadAllText($configPath).Replace('__OWNER_CURRENT_BOOT__',$boot)
    [IO.File]::WriteAllText($configPath,$configText,[Text.UTF8Encoding]::new($true))
    $newLock=[IO.FileStream]::new((Join-Path $stateRoot 'target.lock'),[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    try{$newLock.Flush($true)}finally{$newLock.Dispose()}
    # Exact role definitions and absolute module import; no default-admin VA,
    # wildcard capability, provider, external program or general AD cmdlet.
    $modulePath=Join-Path $moduleRoot 'DevopsEndpoint.psm1'
    $sessionPath=Join-Path $moduleRoot 'endpoint.pssc'
    $roles=@{};$roles[$manifest.connector]=@{RoleCapabilityFiles=@([string](Join-Path $moduleRoot 'DevopsBoundRole.psrc'))}
    New-PSSessionConfigurationFile -Path $sessionPath -SessionType RestrictedRemoteServer -LanguageMode NoLanguage -GroupManagedServiceAccount $manifest.run_as_gmsa -ModulesToImport @([string]$modulePath) -RoleDefinitions $roles
    Require-Owner (Test-PSSessionConfigurationFile -Path $sessionPath)
    Register-PSSessionConfiguration -Name $manifest.endpoint_name -Path $sessionPath -NoServiceRestart -Force | Out-Null
    @{status='installed_not_verified';endpoint=$manifest.endpoint_name;verification='Independent owner must review effective capability, start/restart endpoint in its maintenance window and complete native acceptance; this is not an execution grant'} | ConvertTo-Json -Depth 4
    exit 0
} catch {
    # Partial owner provisioning is retained for reconciliation; no recursive
    # rollback, account deletion or automatic WinRM restart is attempted.
    'OWNER_BOOTSTRAP_REFUSED_OR_PARTIAL: preserve state and reconcile; no execution authority was issued'
    exit 3
}
