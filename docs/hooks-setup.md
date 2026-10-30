# Native Codex guard and protected setup

The native `PreToolUse` guard denies direct shell, edits, code, connectors,
delegation and unknown tools. It accepts only canonical literal invocations of
registered offline helpers and the pinned typed broker client. It never grants
host escalation. A failed or unsupported callback may fail open in Codex: the
separate broker, target permissions and credential boundaries remain mandatory.

Prepare a reviewable managed configuration without installing anything:

```bash
python tools/devops_guard_setup.py --runtime /absolute/protected/runtime --interpreter /absolute/protected/python --platform linux --output /absolute/new-review-directory
```

On Windows choose `--platform windows` and absolute Windows paths. An administrator
reviews `requirements.review.toml`, protects runtime/interpreter/ancestors and
installs policy at the native managed location. The helper never modifies actual
system settings, grants trust, installs credentials or activates authority.

The prepared closed profile permits read-only execution, requires managed-only
hooks, disables login shells, resumable exec/write_stdin, plugins, apps, browser,
computer use, delegation and ordinary MCP servers. It deliberately grants no
command networking. An owner must separately review a minimal broker-network
profile and egress allowlist for the exact broker; do not enable Full Access or
unrestricted network to make the client work. The client itself requires no
local write lock. Preserve organizational policy instead of replacing it.

SessionStart/UserPromptSubmit callbacks only coordinate local planning cards.
Local confirmation is not an authenticated signature or execution authority.
Native hooks apply to locally orchestrated Codex, not every desktop specialized
surface or cloud Work orchestration. Managed settings and runtime protection
must be independently verified on the exact deployed host/version.

The optional historical Claude adapter retains bounded read grammar and refuses
the removed arbitrary-command wrapper. It is not a new protected Claude broker
integration. Skill `allowed-tools` metadata is not an operating-system deny list.

See [protected execution and migration](protected-execution.md), [mode workflow](autonomy-modes.md),
[official native hook semantics](https://learn.chatgpt.com/docs/hooks), and
[managed policy controls](https://learn.chatgpt.com/docs/enterprise/managed-configuration).
Native CI tests a pinned real Codex CLI against an isolated synthetic provider,
including an executing positive control and a guard-blocked canary. This is
protocol evidence, not proof of production permissions or Windows ACL isolation.
