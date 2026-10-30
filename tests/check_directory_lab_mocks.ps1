# Fail if a refused execution request reaches any native AD/GPMC call.
param([string]$PlanPath, [string]$TracePath)
$global:directoryCallTrace = $TracePath
function Stop-DirectoryCall {
    Add-Content -LiteralPath $global:directoryCallTrace -Value 'unexpected_native_call'
    throw 'A refused execution request reached native tooling'
}
function Import-Module { Stop-DirectoryCall }
function Get-ADDomain { Stop-DirectoryCall }
function Get-ADObject { Stop-DirectoryCall }
function Get-ADUser { Stop-DirectoryCall }
function Get-GPO { Stop-DirectoryCall }
function Remove-ADObject { Stop-DirectoryCall }
function Restore-ADObject { Stop-DirectoryCall }
function Set-GPRegistryValue { Stop-DirectoryCall }
function Restore-GPO { Stop-DirectoryCall }
& (Join-Path $PSScriptRoot 'check_identity_directory_lab.ps1') -PlanPath $PlanPath -Execute
exit $LASTEXITCODE
