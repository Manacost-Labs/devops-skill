# Protected Windows task integration in 0.16

This optional transport/endpoint foundation is not an installed AD executor.
Installing skills creates no identity, endpoint, certificate, grant, target task
or protected Codex session.

## Independent owner and requester

Use a fresh standard-user Codex context without host-admin, Hyper-V, Docker,
owner WSL, broker, VM disk/configuration/export or credential-store control.
A filtered UAC administrator token is insufficient. A same-host broker VM does
not isolate an agent that controls the hypervisor or target VMs. Stop privileged
agent sessions before activation; do not copy the owner's entire Codex/SSH home.
The active privileged chat cannot become an independent owner by changing a flag.

Use a separate Windows logon/session or equivalently isolated headless executor.
RunAs on the owner's interactive desktop is insufficient: shared desktop/UI and
clipboard routes must not let the agent interact with owner tools. The readiness
script does not establish this session boundary.

The owner protects runtime/interpreter and all ancestors, provisions scoped
credentials and registers immutable tasks. Keep the Ed25519 issuer outside both
agent and broker. Independently deliver/verify the installer in an immutable
owner-controlled location: its manifest digest binds data, not the executing
installer. Elevating a mutable agent-produced installer defeats the boundary.

`tools/windows_agent_readiness.ps1` checks actual SID, privileged groups
(including deny-only Administrators), Docker membership and access to named
**nonsecret owner-created canaries** without modifying them. Missing/unknown
checks are incomplete, not denied. It always reports deployment_verified=false;
it cannot prove all APIs, network paths or Codex tool surfaces by itself.

Preserve managed Codex policy. The existing closed review profile has networking
off, so it is not a broker-network profile. Separately verify minimal networking
to the exact broker on the deployed client/OS. Do not enable Full Access or broad
network/connector access to make it work. Hooks remain defense in depth; target
permissions and credential separation are mandatory.

## Broker and worker protocol

The Linux broker retains signature/risk/epoch/deadline checks, separate worker
UIDs and quarantine. Register `worker_input: context-v2` to opt into the new
payload. This changes the signed registry digest; old grants cannot silently
gain it. Otherwise exact legacy `{parameters,target}` bytes remain unchanged.
Opt-in adds schema_version 2.0 and broker-derived context: operation/task/target
IDs, call/grant/registry digests, epoch, effective not-before/expiry, parameter
and target digests. Caller parameters cannot set those bindings.

`tools/windows_bridge.py` is a protected worker task, never an agent helper.
Register its exact source/dependencies and target resource. It invokes only
Get-DevopsEndpointBinding, Invoke-DevopsBoundTask and Get-DevopsBoundTaskStatus on
one named endpoint. No script strings, WinRS shell, caller paths, fallback
endpoint or automatic execution retries. TLS verifies host/CA; redirects,
environment proxies and auth downgrade to NTLM/CredSSP are refused.

Authoritative resource shape:

```json
{
  "kind": "windows-jea-v1",
  "server": "dc01.directory.test",
  "port": 5986,
  "configuration_name": "DevopsBound-directorylab",
  "ca_file": "/protected/windows-ca.pem",
  "authentication": {"method": "kerberos", "cache_file": "/private/worker/connector.ccache"},
  "binding_digest": "sha256:REPLACE_WITH_PREPARED_BINDING"
}
```

Kerberos needs a Linux worker, explicit FQDN, private finite FILE ticket cache,
reviewed native GSSAPI/Kerberos runtime and correct DNS/time/SPN. The optional
hash-locked PSRP requirements do not install that OS/native Kerberos environment.
The bridge does not read a password/keytab, run kinit or delegate credentials.
Windows SSPI cannot substitute the interactive identity for the registered cache.

For non-DC Windows hosts, authentication can instead contain only method
`certificate`, certificate_pem and certificate_key_pem (absolute worker-only
paths). Map that credential to a nonadmin local connector restricted to the
named endpoint. WinRM local-account certificate mapping is not a domain-account
mapping on a DC: direct-DC integration uses Kerberos. Restrict listener/firewall
sources and prove default PS/WinRS denied. Never pass an administrator password
or disable certificate validation as a workaround.

## Windows endpoint and bootstrap

The JEA module loads adjacent owner-protected endpoint.psd1. This fixes target,
resource/binding digests, exact task filenames/hashes and finite parameter/result
schemas. Requests cannot select script, DN, GPO, path, credential or command.
Each registered task is one bounded slice that rechecks its actual target and
fresh state immediately before writing. No AD task ships with this foundation.

Windows does not independently verify Ed25519 signatures in the context. It
trusts the separately protected broker worker's connector identity. Therefore
the agent must have neither that credential nor another target write path.
Binding/owner-run fields are never a replacement for this separation.

Prefer a dedicated minimally delegated gMSA for routine AD work. Default DC JEA
virtual accounts are Domain Admins; explicit VA groups still use the DC computer
identity for network access. Check actual ADWS/GPMC/SYSVOL identity and effective
rights; do not add DC01$ rights to fix a failure. Forest features, DC promotion,
reboots and client policy processing require separate privilege/recovery tasks.

Prepare a private schema_version 1.0 plan containing endpoint_name, connector,
run_as_gmsa, module_root (new direct child of Program Files), state_root (new
direct child of ProgramData), target_id, target_resource (above without
binding_digest), and tasks. Each task ID maps to source_file (absolute reviewed
PS1), parameters and result_schema using broker enum/integer/digest shapes:

Task source encoding must be valid for Windows PowerShell 5.1. Generated static
data uses a UTF-8 BOM so non-ASCII enum values and paths retain their exact meaning.

```powershell
python tools/prepare_windows_endpoint.py --plan C:\PrivateReview\endpoint-plan.json --output C:\PrivateReview\new-endpoint-bundle
```

Output pins exact task/module bytes and derives endpoint/resource digests. It
creates no keys, accounts, endpoint or authority. The independent owner verifies
source/installer and displayed manifest digest, then validates without applying:

```powershell
.\Install-ReviewedEndpoint.ps1 -Bundle C:\PrivateReview\new-endpoint-bundle -ExpectedManifestSHA256 <reviewed-lowercase-sha256>
```

`-Apply` requests administrative installation, never execution admission. It
requires existing scoped gMSA/connector, protected HTTPS listener, unused paths
and exact digest. Bounded source bytes are read once, verified and written from
that snapshot into protected destinations. Code is read-only to the gMSA; only
state is writable. The endpoint uses explicit RestrictedRemoteServer/NoLanguage
roles. It registers without automatically restarting WinRM. No account creation,
Domain Admin grant, broad remoting/firewall setup or recursive rollback occurs.
Retain partial provisioning for owner reconciliation.

The owner separately handles service maintenance, verifies the connector's
effective JEA capability (roles combine), provisions Linux registry/credential
and external issuer, and completes acceptance. installed_not_verified is not
ready execution. A source checkout is never an execution grant.

## Remote outcomes

Windows takes an exclusive state lock, writes operation-ID binding/intent with
Flush/WriteThrough before dispatch and retains a target latch until valid success
is recorded. Same call replays its receipt without rerunning. Same operation ID
with different call/grant is refused. Task errors, caller ErrorAction and native
nonzero exits cannot become success. Lost replies, invalid results and interruption
remain unknown: terminating the Linux client does not prove remote commands stopped.

Reconcile both Linux and Windows receipts/latches under original IDs. Never use
a fresh ID, delete state or repeat restoration to clear an error. Status reads
do not need the old execution deadline. Broker status is distinct from a newly
registered R0 remote-status task, which still needs valid scoped broker authority.

Execution is boot-bound: after target reboot, owner reconciles actual effects and
retained receipts/latches before re-enrolling the boot and refreshing authority.
Binding/status reads remain available. Local journals are not external immutable
audit or disk-failure guarantees. Broker Safe stops new admissions; it cannot
atomically undo an admitted remote task.

## Acceptance and evidence limits

From the actual fresh agent identity, prove direct Hyper-V/Docker/default-remoting,
disk/backup, credential/issuer and code/state access denied. Prove valid bounded
task, wrong target/digest, expired authority, invalid parameters, replay, disconnect,
failure-after-write, state I/O failure and reboot quarantine. Check actual gMSA
delegation and target-specific recovery. Missing rows remain not_run.

CI covers real dropped Linux workers with v2 context; Windows PS5 filesystem
journal/error/refusal cases; owner-loader dry-run/tamper refusal; and an actual
ephemeral certificate-authenticated HTTPS/JEA endpoint on a non-domain Windows
runner. It uses only new owned fixture identities/files/certificates. This does
not prove Kerberos, AD/GPO, gMSA ACLs or a user's installed Codex boundary. Public
PRs receive no directory credential or persistent privileged runner.

Sources refreshed 2026-10-30: [JEA configuration](https://learn.microsoft.com/en-us/powershell/scripting/security/remoting/jea/session-configurations),
[JEA security](https://learn.microsoft.com/en-us/powershell/scripting/security/remoting/jea/security-considerations),
[PSRP maintainer](https://github.com/jborean93/pypsrp),
[certificate-auth maintainer](https://github.com/jborean93/winrm-cert-auth),
[Codex managed policy](https://learn.chatgpt.com/docs/enterprise/managed-configuration).
