[CmdletBinding()]
param([ValidateRange(1,100)][int]$MaxItems = 20)
$ErrorActionPreference = 'Stop'
try {
    . (Join-Path $PSScriptRoot 'windows-evidence.ps1')
    $report = Get-WindowsServerEvidence -Limit $MaxItems
    $report | ConvertTo-Json -Depth 8
    if ($report.status -eq 'unsupported_target') { exit 2 }
} catch { Write-Output '{"status":"unknown","verification":"not_assessed","reason":"host discovery failed"}'; exit 2 }
