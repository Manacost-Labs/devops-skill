#!/usr/bin/env python3
"""Build a contract-v2 operation request bound to one exact command.

Usage:
    python tools/devops_plan.py --target-profile profile.yaml \
        --action container_rollout --risk R2 \
        --objective "Roll out the approved immutable release" \
        --scope service:api --verify "health endpoint returns 2xx" \
        -- docker compose up -d

The builder computes the three bindings that cannot reasonably be produced by
hand: the canonical digest of the exact command argv, the canonical digest of
the selected registered policy, and the validated target-profile digest. It
also derives the minimum risk class the policy implies and refuses to emit a
request that understates it.

It never manufactures authorization. Approvals are emitted as structurally
incomplete slots that the operation gate rejects until a real approver, role,
evidence reference, and time window replace them, and required recovery
evidence is left empty rather than invented. Passing the unedited output to
tools/devops_exec.py is expected to be BLOCKED.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "devops-platform-contracts" / "scripts" / "operation_gate.py"
PROFILE_DIGEST_TOOL = ROOT / "devops-core" / "scripts" / "profile_digest.py"
RISK_ORDER = ("R0", "R1", "R2", "R3", "R4")
RISK_RANK = {name: index for index, name in enumerate(RISK_ORDER)}
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
UNSAFE_ID = re.compile(r"[^A-Za-z0-9._-]+")


def canonical_command_digest(argv: list[str]) -> str:
    payload = json.dumps(list(argv), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def load_gate_module():
    spec = importlib.util.spec_from_file_location("operation_gate_for_planning", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def target_profile_digest(path: Path) -> str:
    result = subprocess.run([sys.executable, str(PROFILE_DIGEST_TOOL), str(path)], capture_output=True, text=True, check=False)
    value = result.stdout.strip()
    if result.returncode != 0 or not DIGEST.fullmatch(value):
        raise ValueError(f"target profile is invalid or undigestible: {(result.stdout + result.stderr).strip()}")
    return value


def minimum_risk(policy: dict[str, Any], action: str, environment: str, stateful: bool, destructive: bool, external: bool) -> tuple[str, list[str]]:
    minimum = "R0"
    reasons: list[str] = []

    def raise_to(level: str, reason: str) -> None:
        nonlocal minimum
        if RISK_RANK[level] > RISK_RANK[minimum]:
            minimum = level
        reasons.append(reason)

    if external:
        raise_to("R2", "external side effects require at least R2")
    if environment == "production" and external:
        raise_to("R3", "production mutation requires at least R3")
    if action in set(policy["always_require_approval"]):
        raise_to("R3", f"policy lists '{action}' as always requiring approval, which needs at least R3")
    if destructive:
        raise_to("R4", "destructive work must be classified R4")
    if stateful and not destructive:
        reasons.append("stateful work at R4 or destructive work requires proven recovery")
    return minimum, reasons


def build_request(args: argparse.Namespace, command: list[str], gate: Any) -> tuple[dict[str, Any], list[str]]:
    policy, policy_digest = gate.load_registered_policy(args.policy)
    profile_path = Path(args.target_profile)
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8-sig"))
    if not isinstance(profile, dict):
        raise ValueError("target profile must be a YAML mapping")
    profile_digest = target_profile_digest(profile_path)

    name = str(profile.get("name", "")).strip()
    environment = str(profile.get("environment", "")).strip()
    owner = str(profile.get("owner", "")).strip()
    classification = args.data_classification or str(profile.get("data_classification", "")).strip()
    if not name or not environment or not owner:
        raise ValueError("target profile must declare name, environment, and owner")
    if classification not in set(policy["data"]["allowed_classifications"]):
        raise ValueError(f"data classification '{classification}' is not allowed by {policy['policy_id']}")

    plan_digest = canonical_command_digest(command)
    floor, notes = minimum_risk(policy, args.action, environment, args.stateful, args.destructive, args.external_side_effects)
    if RISK_RANK[args.risk] < RISK_RANK[floor]:
        raise ValueError(f"--risk {args.risk} understates this change; policy and flags require at least {floor}: " + "; ".join(notes))
    if args.destructive and args.risk != "R4":
        raise ValueError("destructive work must be classified exactly R4")
    if RISK_RANK[args.risk] >= RISK_RANK["R2"] and not args.verify:
        raise ValueError("--verify is required at R2 and above: acceptance criteria must exist before approval is requested")

    now = gate.parse_time(args.at, "--at", []) if args.at else datetime.now(timezone.utc)
    if now is None:
        raise ValueError("--at must be an RFC3339 timestamp with timezone")
    window_end = now + timedelta(minutes=args.window_minutes)
    ttl = policy["approval_ttl_minutes"]
    if args.window_minutes > ttl:
        raise ValueError(f"--window-minutes {args.window_minutes} exceeds the {ttl}-minute approval TTL of {policy['policy_id']}")

    slug = UNSAFE_ID.sub("-", name).strip("-")[:60] or "target"
    short = plan_digest[7:15]
    required_approvals = policy["minimum_approvals"][args.risk]
    if args.action in set(policy["always_require_approval"]) or args.external_side_effects:
        required_approvals = max(required_approvals, 1)
    needs_lock = args.risk in set(policy["require_change_lock"])
    needs_recovery = args.action in set(policy["require_recovery_evidence"]) or (args.stateful and (args.risk == "R4" or args.destructive))

    approval_slot = {
        "approver": "",
        "role": "",
        "target": name,
        "plan_digest": plan_digest,
        "policy_digest": policy_digest,
        "approved_at": None,
        "expires_at": None,
        "evidence_ref": "",
    }
    request = {
        "schema_version": "2.0",
        "operation_id": args.operation_id or f"ops-{slug}-{short}",
        "objective": args.objective,
        "data_classification": classification,
        "policy": {"id": policy["policy_id"], "version": policy["version"], "digest": policy_digest},
        "target": {"name": name, "environment": environment, "owner": owner, "profile_digest": profile_digest},
        "change": {
            "action": args.action,
            "risk": args.risk,
            "scope": list(args.scope),
            "plan_digest": plan_digest,
            "stateful": args.stateful,
            "destructive": args.destructive,
            "external_side_effects": args.external_side_effects,
        },
        "execution": {
            "executor": args.executor,
            "requested_at": now.isoformat().replace("+00:00", "Z"),
            "window_start": now.isoformat().replace("+00:00", "Z"),
            "window_end": window_end.isoformat().replace("+00:00", "Z"),
            "idempotency_key": f"{slug}-{short}",
            "change_lock_ref": args.change_lock if args.change_lock else ("" if needs_lock else None),
        },
        "approvals": [dict(approval_slot) for _ in range(required_approvals)],
        "recovery": {
            "required": needs_recovery,
            "method": args.recovery_method or ("" if needs_recovery else None),
            "artifact_ref": args.recovery_artifact or ("" if needs_recovery else None),
            "restore_tested_at": args.restore_tested_at,
            "rpo_minutes": args.rpo_minutes,
            "rto_minutes": args.rto_minutes,
        },
        "verification": {"criteria": list(args.verify), "observation_window_minutes": args.observation_minutes},
        "exception": None,
    }

    todo: list[str] = []
    if required_approvals:
        distinct = " from distinct approvers with distinct roles" if required_approvals > 1 else ""
        todo.append(f"fill {required_approvals} approval slot(s){distinct}: approver, role, evidence_ref, approved_at, expires_at (within {ttl} minutes)")
    if policy["require_separation_of_duties"][args.risk]:
        todo.append(f"separation of duties applies at {args.risk}: the executor '{args.executor}' must not appear as an approver")
    if needs_lock and not args.change_lock:
        todo.append(f"acquire a target-scoped change lock and set execution.change_lock_ref ({args.risk} requires it)")
    if needs_recovery:
        missing = [field for field, value in (("method", args.recovery_method), ("artifact_ref", args.recovery_artifact), ("restore_tested_at", args.restore_tested_at), ("rpo_minutes", args.rpo_minutes), ("rto_minutes", args.rto_minutes)) if value in (None, "")]
        if missing:
            todo.append("prove recovery before execution and set recovery." + ", recovery.".join(missing))
    return request, todo


def main() -> int:
    arguments = sys.argv[1:]
    if "--" not in arguments:
        print("BLOCKED: no command was provided after --")
        return 2
    split = arguments.index("--")
    command = arguments[split + 1 :]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target-profile", required=True, help="Validated non-secret target profile YAML.")
    parser.add_argument("--action", required=True, help="Action identifier, [a-z0-9_-]{2,80}.")
    parser.add_argument("--risk", required=True, choices=list(RISK_ORDER), help="Declared risk class; must not understate policy.")
    parser.add_argument("--objective", required=True, help="What this operation achieves, 8-1000 characters.")
    parser.add_argument("--scope", action="append", default=[], help="Affected scope entry; repeatable.")
    parser.add_argument("--verify", action="append", default=[], help="Acceptance criterion; repeatable, required at R2+.")
    parser.add_argument("--policy", default="default-policy.json", help="Registered policy basename.")
    parser.add_argument("--executor", default="service:codex", help="Execution identity.")
    parser.add_argument("--operation-id", help="Override the generated operation ID.")
    parser.add_argument("--data-classification", help="Override the profile data classification.")
    parser.add_argument("--window-minutes", type=int, default=60, help="Execution window length from now.")
    parser.add_argument("--observation-minutes", type=int, default=10, help="Post-change observation window.")
    parser.add_argument("--stateful", action="store_true", help="The change alters persistent state.")
    parser.add_argument("--destructive", action="store_true", help="The change destroys data or resources (forces R4).")
    parser.add_argument("--external-side-effects", action="store_true", help="The change is observable outside the target.")
    parser.add_argument("--change-lock", help="Target-scoped change lock reference.")
    parser.add_argument("--recovery-method", help="How the change is reversed.")
    parser.add_argument("--recovery-artifact", help="Reference to the recovery artifact.")
    parser.add_argument("--restore-tested-at", help="RFC3339 time an isolated restore was proven.")
    parser.add_argument("--rpo-minutes", type=int, help="Measured recovery point objective.")
    parser.add_argument("--rto-minutes", type=int, help="Measured recovery time objective.")
    parser.add_argument("--at", help="RFC3339 build time for deterministic output; defaults to now.")
    parser.add_argument("--output", type=Path, help="Write the request here instead of stdout.")
    args = parser.parse_args(arguments[:split])

    try:
        if not command:
            raise ValueError("no command was provided after --")
        if not args.scope:
            raise ValueError("--scope is required at least once")
        gate = load_gate_module()
        request, todo = build_request(args, command, gate)
    except (OSError, ValueError, TypeError, yaml.YAMLError, json.JSONDecodeError) as error:
        print(f"BLOCKED: {error}")
        return 2

    payload = json.dumps(request, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        if args.output.exists():
            print(f"BLOCKED: refusing to overwrite an existing request: {args.output}")
            return 2
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
        print(f"WROTE: {args.output}")
    else:
        print(payload, end="")

    summary = [
        "",
        f"PLAN DIGEST: {request['change']['plan_digest']} bound to: {subprocess.list2cmdline(command)}",
        f"POLICY: {request['policy']['id']} {request['policy']['digest']}",
        f"TARGET: {request['target']['name']} ({request['target']['environment']}) {request['target']['profile_digest']}",
        f"RISK: {request['change']['risk']}",
        "",
        "NOT YET AUTHORIZED. This request is deliberately incomplete:",
    ]
    summary += [f"  - {item}" for item in todo] or ["  - nothing further is required by policy for this risk class"]
    summary += [
        "",
        "Then execute exactly this command through the gate:",
        f"  python tools/devops_exec.py --operation {args.output or '<request.json>'} --policy {args.policy} -- {subprocess.list2cmdline(command)}",
    ]
    print("\n".join(summary), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
