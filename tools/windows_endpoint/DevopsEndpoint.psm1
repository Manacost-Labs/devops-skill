# Trusted JEA implementation. Install/configure only under an independent owner.
# No target operation is included: owner-registered scripts are a separate review.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:ConfigPath = Join-Path $PSScriptRoot 'endpoint.psd1'

function Assert-Endpoint($Condition) {
    if (-not $Condition) { throw 'Protected endpoint refused invalid or unavailable state' }
}

function Get-EndpointConfig([switch]$ForExecution) {
    $item = Get-Item -LiteralPath $script:ConfigPath -Force
    Assert-Endpoint (-not $item.PSIsContainer -and -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -and $item.Length -le 65536)
    $config = Import-PowerShellDataFile -LiteralPath $script:ConfigPath
    Assert-Endpoint ($config.SchemaVersion -ceq '1.0' -and $config.TargetId -cmatch '^[a-z][a-z0-9-]{5,79}$')
    foreach ($field in @('BindingDigest','TargetDigest')) { Assert-Endpoint ($config[$field] -cmatch '^sha256:[0-9a-f]{64}$') }
    Assert-Endpoint ([IO.Path]::IsPathRooted($config.StatePath) -and -not $config.StatePath.StartsWith('\\'))
    $state = Get-Item -LiteralPath $config.StatePath -Force
    Assert-Endpoint ($state.PSIsContainer -and -not ($state.Attributes -band [IO.FileAttributes]::ReparsePoint))
    Assert-Endpoint ($config.Tasks -is [Collections.IDictionary] -and $config.Tasks.Count -ge 1 -and $config.Tasks.Count -le 128)
    # Machine restart can interrupt a remote command independently of the client.
    # Require owner reconciliation and re-enrollment after every target boot.
    if ($ForExecution) {
        $boot = (Get-CimInstance -ClassName Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
        Assert-Endpoint ($config.BootId -ceq $boot)
    }
    return $config
}

function Get-EndpointHash([string]$Text) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return 'sha256:' + ([BitConverter]::ToString($algorithm.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text)))).Replace('-','').ToLowerInvariant() }
    finally { $algorithm.Dispose() }
}

function Skip-EndpointSpace([string]$Text,[ref]$Index) {
    while ($Index.Value -lt $Text.Length -and @(' ',"`t","`r","`n") -ccontains [string]$Text[$Index.Value]) { $Index.Value++ }
}

function Test-EndpointJsonValue([string]$Text,[ref]$Index,[int]$Depth,$Parser) {
    Assert-Endpoint ($Depth -le 8)
    Skip-EndpointSpace $Text $Index
    Assert-Endpoint ($Index.Value -lt $Text.Length)
    if ($Text[$Index.Value] -ceq '{') {
        $Index.Value++; Skip-EndpointSpace $Text $Index
        $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        if ($Index.Value -lt $Text.Length -and $Text[$Index.Value] -ceq '}') { $Index.Value++; return }
        while ($true) {
            Skip-EndpointSpace $Text $Index
            # Match from the current offset without accepting a later token.
            $token = [regex]::new('\G"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"').Match($Text,$Index.Value)
            Assert-Endpoint ($token.Success -and $token.Index -eq $Index.Value)
            $key = $Parser.DeserializeObject($token.Value)
            Assert-Endpoint ($seen.Add([string]$key))
            $Index.Value += $token.Length; Skip-EndpointSpace $Text $Index
            Assert-Endpoint ($Index.Value -lt $Text.Length -and $Text[$Index.Value] -ceq ':')
            $Index.Value++; Test-EndpointJsonValue $Text $Index ($Depth+1) $Parser
            Skip-EndpointSpace $Text $Index
            Assert-Endpoint ($Index.Value -lt $Text.Length)
            if ($Text[$Index.Value] -ceq '}') { $Index.Value++; return }
            Assert-Endpoint ($Text[$Index.Value] -ceq ','); $Index.Value++
        }
    }
    # Worker contracts contain only finite primitives and nested receipt maps.
    # Arrays, floats, duplicate/case-alias keys and executable text are absent.
    $token = [regex]::new('\G(?:"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"|-?(?:0|[1-9][0-9]*)|true|false|null)').Match($Text,$Index.Value)
    Assert-Endpoint ($token.Success -and $token.Index -eq $Index.Value)
    $Index.Value += $token.Length
}

function Read-EndpointJson([string]$Text) {
    Assert-Endpoint ($Text.Length -le 32768)
    # This parser accepts data only. All fields and finite primitive values are
    # checked below; no script, provider, path or arbitrary object is dispatched.
    Add-Type -AssemblyName System.Web.Extensions
    $parser = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $parser.MaxJsonLength = 32768
    $parser.RecursionLimit = 8
    $index = 0
    Test-EndpointJsonValue $Text ([ref]$index) 0 $parser
    Skip-EndpointSpace $Text ([ref]$index)
    Assert-Endpoint ($index -eq $Text.Length)
    $value = $parser.DeserializeObject($Text)
    Assert-Endpoint ($value -is [Collections.IDictionary])
    return ,$value
}

function Assert-EndpointFields($Value, [string[]]$Fields) {
    Assert-Endpoint ($Value -is [Collections.IDictionary] -and $Value.Count -eq $Fields.Count)
    foreach ($key in $Value.Keys) { Assert-Endpoint ($Fields -ccontains [string]$key) }
}

function Assert-EndpointValues($Schema, $Values) {
    Assert-Endpoint ($Schema -is [Collections.IDictionary] -and $Schema.Count -le 32)
    Assert-EndpointFields $Values @($Schema.Keys)
    foreach ($key in $Schema.Keys) {
        $rule = $Schema[$key]; $value = $Values[$key]
        if ($rule.Contains('Type') -and $rule.Type -ceq 'digest') {
            Assert-Endpoint ($value -is [string] -and $value -cmatch '^sha256:[0-9a-f]{64}$')
        } elseif ($rule.Contains('Type') -and $rule.Type -ceq 'integer') {
            Assert-Endpoint (($value -is [int] -or $value -is [long]) -and $value -ge $rule.Minimum -and $value -le $rule.Maximum)
        } else {
            Assert-Endpoint ($rule.Contains('Enum') -and @($rule.Enum).Count -ge 1 -and @($rule.Enum).Count -le 128)
            $matched = $false
            foreach ($choice in $rule.Enum) {
                if ($null -ne $value -and $null -ne $choice -and $value.GetType() -eq $choice.GetType() -and $value -ceq $choice) { $matched = $true }
            }
            Assert-Endpoint $matched
        }
    }
}

function Write-EndpointRecord([string]$Path, $Value) {
    $bytes = [Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 8 -Compress))
    Assert-Endpoint ($bytes.Length -le 32768)
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None, 4096, [IO.FileOptions]::WriteThrough)
    try { $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
}

function Read-EndpointRecord([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    Assert-Endpoint (-not $item.PSIsContainer -and -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -and $item.Length -le 32768)
    return Read-EndpointJson ([IO.File]::ReadAllText($item.FullName))
}

function Assert-EndpointWindow($Context) {
    foreach ($field in @('not_before','expires')) { Assert-Endpoint ($Context[$field] -cmatch '^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,7})?(?:Z|[+-]\d\d:\d\d)$') }
    $start = [DateTimeOffset]::Parse($Context.not_before, [Globalization.CultureInfo]::InvariantCulture)
    $end = [DateTimeOffset]::Parse($Context.expires, [Globalization.CultureInfo]::InvariantCulture)
    $now = [DateTimeOffset]::UtcNow
    Assert-Endpoint ($start -le $now -and $now -lt $end -and ($end - $start).TotalMinutes -le 120)
}

function Get-DevopsEndpointBinding {
    [CmdletBinding()]param()
    $config = Get-EndpointConfig
    return @{binding_digest=$config.BindingDigest;target_id=$config.TargetId} | ConvertTo-Json -Compress
}

function Get-DevopsBoundTaskStatus {
    [CmdletBinding()]param([Parameter(Mandatory=$true)][ValidatePattern('^sha256:[0-9a-f]{64}$')][string]$CallDigest)
    $config = Get-EndpointConfig
    $stem = Join-Path $config.StatePath $CallDigest.Substring(7)
    $status = 'not_observed'
    if (Test-Path -LiteralPath ($stem + '.result.json')) { $status = (Read-EndpointRecord ($stem + '.result.json'))['status'] }
    elseif (Test-Path -LiteralPath ($stem + '.intent.json')) { $status = 'outcome_unknown' }
    Assert-Endpoint (@('not_observed','outcome_unknown','executed') -ccontains $status)
    return @{status=$status;call_digest=$CallDigest;binding_digest=$config.BindingDigest} | ConvertTo-Json -Compress
}

function Invoke-DevopsBoundTask {
    [CmdletBinding()]param(
        [Parameter(Mandatory=$true)][string]$BindingDigest,
        [Parameter(Mandatory=$true)][string]$ContextJson,
        [Parameter(Mandatory=$true)][string]$ParametersJson
    )
    # A caller's common -ErrorAction must never turn task failures into success.
    $ErrorActionPreference = 'Stop'
    $config = Get-EndpointConfig -ForExecution
    Assert-Endpoint ($BindingDigest -ceq $config.BindingDigest)
    $context = Read-EndpointJson $ContextJson
    Assert-EndpointFields $context @('operation_id','task_id','target_id','call_digest','grant_digest','registry_digest','epoch','not_before','expires','parameters_digest','target_digest')
    foreach ($key in $context.Keys) { Assert-Endpoint ($context[$key] -is [string]) }
    Assert-Endpoint ($context.operation_id -cmatch '^ops-[a-z0-9-]{6,76}$' -and $context.task_id -cmatch '^[a-z][a-z0-9-]{5,79}$')
    Assert-Endpoint ($context.target_id -ceq $config.TargetId -and $context.target_digest -ceq $config.TargetDigest)
    foreach ($key in @('call_digest','grant_digest','registry_digest','parameters_digest')) { Assert-Endpoint ($context[$key] -cmatch '^sha256:[0-9a-f]{64}$') }
    Assert-Endpoint ($context.epoch -cmatch '^[0-9a-f]{64}$')
    Assert-Endpoint ((Get-EndpointHash $ParametersJson) -ceq $context.parameters_digest)
    Assert-EndpointWindow $context
    Assert-Endpoint ($config.Tasks.Contains($context.task_id))
    $task = $config.Tasks[$context.task_id]
    $parameters = Read-EndpointJson $ParametersJson
    Assert-EndpointValues $task.Parameters $parameters
    $scriptPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $task.File))
    Assert-Endpoint ($task.File -cmatch '^[a-z][a-z0-9-]{5,79}\.ps1$' -and [IO.Path]::GetDirectoryName($scriptPath) -ceq $PSScriptRoot)
    $scriptItem = Get-Item -LiteralPath $scriptPath -Force
    Assert-Endpoint (-not $scriptItem.PSIsContainer -and -not ($scriptItem.Attributes -band [IO.FileAttributes]::ReparsePoint))
    Assert-Endpoint (('sha256:' + (Get-FileHash -LiteralPath $scriptPath -Algorithm SHA256).Hash.ToLowerInvariant()) -ceq $task.SHA256)
    # The independent owner protects this entire tree and its ancestors. The
    # connector has no write rights. Do not treat a hash as an ACL boundary.
    $lock = $null; $intentWritten = $false
    $stem = Join-Path $config.StatePath $context.call_digest.Substring(7)
    $latch = Join-Path $config.StatePath 'target-latch.json'
    try {
        $lock = [IO.FileStream]::new((Join-Path $config.StatePath 'target.lock'), [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        if (Test-Path -LiteralPath ($stem + '.result.json')) {
            $old = Read-EndpointRecord ($stem + '.result.json')
            Assert-Endpoint ($old['operation_id'] -ceq $context.operation_id -and $old['status'] -ceq 'executed')
            return $old | ConvertTo-Json -Depth 8 -Compress
        }
        Assert-Endpoint (-not (Test-Path -LiteralPath $latch) -and -not (Test-Path -LiteralPath ($stem + '.intent.json')))
        # An operation ID cannot be replayed with a new grant/call digest.
        $operationPath = Join-Path $config.StatePath ($context.operation_id + '.operation.json')
        Assert-Endpoint (-not (Test-Path -LiteralPath $operationPath))
        Assert-Endpoint (@(Get-ChildItem -LiteralPath $config.StatePath -File).Count -lt 8192)
        Assert-EndpointWindow $context
        $intent = @{operation_id=$context.operation_id;call_digest=$context.call_digest;task_id=$context.task_id;binding_digest=$BindingDigest;status='outcome_unknown';observed_at=[DateTime]::UtcNow.ToString('o')}
        Write-EndpointRecord $operationPath $intent
        Write-EndpointRecord $latch $intent
        Write-EndpointRecord ($stem + '.intent.json') $intent
        $intentWritten = $true
        # Admission is checked again after acquiring the lock and syncing intent.
        # Every registered script must be a single bounded slice, rechecking its
        # actual target before its write; there is no generic AD permission here.
        Assert-EndpointWindow $context
        $result = $null; $count = 0
        $global:LASTEXITCODE = 0
        & $scriptPath -Parameters $parameters -Context $context 2>&1 | ForEach-Object {
            Assert-Endpoint (-not ($_ -is [System.Management.Automation.ErrorRecord]))
            $count++; Assert-Endpoint ($count -eq 1); $result = $_
        }
        Assert-Endpoint ($count -eq 1 -and $global:LASTEXITCODE -eq 0)
        Assert-EndpointValues $task.Result $result
        $receipt = @{operation_id=$context.operation_id;call_digest=$context.call_digest;binding_digest=$BindingDigest;status='executed';result=$result}
        Write-EndpointRecord ($stem + '.result.json') $receipt
        # Only a known successful, durably recorded task releases quarantine.
        Remove-Item -LiteralPath $latch -ErrorAction Stop
        return $receipt | ConvertTo-Json -Depth 8 -Compress
    } catch {
        if ($intentWritten -or (Test-Path -LiteralPath $latch)) { throw 'Remote task outcome is unknown; preserve the original operation ID and reconcile through the owner' }
        throw 'Remote task refused before dispatch; no task was invoked'
    } finally { if ($lock) { $lock.Dispose() } }
}

Export-ModuleMember -Function Get-DevopsEndpointBinding,Get-DevopsBoundTaskStatus,Invoke-DevopsBoundTask
