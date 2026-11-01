# Static PS5 encoding/session-file fixture; does not register or run an endpoint.
[CmdletBinding()]param([Parameter(Mandatory=$true)][string]$Bundle,[Parameter(Mandatory=$true)][string]$ExpectedEnum)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
$data=Import-PowerShellDataFile -LiteralPath (Join-Path $Bundle 'endpoint.psd1')
$matched=$false
foreach($value in $data.Tasks['canary-write'].Parameters['value'].Enum){if([string]::Equals($value,$ExpectedEnum,[StringComparison]::Ordinal)){$matched=$true}}
if(-not $matched){throw 'Generated PS5 data changed the reviewed Unicode value'}
$rolePath=[string](Join-Path $Bundle 'DevopsBoundRole.psrc')
$roles=@{'DIRECTORY\fixtureconnector'=@{RoleCapabilityFiles=@([string]$rolePath)}}
$sessionPath=Join-Path $Bundle 'fixture-generated.pssc'
New-PSSessionConfigurationFile -Path $sessionPath -SessionType RestrictedRemoteServer -LanguageMode NoLanguage -GroupManagedServiceAccount 'DIRECTORY\fixtureworker$' -ModulesToImport @([string](Join-Path $Bundle 'DevopsEndpoint.psm1')) -RoleDefinitions $roles
if(-not(Test-PSSessionConfigurationFile -Path $sessionPath)){throw 'Generated static JEA configuration invalid'}
'WINDOWS_ENDPOINT_STATIC_SETUP_PASS'
