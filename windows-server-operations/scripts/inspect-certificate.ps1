[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidatePattern('^[A-Fa-f0-9]{40}$')][string]$Thumbprint, [ValidateSet('CurrentUser','LocalMachine')][string]$StoreLocation = 'LocalMachine', [ValidateSet('My','WebHosting','Remote Desktop')][string]$StoreName = 'My')
$ErrorActionPreference = 'Stop'
try {
    . (Join-Path $PSScriptRoot 'windows-evidence.ps1')
    if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Windows required' }
    $certificate = Get-Item -LiteralPath ('Cert:\{0}\{1}\{2}' -f $StoreLocation,$StoreName,$Thumbprint) -ErrorAction Stop
    Get-WindowsCertificateEvidence -Certificate $certificate | ConvertTo-Json -Depth 8
} catch { Write-Output '{"status":"unknown","reason":"certificate request failed; key use and trust unverified"}'; exit 2 }
