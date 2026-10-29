#!/usr/bin/env python3
"""Execute one digest-bound command; persist intent before starting the process.

--at is for isolated deterministic CLI tests only and is refused by the protected
hook. Exit 3 means blocked before launch; 74 means execution began but its final
audit record could not be saved. A timeout (124) may already have changed state.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys, uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "devops-platform-contracts/scripts/operation_gate.py"
DEFAULT_LEDGER = ROOT / "operations/execution-ledger.jsonl"
BLOCKED_EXIT = 3
AUDIT_ERROR_EXIT = 74
OUTPUT_TAIL_CHARS = 4000
REDACTED = "[REDACTED]"
KEY_VALUE_SECRET = re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?key|authorization)\b(\s*[=:]\s*)\S+")
VALUE_SECRETS = (
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN[A-Z ]+KEY-----[\s\S]+?-----END[A-Z ]+KEY-----"),
)

def canonical_command_digest(argv):
    return "sha256:" + hashlib.sha256(json.dumps(list(argv), ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()

def redact(text):
    text = KEY_VALUE_SECRET.sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", text)
    for pattern in VALUE_SECRETS:
        text = pattern.sub(REDACTED, text)
    return text

def tail(text):
    return text[-OUTPUT_TAIL_CHARS:]

def append_ledger(ledger_path, entry):
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if ledger_path.is_symlink():
        raise OSError("execution ledger must not be a symlink")
    record = dict(entry, recorded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())

def blocked(reason, ledger_path, entry, status):
    print(f"BLOCKED: {redact(reason)}")
    entry.update(status=status, reason=redact(reason), exit_code=None)
    try:
        append_ledger(ledger_path, entry)
    except OSError:
        print("BLOCKED: execution ledger is unavailable; no command was launched")
    return BLOCKED_EXIT

def finish(ledger_path, entry, status, code, reason=None):
    entry.update(status=status, exit_code=code, reason=reason)
    try:
        append_ledger(ledger_path, entry)
    except OSError:
        print(f"AUDIT ERROR: command already started; outcome={status}, exit={code}. "
              "The final execution record could not be saved. Verify the target before retrying.")
        return AUDIT_ERROR_EXIT
    return code

def main():
    arguments = sys.argv[1:]
    if "--" not in arguments:
        print("BLOCKED: no command was provided after --")
        return BLOCKED_EXIT
    split = arguments.index("--")
    command = arguments[split + 1:]
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--operation", type=Path, required=True)
    parser.add_argument("--policy", default="default-policy.json")
    parser.add_argument("--at", help="Isolated CLI test clock; never allowed in a protected operator session.")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--timeout-seconds", type=int)
    args = parser.parse_args(arguments[:split])
    entry = {"execution_id": str(uuid.uuid4()), "operation_id": None, "policy": args.policy,
             "command": None, "command_digest": None}
    launched = False
    try:
        if not command or (args.timeout_seconds is not None and args.timeout_seconds < 1):
            return blocked("a command and a positive timeout are required", args.ledger, entry, "blocked_usage")
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
            return blocked(f"command digest {digest} does not match approved plan digest {plan_digest}", args.ledger, entry, "blocked_digest_mismatch")
        gate_arguments = [sys.executable, str(GATE), "--request", str(args.operation), "--policy", args.policy]
        if args.at:
            gate_arguments += ["--at", args.at]
        gate = subprocess.run(gate_arguments, capture_output=True, text=True, check=False)
        print(redact((gate.stdout + gate.stderr).strip()))
        if gate.returncode or not gate.stdout.startswith("ALLOWED:"):
            return blocked("operation gate refused execution immediately before launch", args.ledger, entry, "blocked_gate")
        # A durable intent must exist before any child can make a change.
        entry.update(status="launch_intent", exit_code=None, reason=None)
        try:
            append_ledger(args.ledger, entry)
        except OSError:
            return blocked("execution journal could not persist intent", args.ledger, entry, "blocked_ledger")
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except OSError:
            return blocked("approved executable could not be launched", args.ledger, entry, "blocked_launch")
        launched = True
        try:
            stdout, stderr = process.communicate(timeout=args.timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            entry.update(stdout_tail=tail(redact(stdout)), stderr_tail=tail(redact(stderr)))
            print("EXECUTION TIMED OUT: the command started and may have changed state. Verify the target before retrying.")
            return finish(args.ledger, entry, "timed_out", 124, "process exceeded its timeout; child processes and target state require verification")
        # Redact the complete output before truncation, including multiline keys.
        entry.update(stdout_tail=tail(redact(stdout)), stderr_tail=tail(redact(stderr)))
        if entry["stdout_tail"]:
            print(entry["stdout_tail"])
        if entry["stderr_tail"]:
            print(entry["stderr_tail"], file=sys.stderr)
        print(f"EXECUTED: {entry['operation_id']} exit={process.returncode} digest={digest}")
        return finish(args.ledger, entry, "executed", process.returncode)
    except Exception as error:
        if launched:
            print("EXECUTION UNCERTAIN: the command already started. Verify the target before retrying.")
            return finish(args.ledger, entry, "outcome_unknown", 4, f"post-launch error ({type(error).__name__})")
        return blocked(f"invalid execution input ({type(error).__name__})", args.ledger, entry, "blocked_error")

if __name__ == "__main__":
    raise SystemExit(main())
