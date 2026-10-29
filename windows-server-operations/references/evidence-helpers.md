# Read-only evidence helpers

Run only from a protected trusted runtime in an existing approved local/remoting session. Helpers do not establish target authority or invoke remoting/setup. They rely on trusted PowerShell/native modules and a stable owner-controlled path/store; they are not a sandbox against a concurrent hostile administrator.

Use PowerShell 5.1 or 7 on the confirmed Windows target. They return JSON. Exit 0 means the requested inventory was produced, not that access, trust, health or recovery passed. Exit 2 means an unsupported target/invalid request or incomplete collection; inspect the status. Native parameter-binding diagnostics can precede script error handling: never put secret values in arguments.

| Helper | Parameters | Evidence and limits |
|---|---|---|
| win-host-audit.ps1 | MaxItems 1–100, default 20 | Server ProductType/build, bounded volume/service/event/firewall/listener/share/task/disk/reboot metadata. Per-section unknown and truncation; no event messages, task arguments, service command lines or private keys |
| inspect-file-access.ps1 | LiteralPath; MaxRules 1–500, default 128; optional IncludeSddl | One local descriptor, SIDs, ordinary ACE rights/inheritance, null/empty DACL distinction, owner/group/DACL hash. Complex ACE types cause rule projection to be omitted explicitly; SACL and effective remote access are unverified; SDDL is emitted only when explicitly requested |
| inspect-certificate.ps1 | Exact 40-hex Thumbprint; StoreLocation LocalMachine/CurrentUser; StoreName My/WebHosting/Remote Desktop | UTC validity, public algorithm/EKU IDs, key-presence flag. No names/key export, chain/revocation traffic, binding or service-key test |
| inspect-task-definition.ps1 | LiteralPath | One offline XML <=256 KiB; DTD/entities prohibited, bounded structural enum counts. No raw action/identity text, schema certification, registration or execution |

File/XML helpers accept local filesystem drive paths, reject UNC/mapped network paths, alternate streams and observed reparse components, and never walk a tree. Authorize the exact resolved path and artifact I/O first. Path checks are point-in-time observations; protect files/directories against concurrent replacement. A privileged forensic/adversarial collection needs its own tool/environment.

The descriptor hash identifies raw owner/group/DACL SDDL, not semantic access equivalence. Windows can normalize inheritance bookkeeping when applying a descriptor. Capture the resulting native state and verify intended allow/deny behavior; do not ignore differences on an operating target. Conditional/callback/object ACEs require contextual review: the helper reports their types and total ACE count, omits all simplified rules, and preserves the full descriptor hash. An omitted projection is not an empty DACL. Full SDDL is still opt-in sensitive evidence.

Host queries are count-bounded, not a universal hard timeout on all Windows providers. CIM operations request a short operation timeout, but some native providers can still delay; bound the authorized session externally and stop expensive collection on degraded systems. Empty successful results apply only to their query scope; missing command/permission/collection failure becomes unknown. Automatic service candidates, reboot markers, task names and shares are not health/recovery judgments.

Reports can still contain internal resource names, addresses and SIDs. Review locally and redact before storage/sharing. The XML helper deliberately does not emit arbitrary principal/action strings, including malformed enum text. Restricted tool errors use generic script output; raw target exceptions are not copied into JSON.
