# Host certificates and private keys

Identify the consumer (WinRM/RDP, HTTP.sys/IIS/application, client authentication or signing), actual service identity, store location/name, exact certificate thumbprint, endpoint hostname and ownership. A certificate in CurrentUser is not automatically available to a machine service. AD CS templates/issuance/CA recovery and public edge policy keep their owners.

Inspect validity in UTC with the host clock, intended SAN/name match, required EKU/key usage, algorithm/provider, chain/trust, revocation path and private-key availability. A thumbprint selects an object; it does not establish trust. Expiry alone does not diagnose every handshake failure. Offline/blocked revocation evidence is unknown; never turn validation off to obtain a green result.

`scripts/inspect-certificate.ps1` reads one exact certificate and reports bounded public metadata, EKU identifiers and HasPrivateKey. It does not export keys, contact revocation/issuance endpoints, validate a complete chain/name, or prove key access by a different service account. Subject/SAN disclosure needs approved handling; the helper omits them by default.

## Renewal/binding procedure

1. Record current binding/store/key/provider/ACL and the clients/services affected. Confirm whether the binding is centrally managed or owned by edge/application configuration.
2. Obtain the correctly issued certificate through the PKI owner; verify SAN/EKU/chain, matching key and exportability/recovery policy. Do not replace a trusted service certificate with a self-signed one incidentally.
3. Stage new certificate and minimal private-key access for the actual service SID/account. CAPI, CNG and hardware/KSP keys differ; do not guess a universal key-file path or grant broad MachineKeys access.
4. Preserve old binding and usable key until acceptance. PFX export can require a protected password/recipient and may be impossible for nonexportable/HSM keys; plan reissuance or provider recovery instead of pretending a .cer contains the private key.
5. Gate the exact binding/key ACL change. Change only the named consumer, validate its service-specific configuration, and restart/reload only when required with downtime/data owners.
6. Verify handshake as the intended client, hostname/SNI/chain/revocation behavior and actual service key use. Check denied identities as appropriate. Monitor before retiring old material; key deletion/old-certificate cleanup is a separately scoped action.

Treat PFX and recovery credentials as secrets: approved storage, least privilege, encryption and no argv/chat/log values. An export command succeeding is not proof that import and key use work. Global Schannel/cipher or trusted-root changes affect many consumers and need their own compatibility/rollback plan.

Sources: [PKI export](https://learn.microsoft.com/en-us/powershell/module/pki/export-pfxcertificate?view=windowsserver2025-ps), [TLS management](https://learn.microsoft.com/en-us/windows-server/security/tls/manage-tls), [certificate provider](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/about/about_certificate_provider?view=powershell-5.1).
