# Ephemeral GitHub-hosted Windows fixture only. Never run against an AD host.
[CmdletBinding()]param([Parameter(Mandatory=$true)][string]$PythonPath,[Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
function Require-Fixture($Value){if(-not $Value){throw 'Owned Windows JEA fixture prerequisite failed'}}
Require-Fixture ($env:GITHUB_ACTIONS -ceq 'true' -and $env:RUNNER_OS -ceq 'Windows' -and $env:RUNNER_ENVIRONMENT -ceq 'github-hosted' -and $env:DEVOPS_OWNED_JEA_FIXTURE -ceq '1')
Require-Fixture (-not [string]::IsNullOrWhiteSpace($env:RUNNER_TEMP))
$owner=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
Require-Fixture ($owner.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
$computer=Get-CimInstance Win32_ComputerSystem
Require-Fixture (-not $computer.PartOfDomain -and $computer.DomainRole -in @(0,2))
$tag=[guid]::NewGuid().ToString('N')
$root=Join-Path $env:RUNNER_TEMP ('devops-jea-'+$tag)
$name='DvJ'+$tag.Substring(0,10);$groupName='DvJW'+$tag.Substring(0,10);$endpoint='DevopsBound-'+$tag
$createdUser=$null;$createdGroup=$null;$certs=@();$listenerPath=$null;$mappingPath=$null;$registered=$false
$serviceBefore=(Get-Service WinRM).Status;$certificateBefore=$null
function Grant-Fixture([string]$Path,$Sid,[Security.AccessControl.FileSystemRights]$Rights,[switch]$Private){
    if((Get-Item -LiteralPath $Path).PSIsContainer){$acl=[Security.AccessControl.DirectorySecurity]::new()}else{$acl=[Security.AccessControl.FileSecurity]::new()}
    $acl.SetAccessRuleProtection($true,$false)
    foreach($identity in @('S-1-5-18','S-1-5-32-544')){
        $rule=if((Get-Item -LiteralPath $Path).PSIsContainer){[Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($identity),'FullControl','ContainerInherit,ObjectInherit','None','Allow')}else{[Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($identity),'FullControl','Allow')}
        $acl.AddAccessRule($rule)
    }
    if(-not $Private){$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($Sid,$Rights,'ContainerInherit,ObjectInherit','None','Allow'))}
    Set-Acl -LiteralPath $Path -AclObject $acl
}
try{
    $null=New-Item -ItemType Directory -Path $root
    $password=ConvertTo-SecureString ([guid]::NewGuid().ToString('N')+'aA!7') -AsPlainText -Force
    $createdUser=New-LocalUser -Name $name -Password $password -Description ('DevopsJEA '+$tag)
    $createdGroup=New-LocalGroup -Name $groupName -Description ('DevopsJEA '+$tag)
    Grant-Fixture $root $createdGroup.SID ([Security.AccessControl.FileSystemRights]::ReadAndExecute)
    & $PythonPath (Join-Path $SourceRoot 'tests/native_windows_endpoint.py') certificates --folder $root --username $name
    Require-Fixture ($LASTEXITCODE -eq 0)
    foreach($file in @('server.key','server.pfx','client.key')){Grant-Fixture (Join-Path $root $file) $createdGroup.SID ([Security.AccessControl.FileSystemRights]::Read) -Private}
    $state=Join-Path $root 'state';$moduleRoot=Join-Path $root 'module'
    $null=New-Item -ItemType Directory -Path $state;$null=New-Item -ItemType Directory -Path $moduleRoot
    Grant-Fixture $state $createdGroup.SID ([Security.AccessControl.FileSystemRights]::Modify)
    Grant-Fixture $moduleRoot $createdGroup.SID ([Security.AccessControl.FileSystemRights]::ReadAndExecute)
    [IO.File]::WriteAllBytes((Join-Path $state 'target.lock'),[byte[]]@())
    [IO.File]::WriteAllText((Join-Path $state 'value.txt'),'before')
    Copy-Item -LiteralPath (Join-Path $SourceRoot 'tools/windows_endpoint/DevopsEndpoint.psm1') -Destination (Join-Path $moduleRoot 'DevopsEndpoint.psm1')
    $valuePath=(Join-Path $state 'value.txt').Replace("'","''")
    @'
param($Parameters,$Context)
$ErrorActionPreference='Stop'
[IO.File]::WriteAllText('__VALUE_PATH__',$Parameters['value'])
if($Parameters['value'] -ceq 'fail'){throw 'Synthetic failure after write'}
@{state=$Parameters['value']}
'@.Replace('__VALUE_PATH__',$valuePath) | Set-Content -LiteralPath (Join-Path $moduleRoot 'canary-write.ps1') -Encoding utf8
    $taskHash='sha256:'+(Get-FileHash -LiteralPath (Join-Path $moduleRoot 'canary-write.ps1') -Algorithm SHA256).Hash.ToLowerInvariant()
    $binding='sha256:'+('b'*64)
    Start-Service WinRM
    $certificateBefore=(Get-Item WSMan:\localhost\Service\Auth\Certificate).Value
    Set-Item WSMan:\localhost\Service\Auth\Certificate -Value $true
    $ca=Import-Certificate -FilePath (Join-Path $root 'ca.pem') -CertStoreLocation Cert:\LocalMachine\Root
    $certs+=@{Path=('Cert:\LocalMachine\Root\'+$ca.Thumbprint);Private=$false}
    $server=Import-PfxCertificate -FilePath (Join-Path $root 'server.pfx') -CertStoreLocation Cert:\LocalMachine\My
    $certs+=@{Path=('Cert:\LocalMachine\My\'+$server.Thumbprint);Private=$true}
    $client=Import-Certificate -FilePath (Join-Path $root 'client.pem') -CertStoreLocation Cert:\LocalMachine\TrustedPeople
    $certs+=@{Path=('Cert:\LocalMachine\TrustedPeople\'+$client.Thumbprint);Private=$false}
    $existing=@(Get-ChildItem WSMan:\localhost\Listener | Where-Object {$_.Keys -contains 'Transport=HTTPS' -and $_.Keys -contains 'Address=IP:127.0.0.1'})
    Require-Fixture ($existing.Count -eq 0)
    $portProbe=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0);$portProbe.Start();$port=$portProbe.LocalEndpoint.Port;$portProbe.Stop()
    $listener=New-Item WSMan:\localhost\Listener -Address 'IP:127.0.0.1' -Transport HTTPS -Port $port -CertificateThumbprint $server.Thumbprint
    $listenerPath=$listener.PSPath
    $credential=[pscredential]::new(($env:COMPUTERNAME+'\'+$name),$password)
    $mapping=New-Item WSMan:\localhost\ClientCertificate -Subject ($name+'@localhost') -URI ('http://schemas.microsoft.com/powershell/'+$endpoint) -Issuer $ca.Thumbprint -Credential $credential
    $mappingPath=$mapping.PSPath
    $target=@{kind='windows-jea-v1';server='localhost';port=$port;configuration_name=$endpoint;ca_file=(Join-Path $root 'ca.pem');authentication=@{method='certificate';certificate_pem=(Join-Path $root 'client.pem');certificate_key_pem=(Join-Path $root 'client.key')};binding_digest=$binding}
    $target|ConvertTo-Json -Depth 6 -Compress|Set-Content -LiteralPath (Join-Path $root 'target.json') -Encoding utf8
    $digest=& $PythonPath (Join-Path $SourceRoot 'tests/native_windows_endpoint.py') digest --folder $root
    Require-Fixture ($LASTEXITCODE -eq 0 -and $digest -cmatch '^sha256:[0-9a-f]{64}$')
    $boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o');$safeState=$state.Replace("'","''")
    @"
@{SchemaVersion='1.0';TargetId='fixture-target';BindingDigest='$binding';TargetDigest='$digest';BootId='$boot';StatePath='$safeState';Tasks=@{'canary-write'=@{File='canary-write.ps1';SHA256='$taskHash';Parameters=@{value=@{Enum=@('before','after','fail')}};Result=@{state=@{Enum=@('before','after')}}}}}
"@ | Set-Content -LiteralPath (Join-Path $moduleRoot 'endpoint.psd1') -Encoding utf8
    $rolePath=Join-Path $moduleRoot 'DevopsBoundRole.psrc'
    New-PSRoleCapabilityFile -Path $rolePath -VisibleFunctions @('Get-DevopsEndpointBinding','Get-DevopsBoundTaskStatus','Invoke-DevopsBoundTask')
    $roles=@{};$roles[$env:COMPUTERNAME+'\'+$name]=@{RoleCapabilityFiles=@($rolePath)}
    $sessionPath=Join-Path $moduleRoot 'endpoint.pssc'
    New-PSSessionConfigurationFile -Path $sessionPath -SessionType RestrictedRemoteServer -LanguageMode NoLanguage -RunAsVirtualAccount -RunAsVirtualAccountGroups @($groupName) -ModulesToImport @((Join-Path $moduleRoot 'DevopsEndpoint.psm1')) -RoleDefinitions $roles
    Require-Fixture (Test-PSSessionConfigurationFile -Path $sessionPath)
    Register-PSSessionConfiguration -Name $endpoint -Path $sessionPath -NoServiceRestart -Force | Out-Null;$registered=$true
    Restart-Service WinRM -Force
    & $PythonPath (Join-Path $SourceRoot 'tests/native_windows_endpoint.py') exercise --folder $root
    Require-Fixture ($LASTEXITCODE -eq 0)
}finally{
    if($registered){Unregister-PSSessionConfiguration -Name $endpoint -NoServiceRestart -Force | Out-Null}
    if($mappingPath){Remove-Item -LiteralPath $mappingPath -Recurse -Force}
    if($listenerPath){Remove-Item -LiteralPath $listenerPath -Recurse -Force}
    if($null -ne $certificateBefore){Set-Item WSMan:\localhost\Service\Auth\Certificate -Value $certificateBefore}
    foreach($cert in $certs){if($cert.Private){Remove-Item -LiteralPath $cert.Path -DeleteKey -Force}else{Remove-Item -LiteralPath $cert.Path -Force}}
    if($createdUser){Require-Fixture ((Get-LocalUser -Name $name).SID.Value -ceq $createdUser.SID.Value);Remove-LocalUser -Name $name}
    if($createdGroup){Require-Fixture ((Get-LocalGroup -Name $groupName).SID.Value -ceq $createdGroup.SID.Value);Remove-LocalGroup -Name $groupName}
    if($registered){Restart-Service WinRM -Force}
    if($serviceBefore -eq 'Stopped'){Stop-Service WinRM -Force}
    $resolved=[IO.Path]::GetFullPath($root);$parent=[IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\')+'\'
    Require-Fixture ($resolved.StartsWith($parent,[StringComparison]::OrdinalIgnoreCase) -and [IO.Path]::GetFileName($resolved) -cmatch '^devops-jea-[a-f0-9]{32}$')
    if(Test-Path -LiteralPath $resolved){Remove-Item -LiteralPath $resolved -Recurse -Force}
}
