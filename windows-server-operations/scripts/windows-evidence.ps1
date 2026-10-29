# Shared read-only collectors. No target instructions, remoting setup or mutation.
function ConvertTo-WindowsEvidenceText {
    param([object]$Value, [int]$Maximum = 128)
    if ($null -eq $Value) { return $null }
    $text = [string]$Value
    if ($text.Length -gt $Maximum) { return $text.Substring(0, $Maximum) + '[truncated]' }
    return $text
}

function Invoke-WindowsEvidenceProbe {
    param([string]$Name, [scriptblock]$Collect, [scriptblock]$Project, [int]$Limit = 20)
    $ErrorActionPreference = 'Stop'
    try {
        $rows = @(& $Collect | Select-Object -First ($Limit + 1))
        $truncated = $rows.Count -gt $Limit
        $entries = @($rows | Select-Object -First $Limit | ForEach-Object { & $Project $_ })
        return [pscustomobject]@{ name = $Name; status = 'observed'; truncated = $truncated; entries = $entries; completeness = 'bounded scope only; not a health verdict' }
    } catch {
        if ($Name -eq 'system_events' -and $_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*') {
            return [pscustomobject]@{ name = $Name; status = 'observed'; truncated = $false; entries = @(); completeness = 'no matching events in requested scope only' }
        }
        return [pscustomobject]@{ name = $Name; status = 'unknown'; truncated = $false; entries = @(); completeness = 'missing command, permission or collection failure' }
    }
}

function Get-WindowsServerEvidence {
    param([int]$Limit = 20)
    $ErrorActionPreference = 'Stop'
    $os = Get-CimInstance -ClassName Win32_OperatingSystem -OperationTimeoutSec 5 -ErrorAction Stop
    if ($os.ProductType -notin 2,3 -or [string]$os.Version -notlike '10.0.*' -or [int]$os.BuildNumber -notin 17763,20348,26100) {
        return [pscustomobject]@{ status = 'unsupported_target'; verification = 'not_assessed'; reason = 'confirmed supported Windows Server required' }
    }
    $sections = @(
        Invoke-WindowsEvidenceProbe 'volumes' { Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' -OperationTimeoutSec 5 -ErrorAction Stop } {
            param($r) [pscustomobject]@{ drive = $r.DeviceID; filesystem = $r.FileSystem; size_bytes = $r.Size; free_bytes = $r.FreeSpace }
        } $Limit
        Invoke-WindowsEvidenceProbe 'automatic_service_candidates' { Get-CimInstance Win32_Service -Filter "StartMode='Auto' AND State<>'Running'" -OperationTimeoutSec 5 -ErrorAction Stop } {
            param($r) [pscustomobject]@{ name = ConvertTo-WindowsEvidenceText $r.Name; state = $r.State; start_mode = $r.StartMode }
        } $Limit
        Invoke-WindowsEvidenceProbe 'system_events' { Get-WinEvent -FilterHashtable @{LogName='System';Level=2;StartTime=(Get-Date).AddHours(-24)} -MaxEvents ($Limit+1) -ErrorAction Stop } {
            param($r) [pscustomobject]@{ utc = $r.TimeCreated.ToUniversalTime().ToString('o'); id = $r.Id; record_id = $r.RecordId; provider = ConvertTo-WindowsEvidenceText $r.ProviderName }
        } $Limit
        Invoke-WindowsEvidenceProbe 'firewall_profiles' { Get-NetFirewallProfile -ErrorAction Stop } {
            param($r) [pscustomobject]@{ name = $r.Name; enabled = [string]$r.Enabled }
        } $Limit
        Invoke-WindowsEvidenceProbe 'listeners' { Get-NetTCPConnection -State Listen -ErrorAction Stop } {
            param($r) [pscustomobject]@{ address = ConvertTo-WindowsEvidenceText $r.LocalAddress; port = $r.LocalPort }
        } $Limit
        Invoke-WindowsEvidenceProbe 'smb_shares' { Get-SmbShare -ErrorAction Stop } {
            param($r) [pscustomobject]@{ name = ConvertTo-WindowsEvidenceText $r.Name; special = $r.Special; encrypted = $r.EncryptData; scope = ConvertTo-WindowsEvidenceText $r.ScopeName }
        } $Limit
        Invoke-WindowsEvidenceProbe 'scheduled_tasks' { Get-ScheduledTask -ErrorAction Stop } {
            param($r) [pscustomobject]@{ name = ConvertTo-WindowsEvidenceText $r.TaskName; state = [string]$r.State }
        } $Limit
        Invoke-WindowsEvidenceProbe 'disks' { Get-Disk -ErrorAction Stop } {
            param($r) [pscustomobject]@{ number = $r.Number; size_bytes = $r.Size; style = [string]$r.PartitionStyle; bus = [string]$r.BusType; health = [string]$r.HealthStatus; boot = $r.IsBoot; system = $r.IsSystem }
        } $Limit
        Invoke-WindowsEvidenceProbe 'reboot_markers' {
            foreach ($path in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending','HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired')) {
                [pscustomobject]@{ present = Test-Path -LiteralPath $path -ErrorAction Stop }
            }
        } { param($r) [pscustomobject]@{ present = $r.present } } $Limit
    )
    return [pscustomobject]@{
        status = 'discovery_only'; verification = 'not_assessed'; utc = [DateTime]::UtcNow.ToString('o')
        identity = [pscustomobject]@{ caption = ConvertTo-WindowsEvidenceText $os.Caption; version = $os.Version; build = $os.BuildNumber; product_type = $os.ProductType }
        sections = $sections
        notes = @('Automatic services may be trigger-start or unused; candidates are not failures.', 'Reboot-marker absence is incomplete evidence.', 'Task/share presence is not backup, access or health proof.', 'Disk numbers are not immutable change targets.', 'Certificate and private-key checks require an exact consumer/store/identity.')
    }
}

function Get-WindowsLocalEvidenceItem {
    param([string]$LiteralPath)
    if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Windows required' }
    $full = [IO.Path]::GetFullPath($LiteralPath)
    if ($full -notmatch '^[A-Za-z]:\\' -or $full.Substring(2).Contains(':')) { throw 'local filesystem path required' }
    $drive = [IO.DriveInfo]::new($full.Substring(0,3))
    if ($drive.DriveType -notin [IO.DriveType]::Fixed,[IO.DriveType]::Removable,[IO.DriveType]::CDRom,[IO.DriveType]::Ram) { throw 'confirmed local drive required' }
    $cursor = $full.Substring(0,3)
    foreach ($part in $full.Substring(3).Split('\', [StringSplitOptions]::RemoveEmptyEntries)) {
        $cursor = Join-Path $cursor $part
        $item = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'reparse point requires owning path review' }
    }
    $result = Get-Item -LiteralPath $full -Force -ErrorAction Stop
    if ($result.PSProvider.Name -ne 'FileSystem') { throw 'filesystem required' }
    return $result
}

function Get-WindowsFileSecurityEvidence {
    param([string]$LiteralPath, [int]$Limit = 128, [switch]$IncludeSddl)
    $item = Get-WindowsLocalEvidenceItem $LiteralPath
    $acl = Get-Acl -LiteralPath $item.FullName -ErrorAction Stop
    $sections = [Security.AccessControl.AccessControlSections]::Access -bor [Security.AccessControl.AccessControlSections]::Owner -bor [Security.AccessControl.AccessControlSections]::Group
    $sddl = $acl.GetSecurityDescriptorSddlForm($sections)
    $raw = [Security.AccessControl.RawSecurityDescriptor]::new($sddl)
    # GetAccessRules can flatten callback/conditional ACEs into ordinary grants.
    # Inspect raw types first and omit that projection if any semantics need context.
    $aceCount = 0; $complexTypes = @(); $rules = @()
    if ($null -ne $raw.DiscretionaryAcl) {
        $aceCount = $raw.DiscretionaryAcl.Count
        $complexTypes = @($raw.DiscretionaryAcl | Where-Object { $_.AceType -notin [Security.AccessControl.AceType]::AccessAllowed,[Security.AccessControl.AceType]::AccessDenied } | ForEach-Object { [string]$_.AceType } | Select-Object -Unique)
    }
    $projection = 'ordinary_allow_deny'
    if ($complexTypes.Count -gt 0) { $projection = 'omitted_requires_complex_ace_review' }
    else { $rules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) }
    $kind = 'populated'
    if ($null -eq $raw.DiscretionaryAcl) { $kind = 'null_unrestricted_by_dacl' }
    elseif ($raw.DiscretionaryAcl.Count -eq 0) { $kind = 'empty_no_dacl_grants' }
    $hash = [Security.Cryptography.SHA256]::Create()
    try { $digest = ([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($sddl)))).Replace('-','').ToLowerInvariant() } finally { $hash.Dispose() }
    $result = [ordered]@{
        status = 'descriptor_observed'; effective_access = 'not_evaluated'; sacl = 'not_collected'
        owner_sid = $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
        group_sid = $acl.GetGroup([Security.Principal.SecurityIdentifier]).Value
        dacl_kind = $kind; inheritance_protected = $acl.AreAccessRulesProtected; canonical = $acl.AreAccessRulesCanonical
        descriptor_sha256 = $digest; ace_count = $aceCount; rule_projection = $projection
        complex_ace_types = @($complexTypes | Select-Object -First $Limit); truncated = $aceCount -gt $Limit
        rules = @($rules | Select-Object -First $Limit | ForEach-Object { [pscustomobject]@{ sid = $_.IdentityReference.Value; type = [string]$_.AccessControlType; rights = [string]$_.FileSystemRights; inherited = $_.IsInherited; inheritance = [string]$_.InheritanceFlags; propagation = [string]$_.PropagationFlags } })
    }
    if ($IncludeSddl) { $result['owner_group_dacl_sddl'] = $sddl }
    return [pscustomobject]$result
}

function Get-WindowsTaskXmlEvidence {
    param([byte[]]$Bytes)
    if ($Bytes.Length -gt 262144) { throw 'task XML size limit' }
    $settings = [Xml.XmlReaderSettings]::new()
    $settings.DtdProcessing = [Xml.DtdProcessing]::Prohibit
    $settings.XmlResolver = $null
    $settings.MaxCharactersInDocument = 262144
    $stream = [IO.MemoryStream]::new($Bytes, $false)
    $reader = $null
    try {
        $reader = [Xml.XmlReader]::Create($stream, $settings)
        $document = [Xml.XmlDocument]::new(); $document.XmlResolver = $null; $document.Load($reader)
    } finally { if ($reader) { $reader.Dispose() }; $stream.Dispose() }
    $ns = [Xml.XmlNamespaceManager]::new($document.NameTable)
    $ns.AddNamespace('t','http://schemas.microsoft.com/windows/2004/02/mit/task')
    if ($document.DocumentElement.LocalName -cne 'Task' -or $document.DocumentElement.NamespaceURI -cne $ns.LookupNamespace('t')) { throw 'unsupported task XML' }
    $principals = @($document.SelectNodes('/t:Task/t:Principals/t:Principal', $ns))
    $actions = @($document.SelectNodes('/t:Task/t:Actions/*', $ns))
    $triggers = @($document.SelectNodes('/t:Task/t:Triggers/*', $ns))
    $runLevelNodes = @($document.SelectNodes('/t:Task/t:Principals/t:Principal/t:RunLevel',$ns))
    $logonNodes = @($document.SelectNodes('/t:Task/t:Principals/t:Principal/t:LogonType',$ns))
    $runLevels = @($runLevelNodes | Select-Object -First 32 | ForEach-Object { if ($_.InnerText -cin @('LeastPrivilege','HighestAvailable')) { $_.InnerText } else { 'unknown_or_invalid' } })
    $logons = @($logonNodes | Select-Object -First 32 | ForEach-Object { if ($_.InnerText -cin @('Password','S4U','InteractiveToken','Group','ServiceAccount','InteractiveTokenOrPassword','None')) { $_.InnerText } else { 'unknown_or_invalid' } })
    return [pscustomobject]@{
        status = 'structure_observed'; schema_validated = $false; execution_authorized = $false
        principal_count = $principals.Count; run_levels = $runLevels; logon_types = $logons
        action_count = $actions.Count; action_types = @($actions | Select-Object -First 32 | ForEach-Object { if ($_.NamespaceURI -ceq $ns.LookupNamespace('t') -and $_.LocalName -cin @('Exec','ComHandler','SendEmail','ShowMessage')) { $_.LocalName } else { 'unknown_or_invalid' } })
        trigger_count = $triggers.Count; trigger_types = @($triggers | Select-Object -First 32 | ForEach-Object { if ($_.NamespaceURI -ceq $ns.LookupNamespace('t') -and $_.LocalName -cin @('CalendarTrigger','TimeTrigger','BootTrigger','LogonTrigger','EventTrigger','IdleTrigger','RegistrationTrigger','SessionStateChangeTrigger')) { $_.LocalName } else { 'unknown_or_invalid' } })
        truncated = $principals.Count -gt 32 -or $actions.Count -gt 32 -or $triggers.Count -gt 32 -or $runLevelNodes.Count -gt 32 -or $logonNodes.Count -gt 32
        action_and_identity_text = 'omitted; inspect under approved sensitive-evidence handling'
    }
}

function Get-WindowsCertificateEvidence {
    param([Security.Cryptography.X509Certificates.X509Certificate2]$Certificate)
    $now = [DateTime]::UtcNow
    $state = 'within_time_window'
    if ($Certificate.NotAfter.ToUniversalTime() -lt $now) { $state = 'expired' }
    elseif ($Certificate.NotBefore.ToUniversalTime() -gt $now) { $state = 'not_yet_valid' }
    $eku = @()
    foreach ($extension in $Certificate.Extensions) {
        if ($extension -is [Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]) { $eku += @($extension.EnhancedKeyUsages | ForEach-Object { $_.Value }) }
    }
    return [pscustomobject]@{
        status = 'certificate_observed'; thumbprint = $Certificate.Thumbprint
        not_before_utc = $Certificate.NotBefore.ToUniversalTime().ToString('o'); not_after_utc = $Certificate.NotAfter.ToUniversalTime().ToString('o')
        time_state = $state; has_private_key = $Certificate.HasPrivateKey
        eku_oids = @($eku | Select-Object -First 32); truncated = $eku.Count -gt 32
        signature_oid = $Certificate.SignatureAlgorithm.Value
        service_key_access = 'not_verified'; trust_name_revocation = 'not_verified'; names = 'omitted'
    }
}
