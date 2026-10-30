#!/usr/bin/env python3
"""Native Codex guard. Unknown/edit/connector/delegation tools deny by default.

This is defense in depth. Broker credentials, keys and target access must remain
outside the agent principal even if host callbacks fail or are bypassed.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "broker-client.json"
MAX_INPUT = 1024 * 1024
OFFLINE = {
    "devops-platform-contracts/scripts/validate_platform.py",
    "devops-platform-contracts/scripts/operation_gate.py",
    "devops-platform-contracts/scripts/resolve_capabilities.py",
    "devops-core/scripts/profile_digest.py", "devops-core/scripts/validate_contracts.py",
}


def render(argv, windows=None):
    windows = os.name == "nt" if windows is None else windows
    return "& " + " ".join("'" + value.replace("'", "''") + "'" for value in argv) if windows else shlex.join(argv)


def parse(command, windows=None):
    windows = os.name == "nt" if windows is None else windows
    if not isinstance(command, str) or len(command) > 32768 or any(ord(c) < 32 or ord(c) == 127 for c in command):
        raise ValueError("invalid command")
    if windows:
        if not command.startswith("& "):
            raise ValueError("literal PowerShell invocation required")
        result, index = [], 2
        while index < len(command):
            if command[index] != "'":
                raise ValueError("single-quoted literal required")
            index += 1
            token = ""
            while index < len(command):
                if command[index] == "'":
                    if index + 1 < len(command) and command[index + 1] == "'":
                        token += "'"; index += 2; continue
                    index += 1; break
                token += command[index]; index += 1
            else:
                raise ValueError("unterminated literal")
            result.append(token)
            if index < len(command):
                if command[index] != " ":
                    raise ValueError("literal separator required")
                index += 1
    else:
        result = shlex.split(command, posix=True)
    if not result or render(result, windows) != command:
        raise ValueError("canonical literal invocation required")
    return result


def flags(argv, allowed):
    if len(argv) % 2:
        raise ValueError("paired flags required")
    result = {}
    for index in range(0, len(argv), 2):
        flag, value = argv[index:index + 2]
        if flag not in allowed or flag in result:
            raise ValueError("unknown or duplicate flag")
        result[flag] = value
    return result


def evaluate(event):
    if not isinstance(event, dict) or event.get("hook_event_name") != "PreToolUse":
        return False, "invalid native hook event"
    tool = event.get("tool_name")
    if tool in {"request_user_input", "request_user_input_async", "update_plan"}:
        return True, "non-executing planning or human input"
    if tool != "Bash":
        return False, "direct edits, alternate tools, connectors and delegated execution require a registered protected task"
    value = event.get("tool_input")
    if not isinstance(value, dict) or set(value) - {"command", "description", "timeout_ms", "yield_time_ms", "max_output_tokens", "shell", "login", "workdir", "cwd"}:
        return False, "unsupported shell input fields"
    shell = value.get("shell")
    trusted_shells = {Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"} if os.name == "nt" else {Path("/bin/bash"), Path("/bin/sh")}
    if value.get("login") is True or shell and (not Path(shell).is_absolute() or Path(shell).resolve() not in {path.resolve() for path in trusted_shells}):
        return False, "unsupported shell semantics"
    argv = parse(value.get("command"))
    if len(argv) < 3 or not Path(argv[0]).is_absolute() or Path(argv[0]).resolve() != Path(sys.executable).resolve() or argv[1] != "-I":
        return False, "use the exact trusted interpreter with isolated Python and a registered helper"
    script = Path(argv[2])
    if not script.is_absolute():
        return False, "absolute trusted helper required"
    script = script.resolve()
    relative = script.relative_to(ROOT).as_posix()
    if relative in OFFLINE:
        return True, "offline contract validation only; its output never grants execution"
    if relative == "tools/devops_plan.py":
        # Existing planner output is bounded to the draft directory. It cannot
        # authorize broker execution, even with fabricated JSON approvals.
        spec = importlib.util.spec_from_file_location("native_offline_planner_grammar", ROOT / "tools/hooks/pretooluse_gate.py")
        grammar = importlib.util.module_from_spec(spec); spec.loader.exec_module(grammar)
        return grammar.classify_segment([str(sys.executable), str(script), *argv[3:]], Path(event["cwd"]))
    if relative == "tools/devops_mode.py":
        return bool(argv[3:]) and argv[3] in {"status", "prepare", "safe"}, "planning-mode helpers only; broker independently admits effects"
    if relative != "tools/devops_exec.py":
        return False, "unregistered helper or owner-only issuer"
    parsed = flags(argv[3:], {"--broker-config", "--request", "--grant", "--admission", "--route", "--mode", "--task-id", "--parameters", "--operation-id"})
    if "--broker-config" not in parsed or Path(parsed["--broker-config"]).resolve() != PROFILE.resolve() or not PROFILE.is_file() or PROFILE.is_symlink():
        return False, "managed broker profile is missing or differs from pinned runtime profile"
    if parsed.get("--route", "execute") not in {"prepare", "execute", "restrict", "status", "describe"}:
        return False, "unknown broker route"
    for name in {"--request", "--grant", "--admission"} & parsed.keys():
        if not Path(parsed[name]).is_absolute():
            return False, "absolute input paths required"
    return True, "typed broker client; authority, effects and inputs are independently checked by the broker"


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise ValueError("input limit")
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("duplicate key")
                result[key] = value
            return result
        event = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        allowed, reason = evaluate(event)
    except Exception:
        allowed, reason = False, "unverifiable native tool input"
    if allowed:
        # Do not grant host escalation or rewrite user tool parameters. An empty
        # successful hook leaves ordinary host permissions in force.
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": reason}}))
        return 0
    reason = "BLOCKED: " + reason
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}))
    # A successful callback carries an explicit native denial. On Windows an
    # outer PowerShell command can translate child exit 2 to exit 1, which Codex
    # treats as a failed (potentially fail-open) callback. Never encode policy
    # refusal as transport failure; the real native host tests cover this path.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
