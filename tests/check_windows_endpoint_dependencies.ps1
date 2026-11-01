# Fresh-process metadata only: no CIM query, endpoint registration or task.
param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference='Stop'
$PSModuleAutoLoadingPreference='None'
$endpointModule=Import-Module -Name ([IO.Path]::Combine($SourceRoot,'tools\windows_endpoint\DevopsEndpoint.psm1')) -PassThru
$dependencies=$endpointModule.Invoke({
    foreach($dependency in @('Import-PowerShellDataFile','Get-FileHash','Get-CimInstance')){
        if(-not (Get-Command -Name $dependency -ErrorAction SilentlyContinue)){throw ('Missing private dependency: '+$dependency)}
    }
})
$exports=@($endpointModule.ExportedFunctions.Keys|Sort-Object)
if(($exports -join ',') -cne 'Get-DevopsBoundTaskStatus,Get-DevopsEndpointBinding,Invoke-DevopsBoundTask' -or $endpointModule.ExportedCmdlets.Count -ne 0 -or $endpointModule.ExportedAliases.Count -ne 0){throw 'Endpoint export boundary changed'}
Write-Output 'WINDOWS_ENDPOINT_PRIVATE_DEPENDENCIES_PASS: no autoload, no CIM query, exactly three exports'
