# Synthetic local filesystem fixture; never registers a session or contacts AD.
[CmdletBinding()]param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$fixtureRoot=Join-Path ([IO.Path]::GetTempPath()) ('devops-endpoint-test-'+[guid]::NewGuid().ToString('N'))
$null=New-Item -ItemType Directory -Path $fixtureRoot
$moduleRoot=Join-Path $fixtureRoot 'module'; $null=New-Item -ItemType Directory -Path $moduleRoot
Copy-Item -LiteralPath (Join-Path $SourceRoot 'tools\windows_endpoint\DevopsEndpoint.psm1') -Destination (Join-Path $moduleRoot 'DevopsEndpoint.psm1')
$taskPath=Join-Path $moduleRoot 'canary-write.ps1'
@'
param($Parameters,$Context)
$ErrorActionPreference='Stop'
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'testvalue.txt'),$Parameters['value'])
if($Parameters['value'] -ceq 'fail'){throw 'Synthetic task failed after mutation'}
@{state=$Parameters['value']}
'@ | Set-Content -LiteralPath $taskPath -Encoding utf8
$taskHash='sha256:'+(Get-FileHash -LiteralPath $taskPath -Algorithm SHA256).Hash.ToLowerInvariant()
$binding='sha256:'+('b'*64); $target='sha256:'+('c'*64)
$bootId=(Get-CimInstance -ClassName Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
$passed=0

function Assert-Test($Condition,[string]$Name){if(-not $Condition){throw "Fixture assertion failed: $Name"}; $script:passed++}
function Hash-Test([string]$Text){$s=[Security.Cryptography.SHA256]::Create();try{'sha256:'+([BitConverter]::ToString($s.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text)))).Replace('-','').ToLowerInvariant()}finally{$s.Dispose()}}
function New-Fixture([string]$Name){
    $state=Join-Path $fixtureRoot $Name; $null=New-Item -ItemType Directory -Path $state
    [IO.File]::WriteAllBytes((Join-Path $state 'target.lock'),[byte[]]@())
    $safeState=$state.Replace("'","''")
    @"
@{SchemaVersion='1.0';TargetId='fixture-target';BindingDigest='$binding';TargetDigest='$target';BootId='$bootId';StatePath='$safeState';Tasks=@{'canary-write'=@{File='canary-write.ps1';SHA256='$taskHash';Parameters=@{value=@{Enum=@('before','after','fail')}};Result=@{state=@{Enum=@('before','after')}}}}}
"@ | Set-Content -LiteralPath (Join-Path $moduleRoot 'endpoint.psd1') -Encoding utf8
    [IO.File]::WriteAllText((Join-Path $moduleRoot 'testvalue.txt'),'before')
    return $state
}
function Make-Context([string]$ParametersJson='{"value":"after"}',[string]$Id='ops-fixture-write'){
    return [ordered]@{operation_id=$Id;task_id='canary-write';target_id='fixture-target';call_digest='sha256:'+('d'*64);grant_digest='sha256:'+('e'*64);registry_digest='sha256:'+('f'*64);epoch='a'*64;not_before=[DateTime]::UtcNow.AddMinutes(-1).ToString('o');expires=[DateTime]::UtcNow.AddMinutes(5).ToString('o');parameters_digest=(Hash-Test $ParametersJson);target_digest=$target}
}
function Invoke-Test($Context,[string]$ParametersJson='{"value":"after"}'){
    Invoke-DevopsBoundTask -BindingDigest $binding -ContextJson ($Context | ConvertTo-Json -Compress) -ParametersJson $ParametersJson
}
function Assert-Refusal($Context,[string]$ParametersJson='{"value":"after"}'){
    $denied=$false;try{$null=Invoke-Test $Context $ParametersJson}catch{$denied=$true}
    Assert-Test $denied 'must refuse'
}
try {
    Import-Module (Join-Path $moduleRoot 'DevopsEndpoint.psm1') -Force
    $state=New-Fixture 'success'
    $context=Make-Context
    $first=Invoke-Test $context | ConvertFrom-Json
    Assert-Test ($first.status -ceq 'executed' -and $first.result.state -ceq 'after') 'positive task'
    Assert-Test ([IO.File]::ReadAllText((Join-Path $moduleRoot 'testvalue.txt')) -ceq 'after') 'actual filesystem mutation'
    [IO.File]::WriteAllText((Join-Path $moduleRoot 'testvalue.txt'),'outside-change')
    $null=Invoke-Test $context
    Assert-Test ([IO.File]::ReadAllText((Join-Path $moduleRoot 'testvalue.txt')) -ceq 'outside-change') 'replay never invokes task'
    $context.call_digest='sha256:'+('1'*64)
    Assert-Refusal $context

    foreach($variant in @('expiry','target','parameters','unknown-task','extra-context')){
        $state=New-Fixture $variant; $context=Make-Context
        switch($variant){
            'expiry'{$context.expires=[DateTime]::UtcNow.AddMinutes(-2).ToString('o')}
            'target'{$context.target_digest='sha256:'+('2'*64)}
            'parameters'{$context.parameters_digest='sha256:'+('2'*64)}
            'unknown-task'{$context.task_id='unknown-task'}
            'extra-context'{$context.Add('owner_run',$true)}
        }
        Assert-Refusal $context
        Assert-Test ([IO.File]::ReadAllText((Join-Path $moduleRoot 'testvalue.txt')) -ceq 'before') 'refused before mutation'
    }
    $state=New-Fixture 'unregistered-value';$raw='{"value":"../unreviewed"}';$context=Make-Context $raw
    Assert-Refusal $context $raw
    Assert-Test ([IO.File]::ReadAllText((Join-Path $moduleRoot 'testvalue.txt')) -ceq 'before') 'finite parameters'
    foreach($raw in @('{"value":"before","value":"after"}','{"value":"before","Value":"after"}','{"value":["after"]}')){
        $state=New-Fixture ('json-'+[guid]::NewGuid().ToString('N'));$context=Make-Context $raw
        Assert-Refusal $context $raw
        Assert-Test ([IO.File]::ReadAllText((Join-Path $moduleRoot 'testvalue.txt')) -ceq 'before') 'strict JSON before mutation'
    }

    $state=New-Fixture 'lost-outcome';$raw='{"value":"fail"}';$context=Make-Context $raw
    Assert-Refusal $context $raw
    Assert-Test ([IO.File]::ReadAllText((Join-Path $moduleRoot 'testvalue.txt')) -ceq 'fail') 'failure really follows mutation'
    $status=Get-DevopsBoundTaskStatus -CallDigest $context.call_digest | ConvertFrom-Json
    Assert-Test ($status.status -ceq 'outcome_unknown') 'uncertain receipt'
    $retry=Make-Context '{"value":"after"}' 'ops-fixture-retry';$retry.call_digest='sha256:'+('3'*64)
    Assert-Refusal $retry
    Assert-Test ([IO.File]::ReadAllText((Join-Path $moduleRoot 'testvalue.txt')) -ceq 'fail') 'new operation ID cannot bypass quarantine'

    $state=New-Fixture 'journal-unavailable';$context=Make-Context
    $held=[IO.FileStream]::new((Join-Path $state 'target.lock'),[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    try{Assert-Refusal $context}finally{$held.Dispose()}
    Assert-Test ([IO.File]::ReadAllText((Join-Path $moduleRoot 'testvalue.txt')) -ceq 'before') 'lock precedes mutation'
    foreach($errorMode in @('nonterminating-error','native-exit')){
        if($errorMode -ceq 'nonterminating-error'){
            @'
param($Parameters,$Context)
Write-Error 'Synthetic task error' -ErrorAction Continue
@{state='after'}
'@ | Set-Content -LiteralPath $taskPath -Encoding utf8
        }else{
            @'
param($Parameters,$Context)
& "$env:SystemRoot\System32\cmd.exe" /d /c exit 7
@{state='after'}
'@ | Set-Content -LiteralPath $taskPath -Encoding utf8
        }
        $taskHash='sha256:'+(Get-FileHash -LiteralPath $taskPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $state=New-Fixture $errorMode;$context=Make-Context
        $denied=$false
        try{$null=Invoke-DevopsBoundTask -BindingDigest $binding -ContextJson ($context|ConvertTo-Json -Compress) -ParametersJson '{"value":"after"}' -ErrorAction Continue}catch{$denied=$true}
        Assert-Test $denied 'caller error preference cannot approve task errors'
        Assert-Test ((Get-DevopsBoundTaskStatus -CallDigest $context.call_digest|ConvertFrom-Json).status -ceq 'outcome_unknown') 'task error preserves quarantine'
    }
    "WINDOWS_ENDPOINT_FIXTURE_PASS:$passed"
} finally {
    $resolved=[IO.Path]::GetFullPath($fixtureRoot)
    $temp=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')+'\'
    if(-not $resolved.StartsWith($temp,[StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetFileName($resolved) -notmatch '^devops-endpoint-test-[a-f0-9]{32}$'){throw 'Unsafe fixture cleanup target'}
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
