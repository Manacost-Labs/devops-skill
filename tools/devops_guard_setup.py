#!/usr/bin/env python3
"""Prepare reviewed managed Codex settings; never installs or trusts them."""
import argparse
import base64
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import shlex
import sys


def hook_command(interpreter, script, platform):
    if platform == "windows":
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        code = "$OutputEncoding=[Console]::InputEncoding=[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); & " + quote(interpreter) + " -I " + quote(script) + "; exit $LASTEXITCODE"
        return "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand " + base64.b64encode(code.encode("utf-16-le")).decode("ascii")
    return shlex.join([str(interpreter), "-I", str(script)])


def prepare(runtime, interpreter, platform):
    path_type = PureWindowsPath if platform == "windows" else PurePosixPath
    runtime, interpreter = path_type(runtime), path_type(interpreter)
    if not runtime.is_absolute() or not interpreter.is_absolute():
        raise ValueError("absolute managed paths required")
    managed = runtime / "tools" / "hooks"
    rows = [
        '# Owner review and administrator deployment required. This file grants no task authority.',
        'allowed_approval_policies = ["on-request"]',
        'allowed_approvals_reviewers = ["user"]',
        'default_permissions = ":read-only"',
        'allow_login_shell = false',
        'allow_browser_and_computer_use = false',
        'allowed_web_search_modes = []',
        'allow_managed_hooks_only = true',
        '', '[allowed_permission_profiles]', '":read-only" = true', '":workspace" = false', '":danger-full-access" = false',
        '', '[features]', 'hooks = true', 'unified_exec = false', 'plugins = false', 'apps = false',
        'multi_agent = false', 'browser_use = false', 'browser_use_external = false', 'computer_use = false', 'in_app_browser = false',
        '', '[mcp_servers]', '# Deny unregistered connector identities.',
        '', '[hooks]', ('windows_managed_dir' if platform == 'windows' else 'managed_dir') + ' = ' + json.dumps(str(managed)),
    ]
    for event, file in (("PreToolUse", "codex_pretooluse_gate.py"), ("UserPromptSubmit", "chat_mode_hook.py"), ("SessionStart", "chat_mode_hook.py")):
        command = hook_command(interpreter, managed / file, platform)
        rows += ['', '[[hooks.' + event + ']]']
        if event == "PreToolUse":
            rows.append('matcher = "*"')
        rows += ['[[hooks.' + event + '.hooks]]', 'type = "command"', 'command = ' + json.dumps(command), 'timeout = 15', 'statusMessage = "Checking DevOps boundary"']
    return '\n'.join(rows) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--interpreter", required=True)
    parser.add_argument("--platform", choices=("linux", "windows"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        text = prepare(args.runtime, args.interpreter, args.platform)
        args.output.mkdir(mode=0o700)  # Exclusive new review directory only.
        (args.output / "requirements.review.toml").write_text(text, encoding="utf-8", newline="\n")
        print("PREPARED_NOT_DEPLOYED: review managed requirements; administrator must protect runtime, credentials and host policy, then verify real enforcement")
        return 0
    except Exception:
        print("BLOCKED: invalid managed paths or occupied review output")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
