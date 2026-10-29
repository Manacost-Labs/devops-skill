[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$LiteralPath, [ValidateRange(1,500)][int]$MaxRules = 128, [switch]$IncludeSddl)
$ErrorActionPreference = 'Stop'
try {
    . (Join-Path $PSScriptRoot 'windows-evidence.ps1')
    Get-WindowsFileSecurityEvidence -LiteralPath $LiteralPath -Limit $MaxRules -IncludeSddl:$IncludeSddl | ConvertTo-Json -Depth 8
} catch { Write-Output '{"status":"unknown","reason":"descriptor request failed; no effective-access verdict"}'; exit 2 }
