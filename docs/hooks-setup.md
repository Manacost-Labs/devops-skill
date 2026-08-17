# Enforcement hook setup

`tools/hooks/pretooluse_gate.py` turns the operation gate from a convention into a
mechanism. Without it, `operation_gate.py` is advisory: an agent that skips the gate
can still execute a mutating command. With the hook installed, the agent runtime
consults the hook before every shell command, and the hook denies anything that is
not provably read-only and not bound to a fresh gate PASS.

## Install

Add the hook to the Claude Code settings of the workspace that operates infrastructure
(`.claude/settings.json` in the checkout, or the user-level settings file):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python tools/hooks/pretooluse_gate.py"
          }
        ]
      }
    ]
  }
}
```

The hook reads the standard PreToolUse JSON payload on stdin and answers with a
`permissionDecision` of `allow` or `deny`. A deny also exits with status 2 so that
runtimes that ignore the JSON body still block the call.

## Decision rules

| Command class | Decision |
|---|---|
| Provably read-only segments (`ls`, `cat`, `grep`, `systemctl status`, `kubectl get/describe/logs`, `terraform plan/validate/show`, `docker ps/inspect/logs`, `git status/log/diff`, `aws/gcloud/az/openstack` describe/list/get/show, `gh` view/list/checks and `gh api` without a method or body, plain `curl` GET probes, ...) | allow |
| Registered platform scripts, verified by resolved path (validators, `operation_gate.py`, `resolve_capabilities.py`, `ledger_chain.py`, digest tools, preflight and verification scripts, the portfolio demo runner) | allow |
| `python tools/devops_exec.py --operation <request> -- <command>` | allow only after the hook re-verifies that `change.plan_digest` equals the canonical digest of the exact wrapped command, the execution window is open, and `operation_gate.py` returns a fresh PASS for that request |
| Mutating verbs (`terraform apply/destroy`, `kubectl apply/delete/patch/scale`, `docker compose up/down`, `systemctl restart/stop/disable`, `rm`, `dd`, `mkfs`, package installs, firewall changes, cloud create/update/delete, ...) | deny with the exact remediation |
| Obfuscation: `bash -c`, `sh -c`, `eval`, `xargs`, `env` wrappers, `base64`, command substitution `$(...)`, backticks, variable expansion `$VAR`, multi-line commands, redirections, unknown executables | deny (fail closed) |

The canonical command digest is `sha256` over the JSON encoding of the exact argv
list, computed identically by the hook and by `tools/devops_exec.py`. Approving a
plan therefore approves one exact command, not a family of similar commands.

## Properties and limits

- Fail closed: a command the hook cannot classify is treated as mutating; a hook
  crash denies the call.
- The wrapper re-runs the gate itself immediately before launch, so editing the
  operation file between the hook check and execution does not help an attacker.
- The hook governs shell commands. File edits and other tools are constrained by
  the per-module `allowed-tools` declarations validated by
  `devops-platform-contracts/scripts/validate_platform.py`.
- The hook only protects sessions where it is installed. CI and development
  sessions that run the repository's own test suite typically omit it; operator
  sessions that can reach real infrastructure must not.
