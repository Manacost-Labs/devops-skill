[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$LiteralPath)
$ErrorActionPreference = 'Stop'
try {
    . (Join-Path $PSScriptRoot 'windows-evidence.ps1')
    $item = Get-WindowsLocalEvidenceItem $LiteralPath
    if ($item.PSIsContainer) { throw 'file required' }
    $stream = [IO.FileStream]::new($item.FullName, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $buffer = [byte[]]::new(262145); $read = 0
        while ($read -lt $buffer.Length) { $count = $stream.Read($buffer, $read, $buffer.Length-$read); if ($count -eq 0) { break }; $read += $count }
        if ($read -gt 262144) { throw 'task XML size limit' }
        $bytes = [byte[]]::new($read); [Array]::Copy($buffer, $bytes, $read)
    } finally { $stream.Dispose() }
    Get-WindowsTaskXmlEvidence -Bytes $bytes | ConvertTo-Json -Depth 8
} catch { Write-Output '{"status":"unknown","reason":"task XML request failed; no registration or execution"}'; exit 2 }
