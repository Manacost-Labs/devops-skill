[CmdletBinding()]
param()
# Read-only Windows Server audit. Run locally on the target or in an approved remoting session.
$ErrorActionPreference = 'Continue'
$warnings = [System.Collections.Generic.List[string]]::new()
function Section([string]$Name) { Write-Output "`n== $Name ==" }
function Line([string]$Name, [object]$Value) { Write-Output ("{0,-28} {1}" -f ($Name + ':'), $Value) }
function Warn([string]$Message) { $warnings.Add($Message); Write-Output "WARN: $Message" }

Section 'Identity'
$os = Get-CimInstance Win32_OperatingSystem
$computer = Get-CimInstance Win32_ComputerSystem
Line 'timestamp_utc' ([DateTime]::UtcNow.ToString('o'))
Line 'hostname' $env:COMPUTERNAME
Line 'os' ("{0} {1}" -f $os.Caption, $os.Version)
Line 'uptime' ((Get-Date) - $os.LastBootUpTime)
Line 'domain_or_workgroup' $computer.Domain
Line 'virtualization' $computer.Model

Section 'Resources'
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {
  $freePct = if ($_.Size) { [math]::Round(100 * $_.FreeSpace / $_.Size, 1) } else { 0 }
  Line ("disk_{0}" -f $_.DeviceID) ("free={0:N1}GB ({1}%) size={2:N1}GB" -f ($_.FreeSpace / 1GB), $freePct, ($_.Size / 1GB))
  if ($freePct -lt 10) { Warn "Critical disk pressure on $($_.DeviceID)" } elseif ($freePct -lt 20) { Warn "Disk warning on $($_.DeviceID)" }
}
$memory = Get-CimInstance Win32_OperatingSystem
Line 'memory' ("free={0:N1}GB total={1:N1}GB" -f ($memory.FreePhysicalMemory / 1MB), ($memory.TotalVisibleMemorySize / 1MB))

Section 'Services and events'
$failed = Get-CimInstance Win32_Service | Where-Object { $_.StartMode -eq 'Auto' -and $_.State -ne 'Running' }
if ($failed) { $failed | Select-Object Name, State, StartMode, StartName | Format-Table -AutoSize | Out-String | Write-Output; Warn 'Automatic Windows services are not running' } else { Line 'automatic_services' 'no stopped automatic services detected' }
$recentErrors = Get-WinEvent -FilterHashtable @{LogName='System'; Level=2; StartTime=(Get-Date).AddHours(-24)} -MaxEvents 10 -ErrorAction SilentlyContinue
Line 'system_errors_24h' ($recentErrors.Count)
$recentErrors | Select-Object TimeCreated, Id, ProviderName, Message | Format-Table -Wrap -AutoSize | Out-String | Write-Output

Section 'Access and network'
$winrm = Get-Service WinRM -ErrorAction SilentlyContinue
$winrmValue = if ($winrm) { $winrm.Status } else { 'not installed or unavailable' }
Line 'winrm_service' $winrmValue
$rdp = Get-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -ErrorAction SilentlyContinue
$rdpValue = if ($rdp -and $rdp.fDenyTSConnections -eq 0) { 'yes' } else { 'no or unknown' }
Line 'rdp_enabled' $rdpValue
Get-NetFirewallProfile -ErrorAction SilentlyContinue | ForEach-Object { Line ("firewall_{0}" -f $_.Name) $_.Enabled }
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, OwningProcess | Sort-Object LocalPort -Unique | Format-Table -AutoSize | Out-String | Write-Output

Section 'Updates and recovery signals'
$rebootKeys = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending','HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired')
$pending = $rebootKeys | Where-Object { Test-Path $_ }
$rebootValue = if ($pending) { 'yes' } else { 'not detected' }
Line 'reboot_pending' $rebootValue
if ($pending) { Warn 'Reboot pending; this is not authorization to reboot' }
Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -match 'backup|snapshot|veeam|windows server backup|monitor|exporter|otel' } | Select-Object TaskName, State, TaskPath | Format-Table -AutoSize | Out-String | Write-Output

Section 'Summary'
if ($warnings.Count) { Line 'overall' 'review required; no changes were made'; $warnings | ForEach-Object { Write-Output "- $_" } } else { Line 'overall' 'no immediate warning detected; this does not prove host health' }
Line 'next' 'Create a Windows change card before remediation; hand off cross-layer findings to the owning module.'