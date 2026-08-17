#!/usr/bin/env python3
"""Fail-closed authorization gate for DevOps operation contract v2."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = ROOT / "devops-platform-contracts" / "policies"
REGISTERED_POLICIES = {
    "default-policy.json": "default-baseline",
    "enterprise-policy.json": "enterprise-baseline",
}
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
OPERATION_ID = re.compile(r"^ops-[A-Za-z0-9._-]{6,120}$")
ACTION = re.compile(r"^[a-z0-9_-]{2,80}$")
POLICY_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
RISK_ORDER = ("R0", "R1", "R2", "R3", "R4")
RISK = set(RISK_ORDER)
RISK_RANK = {name: index for index, name in enumerate(RISK_ORDER)}
DATA_CLASSES = {"public", "internal", "confidential", "restricted"}
TOP_LEVEL = {"schema_version", "operation_id", "objective", "data_classification", "policy", "target", "change", "execution", "approvals", "recovery", "verification", "exception"}
FIELDS = {
    "policy": {"id", "version", "digest"},
    "target": {"name", "environment", "owner", "profile_digest"},
    "change": {"action", "risk", "scope", "plan_digest", "stateful", "destructive", "external_side_effects"},
    "execution": {"executor", "requested_at", "window_start", "window_end", "idempotency_key", "change_lock_ref"},
    "approval": {"approver", "role", "target", "plan_digest", "policy_digest", "approved_at", "expires_at", "evidence_ref"},
    "recovery": {"required", "method", "artifact_ref", "restore_tested_at", "rpo_minutes", "rto_minutes"},
    "verification": {"criteria", "observation_window_minutes"},
    "exception": {"owner", "evidence_ref", "rationale", "compensating_controls", "approved_at", "expires_at"},
}
POLICY_FIELDS = {
    "version", "policy_id", "risk_classes", "approval_ttl_minutes",
    "minimum_approvals", "require_separation_of_duties",
    "require_change_lock", "require_plan_digest", "always_require_approval",
    "require_recovery_evidence", "deny_by_default", "completion_statuses",
    "exceptions", "ledger", "data",
}
POLICY_LIST_FIELDS = (
    "require_change_lock", "require_plan_digest", "always_require_approval",
    "require_recovery_evidence", "deny_by_default",
)


def canonical_policy_digest(policy: dict[str, Any]) -> str:
    canonical = json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def is_integer(value: Any) -> bool:
    return type(value) is int


def valid_text(value: Any, minimum: int = 1, maximum: int | None = None) -> bool:
    if not isinstance(value, str):
        return False
    size = len(value.strip())
    return size >= minimum and (maximum is None or size <= maximum)


def parse_time(value: Any, field: str, reasons: list[str]) -> datetime | None:
    if not isinstance(value, str):
        reasons.append(f"{field} must be an RFC3339 timestamp")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
        return parsed.astimezone(timezone.utc)
    except ValueError:
        reasons.append(f"{field} must be an RFC3339 timestamp with timezone")
        return None


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key == "extends":
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def require_exact_keys(value: dict[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required)
    if missing or unknown:
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unknown " + ", ".join(unknown))
        raise ValueError(f"{label} fields invalid: {'; '.join(details)}")


def validate_policy_shape(policy: dict[str, Any], label: str) -> None:
    require_exact_keys(policy, POLICY_FIELDS, label)
    if policy.get("version") != "2.0":
        raise ValueError(f"{label} version must be 2.0")
    if not isinstance(policy.get("policy_id"), str) or not POLICY_ID.fullmatch(policy["policy_id"]):
        raise ValueError(f"{label} policy_id is invalid")
    if policy.get("risk_classes") != list(RISK_ORDER):
        raise ValueError(f"{label} risk_classes are invalid")
    if not is_integer(policy.get("approval_ttl_minutes")) or policy["approval_ttl_minutes"] <= 0:
        raise ValueError(f"{label} approval_ttl_minutes must be a positive integer")
    for field in ("minimum_approvals", "require_separation_of_duties"):
        values = policy.get(field)
        if not isinstance(values, dict) or set(values) != RISK:
            raise ValueError(f"{label} {field} must cover R0-R4")
    if any(not is_integer(value) or value < 0 for value in policy["minimum_approvals"].values()):
        raise ValueError(f"{label} minimum_approvals are invalid")
    if any(type(value) is not bool for value in policy["require_separation_of_duties"].values()):
        raise ValueError(f"{label} separation-of-duties values are invalid")
    for field in POLICY_LIST_FIELDS:
        values = policy.get(field)
        if not isinstance(values, list) or any(not valid_text(value) for value in values) or len(values) != len(set(values)):
            raise ValueError(f"{label} {field} must contain unique non-empty strings")
    for field in ("require_change_lock", "require_plan_digest"):
        if not set(policy[field]) <= RISK:
            raise ValueError(f"{label} {field} contains an invalid risk class")
    for field in ("always_require_approval", "require_recovery_evidence", "deny_by_default"):
        if any(not ACTION.fullmatch(value) for value in policy[field]):
            raise ValueError(f"{label} {field} contains an invalid action/control identifier")
    if set(policy.get("completion_statuses", [])) != {"verified", "partially_verified", "rolled_back", "blocked"}:
        raise ValueError(f"{label} completion_statuses are invalid")
    exceptions = policy.get("exceptions")
    if not isinstance(exceptions, dict):
        raise ValueError(f"{label} exceptions must be an object")
    require_exact_keys(exceptions, {"allowed", "max_ttl_minutes", "minimum_compensating_controls", "never_waive"}, f"{label} exceptions")
    if type(exceptions["allowed"]) is not bool:
        raise ValueError(f"{label} exceptions.allowed must be boolean")
    if not is_integer(exceptions["max_ttl_minutes"]) or exceptions["max_ttl_minutes"] <= 0:
        raise ValueError(f"{label} exception TTL must be a positive integer")
    if not is_integer(exceptions["minimum_compensating_controls"]) or exceptions["minimum_compensating_controls"] < 1:
        raise ValueError(f"{label} minimum_compensating_controls must be positive")
    never_waive = exceptions["never_waive"]
    if not isinstance(never_waive, list) or not never_waive or any(not valid_text(value) for value in never_waive) or len(never_waive) != len(set(never_waive)):
        raise ValueError(f"{label} never_waive must contain unique non-empty strings")
    ledger = policy.get("ledger")
    if not isinstance(ledger, dict):
        raise ValueError(f"{label} ledger must be an object")
    require_exact_keys(ledger, {"hash_chain", "external_immutable_sink_required"}, f"{label} ledger")
    if any(type(value) is not bool for value in ledger.values()):
        raise ValueError(f"{label} ledger values must be boolean")
    data = policy.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"{label} data must be an object")
    require_exact_keys(data, {"allowed_classifications", "default"}, f"{label} data")
    allowed = data["allowed_classifications"]
    if not isinstance(allowed, list) or not allowed or any(not valid_text(value) for value in allowed) or len(allowed) != len(set(allowed)):
        raise ValueError(f"{label} allowed_classifications are invalid")
    if not set(allowed) <= DATA_CLASSES:
        raise ValueError(f"{label} contains an unknown data classification")
    if data["default"] not in allowed:
        raise ValueError(f"{label} default data classification is not allowed")


def ensure_not_weaker(parent: dict[str, Any], child: dict[str, Any], label: str) -> None:
    if child["approval_ttl_minutes"] > parent["approval_ttl_minutes"]:
        raise ValueError(f"{label} cannot lengthen approval TTL")
    for risk in RISK_ORDER:
        if child["minimum_approvals"][risk] < parent["minimum_approvals"][risk]:
            raise ValueError(f"{label} cannot reduce approval count for {risk}")
        if parent["require_separation_of_duties"][risk] and not child["require_separation_of_duties"][risk]:
            raise ValueError(f"{label} cannot disable separation of duties for {risk}")
    for field in POLICY_LIST_FIELDS:
        if not set(child[field]) >= set(parent[field]):
            raise ValueError(f"{label} weakens {field}")
    parent_exceptions = parent["exceptions"]
    child_exceptions = child["exceptions"]
    if not parent_exceptions["allowed"] and child_exceptions["allowed"]:
        raise ValueError(f"{label} cannot enable exceptions disabled by its parent")
    if child_exceptions["max_ttl_minutes"] > parent_exceptions["max_ttl_minutes"]:
        raise ValueError(f"{label} cannot lengthen exception TTL")
    if child_exceptions["minimum_compensating_controls"] < parent_exceptions["minimum_compensating_controls"]:
        raise ValueError(f"{label} cannot reduce compensating controls")
    if not set(child_exceptions["never_waive"]) >= set(parent_exceptions["never_waive"]):
        raise ValueError(f"{label} weakens never_waive")
    for field in ("hash_chain", "external_immutable_sink_required"):
        if parent["ledger"][field] and not child["ledger"][field]:
            raise ValueError(f"{label} cannot disable ledger control {field}")
    if not set(child["data"]["allowed_classifications"]) <= set(parent["data"]["allowed_classifications"]):
        raise ValueError(f"{label} broadens allowed data classifications")


def _load_registered_policy(filename: str, stack: tuple[str, ...] = ()) -> dict[str, Any]:
    if filename not in REGISTERED_POLICIES or Path(filename).name != filename:
        raise ValueError(f"policy is not registered: {filename}")
    if filename in stack:
        raise ValueError("policy inheritance cycle detected")
    path = POLICY_DIR / filename
    resolved = path.resolve()
    if path.is_symlink() or resolved.parent != POLICY_DIR.resolve() or not resolved.is_file():
        raise ValueError(f"registered policy file is unavailable or unsafe: {filename}")
    raw = json.loads(resolved.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError(f"registered policy must be an object: {filename}")
    unknown = sorted(set(raw) - POLICY_FIELDS - {"extends"})
    if unknown:
        raise ValueError(f"{filename} contains unknown policy fields: {', '.join(unknown)}")
    parent_name = raw.get("extends")
    if parent_name is not None:
        if not isinstance(parent_name, str):
            raise ValueError(f"{filename} extends must name a registered policy")
        parent = _load_registered_policy(parent_name, stack + (filename,))
        effective = deep_merge(parent, raw)
        validate_policy_shape(effective, filename)
        ensure_not_weaker(parent, effective, filename)
    else:
        effective = copy.deepcopy(raw)
        validate_policy_shape(effective, filename)
    expected_id = REGISTERED_POLICIES[filename]
    if effective["policy_id"] != expected_id:
        raise ValueError(f"{filename} policy_id must be {expected_id}")
    return effective


def load_registered_policy(filename: str) -> tuple[dict[str, Any], str]:
    policy = _load_registered_policy(filename)
    return policy, canonical_policy_digest(policy)


def require_mapping(value: Any, name: str, reasons: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        reasons.append(f"{name} must be an object")
        return {}
    return value


def reject_unknown(value: dict[str, Any], contract: str, label: str, reasons: list[str]) -> None:
    unknown = sorted(set(value) - FIELDS[contract])
    if unknown:
        reasons.append(f"{label} contains unknown fields: {', '.join(unknown)}")


def validate(request: dict[str, Any], policy: dict[str, Any], policy_digest: str, now: datetime) -> list[str]:
    reasons: list[str] = []
    unknown = sorted(set(request) - TOP_LEVEL)
    missing = sorted((TOP_LEVEL - {"exception"}) - set(request))
    if unknown:
        reasons.append("unknown top-level fields: " + ", ".join(unknown))
    if missing:
        reasons.append("missing top-level fields: " + ", ".join(missing))
    if request.get("schema_version") != "2.0":
        reasons.append("schema_version must be 2.0; v1 requests cannot authorize execution")
    operation_id = request.get("operation_id")
    if not isinstance(operation_id, str) or not OPERATION_ID.fullmatch(operation_id):
        reasons.append("operation_id must match ops-[A-Za-z0-9._-]{6,120}")
    if not valid_text(request.get("objective"), 8, 1000):
        reasons.append("objective must contain 8-1000 non-whitespace characters")
    if request.get("data_classification") not in DATA_CLASSES or request.get("data_classification") not in set(policy["data"]["allowed_classifications"]):
        reasons.append("data classification is not allowed by policy")

    binding = require_mapping(request.get("policy"), "policy", reasons)
    reject_unknown(binding, "policy", "policy", reasons)
    for field in FIELDS["policy"]:
        if field not in binding:
            reasons.append(f"policy.{field} is required")
    if binding.get("id") != policy["policy_id"]:
        reasons.append("policy.id does not match the selected registered policy")
    if binding.get("version") != policy["version"]:
        reasons.append("policy.version does not match the selected registered policy")
    if not isinstance(binding.get("digest"), str) or not DIGEST.fullmatch(binding.get("digest", "")):
        reasons.append("policy.digest must be sha256:<64 lowercase hex>")
    elif binding["digest"] != policy_digest:
        reasons.append("policy.digest does not match the selected registered policy semantics")

    target = require_mapping(request.get("target"), "target", reasons)
    change = require_mapping(request.get("change"), "change", reasons)
    execution = require_mapping(request.get("execution"), "execution", reasons)
    recovery = require_mapping(request.get("recovery"), "recovery", reasons)
    verification = require_mapping(request.get("verification"), "verification", reasons)
    for value, contract in ((target, "target"), (change, "change"), (execution, "execution"), (recovery, "recovery"), (verification, "verification")):
        reject_unknown(value, contract, contract, reasons)

    if not valid_text(target.get("name")):
        reasons.append("target.name is required")
    if target.get("environment") not in {"lab", "dev", "staging", "production"}:
        reasons.append("target.environment is invalid")
    if not valid_text(target.get("owner")):
        reasons.append("target.owner is required")
    if not isinstance(target.get("profile_digest"), str) or not DIGEST.fullmatch(target.get("profile_digest", "")):
        reasons.append("target.profile_digest must be sha256:<64 lowercase hex>")

    risk = change.get("risk")
    action = change.get("action")
    plan_digest = change.get("plan_digest")
    if risk not in RISK:
        reasons.append("change.risk is invalid")
    if not isinstance(action, str) or not ACTION.fullmatch(action):
        reasons.append("change.action must match [a-z0-9_-]{2,80}")
    scope = change.get("scope")
    if not isinstance(scope, list) or not scope or any(not valid_text(item) for item in scope):
        reasons.append("change.scope must be a non-empty array of non-empty strings")
    if not isinstance(plan_digest, str) or not DIGEST.fullmatch(plan_digest):
        reasons.append("change.plan_digest must be sha256:<64 lowercase hex>")
    for flag in ("stateful", "destructive", "external_side_effects"):
        if type(change.get(flag)) is not bool:
            reasons.append(f"change.{flag} must be boolean")
    if risk in RISK:
        if change.get("destructive") and risk != "R4":
            reasons.append("destructive work must be classified R4")
        if change.get("external_side_effects") and RISK_RANK[risk] < RISK_RANK["R2"]:
            reasons.append("external side effects require at least R2")
        if target.get("environment") == "production" and change.get("external_side_effects") and RISK_RANK[risk] < RISK_RANK["R3"]:
            reasons.append("production mutation requires at least R3")
        if action in set(policy["always_require_approval"]) and RISK_RANK[risk] < RISK_RANK["R3"]:
            reasons.append("this action requires at least R3")

    executor = execution.get("executor")
    if not valid_text(executor, 3):
        reasons.append("execution.executor must contain at least 3 characters")
    if not valid_text(execution.get("idempotency_key"), 8):
        reasons.append("execution.idempotency_key must contain at least 8 characters")
    lock_ref = execution.get("change_lock_ref")
    if lock_ref is not None and not valid_text(lock_ref):
        reasons.append("execution.change_lock_ref must be a non-empty string or null")
    requested_at = parse_time(execution.get("requested_at"), "execution.requested_at", reasons)
    window_start = parse_time(execution.get("window_start"), "execution.window_start", reasons)
    window_end = parse_time(execution.get("window_end"), "execution.window_end", reasons)
    if window_start and window_end:
        if window_start > window_end:
            reasons.append("execution window start must not be after window end")
        elif not window_start <= now <= window_end:
            reasons.append("current time is outside the execution window")
    if requested_at and requested_at > now:
        reasons.append("execution.requested_at is in the future")
    if risk in set(policy["require_change_lock"]) and not valid_text(lock_ref):
        reasons.append("target-scoped change lock is required")

    always = set(policy["always_require_approval"])
    minimum = policy["minimum_approvals"].get(str(risk), 0)
    if action in always or change.get("external_side_effects") is True:
        minimum = max(minimum, 1)
    approvals = request.get("approvals")
    if not isinstance(approvals, list):
        reasons.append("approvals must be an array")
        approvals = []
    valid_approvers: set[str] = set()
    valid_roles: set[str] = set()
    max_ttl = policy["approval_ttl_minutes"]
    for index, approval_value in enumerate(approvals):
        approval = require_mapping(approval_value, f"approvals[{index}]", reasons)
        reject_unknown(approval, "approval", f"approvals[{index}]", reasons)
        missing_approval = sorted(FIELDS["approval"] - set(approval))
        if missing_approval:
            reasons.append(f"approvals[{index}] missing fields: {', '.join(missing_approval)}")
        approver = approval.get("approver")
        role = approval.get("role")
        if not valid_text(approver, 3):
            reasons.append(f"approvals[{index}].approver must contain at least 3 characters")
        else:
            valid_approvers.add(approver)
        if not valid_text(role, 2):
            reasons.append(f"approvals[{index}].role must contain at least 2 characters")
        else:
            valid_roles.add(role)
        if not valid_text(approval.get("target")) or approval.get("target") != target.get("name"):
            reasons.append(f"approvals[{index}] target does not match")
        if not isinstance(approval.get("plan_digest"), str) or approval.get("plan_digest") != plan_digest:
            reasons.append(f"approvals[{index}] plan digest does not match")
        if not isinstance(approval.get("policy_digest"), str) or approval.get("policy_digest") != policy_digest:
            reasons.append(f"approvals[{index}] policy digest does not match")
        if not valid_text(approval.get("evidence_ref"), 4):
            reasons.append(f"approvals[{index}].evidence_ref must contain at least 4 characters")
        approved = parse_time(approval.get("approved_at"), f"approvals[{index}].approved_at", reasons)
        expires = parse_time(approval.get("expires_at"), f"approvals[{index}].expires_at", reasons)
        if approved and expires:
            if approved > expires:
                reasons.append(f"approvals[{index}] expires before approval")
            else:
                if not approved <= now <= expires:
                    reasons.append(f"approvals[{index}] is not currently valid")
                if (expires - approved).total_seconds() > max_ttl * 60:
                    reasons.append(f"approvals[{index}] exceeds policy TTL")
    if len(valid_approvers) < minimum:
        reasons.append(f"{minimum} distinct valid approval(s) required")
    if minimum > 1 and len(valid_roles) < 2:
        reasons.append("multi-party approval requires distinct approval roles")
    if policy["require_separation_of_duties"].get(str(risk)) and executor in valid_approvers:
        reasons.append("executor cannot approve this operation")

    required_flag = recovery.get("required")
    if type(required_flag) is not bool:
        reasons.append("recovery.required must be boolean")
    for field in ("method", "artifact_ref"):
        if recovery.get(field) is not None and not isinstance(recovery.get(field), str):
            reasons.append(f"recovery.{field} must be a string or null")
    restore_tested_at = recovery.get("restore_tested_at")
    if restore_tested_at is not None:
        parse_time(restore_tested_at, "recovery.restore_tested_at", reasons)
    for field in ("rpo_minutes", "rto_minutes"):
        value = recovery.get(field)
        if value is not None and (not is_integer(value) or value < 0):
            reasons.append(f"recovery.{field} must be a non-negative integer or null")
    needs_recovery = action in set(policy["require_recovery_evidence"]) or bool(change.get("stateful")) and (risk == "R4" or bool(change.get("destructive")))
    if needs_recovery:
        if required_flag is not True:
            reasons.append("recovery.required must be true")
        if not valid_text(recovery.get("method")) or not valid_text(recovery.get("artifact_ref")):
            reasons.append("recovery method and evidence reference are required")
        if restore_tested_at is None:
            reasons.append("recovery.restore_tested_at is required")
        if not is_integer(recovery.get("rpo_minutes")) or recovery["rpo_minutes"] < 0 or not is_integer(recovery.get("rto_minutes")) or recovery["rto_minutes"] < 0:
            reasons.append("measured non-negative RPO and RTO are required")

    criteria = verification.get("criteria")
    if not isinstance(criteria, list) or not criteria or any(not valid_text(item, 3) for item in criteria):
        reasons.append("verification.criteria must be a non-empty array of strings of at least 3 characters")
    observation = verification.get("observation_window_minutes")
    if not is_integer(observation) or observation < 0:
        reasons.append("verification.observation_window_minutes must be a non-negative integer")

    exception = request.get("exception")
    if exception is not None:
        if not policy["exceptions"]["allowed"]:
            reasons.append("policy exceptions are disabled")
        elif not isinstance(exception, dict):
            reasons.append("exception must be an object or null")
        else:
            reject_unknown(exception, "exception", "exception", reasons)
            missing_exception = sorted(FIELDS["exception"] - set(exception))
            if missing_exception:
                reasons.append("exception is missing required fields: " + ", ".join(missing_exception))
            if not valid_text(exception.get("owner"), 3):
                reasons.append("exception.owner must contain at least 3 characters")
            if not valid_text(exception.get("evidence_ref"), 4):
                reasons.append("exception.evidence_ref must contain at least 4 characters")
            if not valid_text(exception.get("rationale"), 8):
                reasons.append("exception.rationale must contain at least 8 characters")
            controls = exception.get("compensating_controls")
            minimum_controls = policy["exceptions"]["minimum_compensating_controls"]
            if not isinstance(controls, list) or len(controls) < minimum_controls or any(not valid_text(item, 3) for item in controls):
                reasons.append("exception lacks valid compensating controls")
            start = parse_time(exception.get("approved_at"), "exception.approved_at", reasons)
            end = parse_time(exception.get("expires_at"), "exception.expires_at", reasons)
            if start and end:
                if start > end:
                    reasons.append("exception expires before approval")
                else:
                    if not start <= now <= end:
                        reasons.append("exception is not currently valid")
                    if (end - start).total_seconds() > policy["exceptions"]["max_ttl_minutes"] * 60:
                        reasons.append("exception exceeds policy TTL")
    return reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, help="Secret-free JSON operation request v2.")
    parser.add_argument("--policy", default="default-policy.json", help="Registered policy basename.")
    parser.add_argument("--at", help="RFC3339 evaluation time for deterministic testing; defaults to now.")
    parser.add_argument("--print-policy-digest", action="store_true", help="Print the canonical effective policy digest.")
    args = parser.parse_args()
    try:
        policy, policy_digest = load_registered_policy(args.policy)
        if args.print_policy_digest:
            print(f"POLICY: id={policy['policy_id']} version={policy['version']} digest={policy_digest}")
            if args.request is None:
                return 0
        if args.request is None:
            raise ValueError("--request is required unless --print-policy-digest is used")
        request = json.loads(args.request.read_text(encoding="utf-8-sig"))
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object")
        time_errors: list[str] = []
        now = parse_time(args.at, "--at", time_errors) if args.at else datetime.now(timezone.utc)
        if time_errors or now is None:
            raise ValueError("; ".join(time_errors))
        reasons = validate(request, policy, policy_digest, now)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"BLOCKED: invalid request, registered policy, or evaluation time: {error}")
        return 2
    except Exception as error:
        print(f"BLOCKED: internal validation error ({type(error).__name__})")
        return 2
    if reasons:
        print("BLOCKED: " + "; ".join(dict.fromkeys(reasons)))
        return 1
    change, target = request["change"], request["target"]
    print(f"ALLOWED: {request['operation_id']} {change['risk']} {change['action']} on {target['name']} passed {policy['policy_id']} {policy_digest}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
