# Ephemeral GitHub-hosted Windows fixture only. Never run against an AD host.
[CmdletBinding()]param([Parameter(Mandatory=$true)][string]$PythonPath,[Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
function Require-Fixture($Value,[string]$Reason='prerequisite'){if(-not $Value){throw ('Owned Windows JEA fixture failed: '+$Reason)}}
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
$fixtureStart=Get-Date;$requestStart=$fixtureStart
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
    Add-LocalGroupMember -SID ([Security.Principal.SecurityIdentifier]::new('S-1-5-32-545')) -Member $createdUser
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
    $clientTrust=Import-Certificate -FilePath (Join-Path $root 'client.pem') -CertStoreLocation Cert:\LocalMachine\Root
    $certs+=@{Path=('Cert:\LocalMachine\Root\'+$clientTrust.Thumbprint);Private=$false}
    $existing=@(Get-ChildItem WSMan:\localhost\Listener | Where-Object {$_.Keys -contains 'Transport=HTTPS' -and $_.Keys -contains 'Address=IP:127.0.0.1'})
    Require-Fixture ($existing.Count -eq 0)
    $portProbe=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0);$portProbe.Start();$port=$portProbe.LocalEndpoint.Port;$portProbe.Stop()
    $null=New-WSManInstance -ResourceURI winrm/config/Listener -SelectorSet @{Address='IP:127.0.0.1';Transport='HTTPS'} -ValueSet @{Hostname='localhost';Port=[string]$port;CertificateThumbprint=$server.Thumbprint;Enabled='true'}
    $listener=@(Get-ChildItem WSMan:\localhost\Listener | Where-Object {$_.Keys -contains 'Transport=HTTPS' -and $_.Keys -contains 'Address=IP:127.0.0.1'})
    Require-Fixture ($listener.Count -eq 1)
    $listenerPath=$listener[0].PSPath
    $credential=[pscredential]::new(($env:COMPUTERNAME+'\'+$name),$password)
    $subject=$name+'@localhost';$resourceUri='http://schemas.microsoft.com/powershell/'+$endpoint
    $existingMappings=@(Get-ChildItem WSMan:\localhost\ClientCertificate | Where-Object {$_.Keys -contains ('Subject='+$subject) -and $_.Keys -contains ('URI='+$resourceUri) -and $_.Keys -contains ('Issuer='+$client.Thumbprint)})
    Require-Fixture ($existingMappings.Count -eq 0)
    $mapping=New-Item WSMan:\localhost\ClientCertificate -Subject $subject -URI $resourceUri -Issuer $client.Thumbprint -Credential $credential -Force
    $mappingPath=$mapping.PSPath
    Require-Fixture ($client.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::UpnName,$false) -ceq $subject) 'client_upn'
    $chain=[Security.Cryptography.X509Certificates.X509Chain]::new()
    try{
        $chainBuilt=$chain.Build($client)
        if(-not $chainBuilt){@{fixture_chain_status=@($chain.ChainStatus|ForEach-Object {$_.Status.ToString()})}|ConvertTo-Json -Compress}
        Require-Fixture ($chainBuilt -and $chain.ChainElements[$chain.ChainElements.Count-1].Certificate.Thumbprint -ieq $client.Thumbprint) 'client_chain'
    }finally{$chain.Dispose()}
    Require-Fixture ((Get-Item -LiteralPath ($mappingPath+'\Enabled')).Value -ieq 'true') 'mapping_enabled'
    $mappingUser=[string](Get-Item -LiteralPath ($mappingPath+'\UserName')).Value
    Require-Fixture ($mappingUser -ieq $name -or $mappingUser -ieq ($env:COMPUTERNAME+'\'+$name)) 'mapping_user_name'
    if($mappingUser -notmatch '\\'){$mappingUser=$env:COMPUTERNAME+'\'+$mappingUser}
    $mappedSid=([Security.Principal.NTAccount]::new($mappingUser)).Translate([Security.Principal.SecurityIdentifier])
    Require-Fixture ($mappedSid.Value -ceq $createdUser.SID.Value) 'mapping_user_sid'
    # Match the exact IPv4 listener; localhost can select ::1 while HTTP.sys
    # has a port binding but WinRM has no matching IPv6 listener. The server
    # certificate explicitly includes the verified 127.0.0.1 IP SAN.
    $target=@{kind='windows-jea-v1';server='127.0.0.1';port=$port;configuration_name=$endpoint;ca_file=(Join-Path $root 'ca.pem');authentication=@{method='certificate';certificate_pem=(Join-Path $root 'client.pem');certificate_key_pem=(Join-Path $root 'client.key')};binding_digest=$binding}
    $target|ConvertTo-Json -Depth 6 -Compress|Set-Content -LiteralPath (Join-Path $root 'target.json') -Encoding utf8
    $digest=& $PythonPath (Join-Path $SourceRoot 'tests/native_windows_endpoint.py') digest --folder $root
    Require-Fixture ($LASTEXITCODE -eq 0 -and $digest -cmatch '^sha256:[0-9a-f]{64}$')
    $boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o');$safeState=$state.Replace("'","''")
    @"
@{SchemaVersion='1.0';TargetId='fixture-target';BindingDigest='$binding';TargetDigest='$digest';BootId='$boot';StatePath='$safeState';Tasks=@{'canary-write'=@{File='canary-write.ps1';SHA256='$taskHash';Parameters=@{value=@{Enum=@('before','after','fail')}};Result=@{state=@{Enum=@('before','after')}}}}}
"@ | Set-Content -LiteralPath (Join-Path $moduleRoot 'endpoint.psd1') -Encoding utf8
    $rolePath=Join-Path $moduleRoot 'DevopsBoundRole.psrc'
    New-PSRoleCapabilityFile -Path $rolePath -VisibleFunctions @('Get-DevopsEndpointBinding','Get-DevopsBoundTaskStatus','Invoke-DevopsBoundTask')
    $roles=@{};$roles[$env:COMPUTERNAME+'\'+$name]=@{RoleCapabilityFiles=@([string]$rolePath)}
    $sessionPath=Join-Path $moduleRoot 'endpoint.pssc'
    New-PSSessionConfigurationFile -Path $sessionPath -SessionType RestrictedRemoteServer -LanguageMode NoLanguage -RunAsVirtualAccount -RunAsVirtualAccountGroups @([string]$groupName) -ModulesToImport @([string](Join-Path $moduleRoot 'DevopsEndpoint.psm1')) -RoleDefinitions $roles
    Require-Fixture (Test-PSSessionConfigurationFile -Path $sessionPath)
    Register-PSSessionConfiguration -Name $endpoint -Path $sessionPath -NoServiceRestart -Force | Out-Null;$registered=$true
    Restart-Service WinRM -Force
    $observed=Get-WSManInstance -ResourceURI winrm/config/Listener -SelectorSet @{Address='IP:127.0.0.1';Transport='HTTPS'}
    Require-Fixture ([int]$observed.Port -eq $port -and $observed.Hostname -ceq 'localhost' -and $observed.CertificateThumbprint -ieq $server.Thumbprint -and $observed.Enabled -ieq 'true')
    Require-Fixture (@($observed.ListeningOn).Count -eq 1 -and @($observed.ListeningOn)[0] -ceq '127.0.0.1')
    Require-Fixture $server.HasPrivateKey
    Require-Fixture ((Get-Item WSMan:\localhost\Service\Auth\Certificate).Value -ieq 'true')
    $requestStart=Get-Date
    & $PythonPath (Join-Path $SourceRoot 'tests/native_windows_endpoint.py') diagnose-tls --folder $root
    & $PythonPath (Join-Path $SourceRoot 'tests/native_windows_endpoint.py') exercise --folder $root
    Require-Fixture ($LASTEXITCODE -eq 0)
}catch{
    foreach($log in @('System','Microsoft-Windows-WinRM/Operational')){
        try{
            $events=Get-WinEvent -FilterHashtable @{LogName=$log;StartTime=$requestStart} -MaxEvents 24 -ErrorAction Stop
            foreach($event in $events){if($log -ne 'System' -or $event.ProviderName -eq 'Schannel'){
                $message=[string]$event.Message
                if($message.Length -gt 1800){$message=$message.Substring(0,1800)}
                @{fixture_diagnostic_log=$log;at=$event.TimeCreated.ToUniversalTime().ToString('o');record=$event.RecordId;id=$event.Id;level=$event.LevelDisplayName;message=$message}|ConvertTo-Json -Compress
            }}
        }catch{ 'FIXTURE_EVENT_DIAGNOSTIC_UNAVAILABLE' }
    }
    try{
        foreach($event in @(Get-WinEvent -FilterHashtable @{LogName='Security';Id=4625;StartTime=$requestStart} -MaxEvents 16 -ErrorAction Stop)){
            $data=@{};foreach($entry in ([xml]$event.ToXml()).Event.EventData.Data){$data[$entry.Name]=[string]$entry.'#text'}
            if($data['TargetUserName'] -ieq $name){@{fixture_logon_failure=$true;at=$event.TimeCreated.ToUniversalTime().ToString('o');status=$data['Status'];substatus=$data['SubStatus'];logon_type=$data['LogonType']}|ConvertTo-Json -Compress}
        }
    }catch{'FIXTURE_LOGON_DIAGNOSTIC_UNAVAILABLE'}
    throw
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
