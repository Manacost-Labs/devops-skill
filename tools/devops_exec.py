#!/usr/bin/env python3
"""Execute exactly one approved command through the fail-closed operation gate.

Usage:
    python tools/devops_exec.py --operation operation.json [--policy NAME] \
        [--at RFC3339] [--ledger PATH] -- <command> [args...]

The wrapper recomputes the canonical digest of the actual command, requires it
to equal the approved ``change.plan_digest``, re-runs the operation gate
immediately before execution, executes without a shell, and appends a
secret-redacted record to a local execution ledger. Any mismatch, gate refusal,
or internal error blocks execution with a non-zero exit code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "devops-platform-contracts" / "scripts" / "operation_gate.py"
DEFAULT_LEDGER = ROOT / "operations" / "execution-ledger.jsonl"
BLOCKED_EXIT = 3
OUTPUT_TAIL_CHARS = 4000
REDACTED = "[REDACTED]"
KEY_VALUE_SECRET = re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?key|authorization)\b(\s*[=:]\s*)\S+")
VALUE_SECRETS = (
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN[A-Z ]+KEY-----[\s\S]+?-----END[A-Z ]+KEY-----"),
)


def canonical_command_digest(argv: list[str]) -> str:
    payload = json.dumps(list(argv), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def redact(text: str) -> str:
    text = KEY_VALUE_SECRET.sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", text)
    for pattern in VALUE_SECRETS:
        text = pattern.sub(REDACTED, text)
    return text


def tail(text: str) -> str:
    return text if len(text) <= OUTPUT_TAIL_CHARS else text[-OUTPUT_TAIL_CHARS:]


def append_ledger(ledger_path: Path, entry: dict) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def blocked(reason: str, ledger_path: Path, entry: dict, status: str) -> int:
    print(f"BLOCKED: {reason}")
    entry.update({"status": status, "reason": redact(reason), "exit_code": None})
    try:
        append_ledger(ledger_path, entry)
    except OSError as error:
        print(f"BLOCKED: execution ledger is unavailable: {error}")
    return BLOCKED_EXIT


def main() -> int:
    arguments = sys.argv[1:]
    if "--" not in arguments:
        print("BLOCKED: no command was provided after --")
        return BLOCKED_EXIT
    split = arguments.index("--")
    command = arguments[split + 1 :]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", type=Path, required=True, help="Secret-free JSON operation request v2.")
    parser.add_argument("--policy", default="default-policy.json", help="Registered policy basename.")
    parser.add_argument("--at", help="RFC3339 evaluation time for deterministic testing; defaults to now.")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER, help="Append-only execution ledger path.")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Optional command timeout.")
    args = parser.parse_args(arguments[:split])

    entry = {
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "operation_id": None,
        "policy": args.policy,
        "command": None,
        "command_digest": None,
    }
    try:
        if not command:
            return blocked("no command was provided after --", args.ledger, entry, "blocked_usage")
        if any(not isinstance(item, str) for item in command):
            return blocked("command arguments must be strings", args.ledger, entry, "blocked_usage")
        entry["command"] = redact(subprocess.list2cmdline(command))
        digest = canonical_command_digest(command)
        entry["command_digest"] = digest

        request = json.loads(args.operation.read_text(encoding="utf-8-sig"))
        if not isinstance(request, dict):
            return blocked("operation request must be a JSON object", args.ledger, entry, "blocked_request")
        entry["operation_id"] = request.get("operation_id") if isinstance(request.get("operation_id"), str) else None
        change = request.get("change")
        plan_digest = change.get("plan_digest") if isinstance(change, dict) else None
        if not isinstance(plan_digest, str):
            return blocked("operation request does not declare change.plan_digest", args.ledger, entry, "blocked_request")
        if plan_digest != digest:
            return blocked(
                f"command digest {digest} does not match approved plan digest {plan_digest}",
                args.ledger, entry, "blocked_digest_mismatch",
            )

        gate_arguments = [sys.executable, str(GATE), "--request", str(args.operation), "--policy", args.policy]
        if args.at:
            gate_arguments += ["--at", args.at]
        gate = subprocess.run(gate_arguments, capture_output=True, text=True, check=False)
        gate_output = (gate.stdout + gate.stderr).strip()
        print(gate_output)
        if gate.returncode != 0 or not gate.stdout.startswith("ALLOWED:"):
            return blocked("operation gate refused execution immediately before launch", args.ledger, entry, "blocked_gate")

        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout_seconds, check=False)
        except subprocess.TimeoutExpired:
            return blocked("command execution timed out before completion", args.ledger, entry, "blocked_timeout")
        stdout = redact(tail(result.stdout))
        stderr = redact(tail(result.stderr))
        if stdout:
            print(stdout, end="" if stdout.endswith("\n") else "\n")
        if stderr:
            print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr)
        entry.update({"status": "executed", "reason": None, "exit_code": result.returncode, "stdout_tail": stdout, "stderr_tail": stderr})
        append_ledger(args.ledger, entry)
        print(f"EXECUTED: {entry['operation_id']} exit={result.returncode} digest={digest}")
        return result.returncode
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return blocked(f"invalid execution input: {error}", args.ledger, entry, "blocked_error")
    except Exception as error:  # fail closed on anything unexpected
        return blocked(f"internal wrapper error ({type(error).__name__})", args.ledger, entry, "blocked_error")


if __name__ == "__main__":
    raise SystemExit(main())
