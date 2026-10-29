# Protected operator sessions

The optional Claude Code hook checks tool calls before execution. It accepts a bounded inspection grammar or a command passed through the approved executor. Unknown commands and options are refused. Enable it explicitly for operator sessions; ordinary development and CI sessions typically leave it disabled.

This is a command and tool filter, not an operating-system sandbox. It assumes trusted, protected hook settings, runtime files, interpreter, PATH and CLI configuration. A CLI can invoke plugins or credential helpers from its configuration. Keep those outside agent write access. Do not expose privileged credentials through an unguarded alternate tool.

## Install

Install a complete runtime using the README instructions. Place this configuration in trusted Claude Code settings, replacing both example paths with absolute paths. The all-tool matcher is required: a Bash-only matcher would leave direct file edits, alternate shells and connector tools outside the gate.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "\"/absolute/path/to/python\" \"/absolute/path/to/devops-runtime/tools/hooks/pretooluse_gate.py\""
          }
        ]
      }
    ]
  }
}
```

Use forward slashes and quoted absolute paths on Windows too. An absolute command path keeps the check working when the shell changes its working directory. Installing a plugin or skill profile does not modify these settings.

The hook returns a tool permission decision and exits 2 on a refusal. It allows Read, Grep, Glob, Skill and AskUserQuestion. Direct Write, Edit, NotebookEdit, PowerShell and unregistered tools are refused. Connector tools need their own reviewed adapter before use in this protected mode; they are denied by default.

## Inspection grammar

The hook checks complete options, not just executable names. Simple inspection pipelines are accepted only when every segment is allowed. Control operators, redirection, subshells, shell expansion, unknown options and explicit paths to arbitrary executables are refused. Conservative refusals can include harmless quoted expressions; do not weaken the filter to guess at full shell semantics.

Examples: `ls -la`, `systemctl status nginx`, `kubectl get pods -A`, `docker ps`, `git status`, bounded GitHub view/list calls and a repository `gh api` GET without body or method flags. Curl inspection requires `-q` first to disable its user configuration, one HTTP(S) URL and known inspection options.

Terraform planning/validation, arbitrary cloud commands, find actions and other operations outside the grammar require the wrapper. Planning may execute providers or external programs, so its name alone does not prove an inspection.

Registered validators and diagnostic scripts are allowed by resolved runtime path. Ledger scripts may only verify, not append. The planner can print a request or save it under the runtime's `operations/plans/` as JSON; it cannot overwrite settings or programs. Planner option abbreviations are disabled. The synthetic demo runs in a development session, not as an unrestricted operator helper.

## Approved execution

Use an absolute executor path when working outside the runtime directory:

```text
python /absolute/runtime/tools/devops_exec.py --operation /absolute/request.json -- command arguments
```

The hook checks the exact command digest, real current UTC execution window and a fresh gate result. It rejects unknown or duplicate wrapper flags. An explicit journal path must remain under runtime `operations/` with a `.jsonl` suffix. The executor rechecks the request before launch and durably records launch intent.

The protected hook never accepts `--at`. That flag remains available only to direct CLIs for isolated deterministic tests. Historical time must never authorize live work.

An argv digest covers arguments, not executable bytes, environment, working directory or referenced files. Protect and verify those inputs separately. Approval records and lock references are local contract data; they are not authenticated identities or an acquired external lock.

## Journal outcomes

- `launch_intent`: intent was durably saved before launch; this alone does not prove a process started.
- `executed`: the child finished; its exit code and service acceptance still need interpretation.
- `timed_out` or `outcome_unknown`: the process started and may have made changes; verify the target before retrying.
- `AUDIT ERROR` / exit 74: execution started but its final record could not be saved. The output never describes this as a pre-launch block.

Pre-launch refusals use `BLOCKED` / exit 3. A child may independently return those same numeric codes; distinguish the outcome message and journal record rather than treating a number alone as proof that nothing ran. Timeout kills the direct child; descendants and remote effects still require investigation. An intent without a completion record is an unresolved operation, not permission to retry.

## Other runtimes

The supplied interception adapter targets Claude Code. Codex skill profiles contain guidance and validators; no equivalent automatic Codex hook adapter is supplied. Run commands through the executor under independently enforced permissions. Skill `allowed-tools` metadata grants Claude pre-approval and does not remove tools from its pool. See the official [skill permission semantics](https://code.claude.com/docs/en/skills#pre-approve-tools-for-a-skill).
