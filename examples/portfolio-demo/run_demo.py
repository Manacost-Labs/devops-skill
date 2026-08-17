#!/usr/bin/env python3
"""Run a deterministic, local-only DevOps change-control portfolio demo."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


DEMO_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEMO_DIR.parents[1]
FIXTURES = DEMO_DIR / "fixtures"
GATE = REPO_ROOT / "devops-platform-contracts" / "scripts" / "operation_gate.py"
CONTRACT_VALIDATOR = REPO_ROOT / "devops-core" / "scripts" / "validate_contracts.py"
POLICY_DIGEST_RE = re.compile(r"digest=(sha256:[0-9a-f]{64})")
PLAIN_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
AT = "2026-08-17T10:15:00Z"


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def run_checked(arguments: list[str], expected_returncode: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(arguments, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if result.returncode != expected_returncode:
        detail = (result.stdout + result.stderr).strip()
        raise RuntimeError(f"unexpected exit {result.returncode} for {arguments!r}: {detail}")
    return result


def profile_digest(path: Path) -> str:
    tool = REPO_ROOT / "devops-core" / "scripts" / "profile_digest.py"
    result = run_checked([sys.executable, str(tool), str(path)])
    value = result.stdout.strip()
    if PLAIN_DIGEST_RE.fullmatch(value) is None:
        raise RuntimeError("profile digest tool returned an invalid digest")
    return value


def policy_digest() -> str:
    result = run_checked([sys.executable, str(GATE), "--policy", "default-policy.json", "--print-policy-digest"])
    match = POLICY_DIGEST_RE.search(result.stdout)
    if match is None:
        raise RuntimeError("operation gate did not return a policy digest")
    return match.group(1)


def make_request(plan_digest: str, target_digest: str, selected_policy_digest: str) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "operation_id": "ops-portfolio-demo-0001",
        "objective": "Exercise exact approval binding for a synthetic lab rollout",
        "data_classification": "public",
        "policy": {"id": "default-baseline", "version": "2.0", "digest": selected_policy_digest},
        "target": {
            "name": "portfolio-demo-lab",
            "environment": "lab",
            "owner": "portfolio-demo-owner",
            "profile_digest": target_digest,
        },
        "change": {
            "action": "container_rollout",
            "risk": "R2",
            "scope": ["service:demo-web"],
            "plan_digest": plan_digest,
            "stateful": False,
            "destructive": False,
            "external_side_effects": True,
        },
        "execution": {
            "executor": "service:portfolio-demo-simulator",
            "requested_at": "2026-08-17T10:00:00Z",
            "window_start": "2026-08-17T10:00:00Z",
            "window_end": "2026-08-17T11:00:00Z",
            "idempotency_key": "portfolio-demo-lab-0001",
            "change_lock_ref": None,
        },
        "approvals": [
            {
                "approver": "fixture:service-owner",
                "role": "service-owner",
                "target": "portfolio-demo-lab",
                "plan_digest": plan_digest,
                "policy_digest": selected_policy_digest,
                "approved_at": "2026-08-17T10:05:00Z",
                "expires_at": "2026-08-17T11:00:00Z",
                "evidence_ref": "fixture:approval-record-0001",
            }
        ],
        "recovery": {
            "required": False,
            "method": "restore the temporary pre-change JSON state",
            "artifact_ref": "fixture:pre-change-state",
            "restore_tested_at": None,
            "rpo_minutes": None,
            "rto_minutes": 1,
        },
        "verification": {
            "criteria": ["release identifier matches the plan", "synthetic health state is healthy"],
            "observation_window_minutes": 0,
        },
        "exception": None,
    }


def gate_request(request: dict[str, Any], directory: Path, name: str) -> subprocess.CompletedProcess[str]:
    request_path = directory / name
    request_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(GATE), "--request", str(request_path), "--policy", "default-policy.json", "--at", AT],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def write_evidence(path: Path, evidence: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite existing evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_demo(output: Path | None) -> dict[str, Any]:
    audit = read_json(FIXTURES / "audit.json")
    plan = read_json(FIXTURES / "plan.json")
    profile_path = FIXTURES / "target-profile.yaml"

    if plan.get("simulation_only") is not True:
        raise RuntimeError("refusing to run a plan that is not explicitly simulation-only")
    if set(plan.get("prohibited_capabilities", [])) != {"cloud-api", "container-runtime", "dns", "network", "production-executor", "ssh"}:
        raise RuntimeError("simulation safety boundary is incomplete")
    if audit.get("source") != "synthetic-fixture" or audit.get("target") != plan.get("target"):
        raise RuntimeError("audit is not a matching synthetic fixture")

    contract = run_checked([sys.executable, str(CONTRACT_VALIDATOR), str(profile_path)])
    selected_policy_digest = policy_digest()
    selected_plan_digest = canonical_digest(plan)
    selected_profile_digest = profile_digest(profile_path)
    request = make_request(selected_plan_digest, selected_profile_digest, selected_policy_digest)

    with tempfile.TemporaryDirectory(prefix="devops-portfolio-demo-") as temporary:
        workspace = Path(temporary)

        mismatched = copy.deepcopy(request)
        mismatched["approvals"][0]["plan_digest"] = "sha256:" + "0" * 64
        blocked = gate_request(mismatched, workspace, "request-mismatched.json")
        if (
            blocked.returncode == 0
            or not blocked.stdout.startswith("BLOCKED:")
            or "plan digest does not match" not in blocked.stdout
        ):
            raise RuntimeError("gate failed to reject an approval with a mismatched plan digest")

        allowed = gate_request(request, workspace, "request-exact.json")
        if allowed.returncode != 0 or not allowed.stdout.startswith("ALLOWED:"):
            raise RuntimeError("gate rejected the exact synthetic approval: " + (allowed.stdout + allowed.stderr).strip())

        before = {
            "release": audit["observed_release"],
            "health": audit["health"],
            "target": audit["target"],
        }
        state_path = workspace / "simulated-state.json"
        state_path.write_text(json.dumps(before, sort_keys=True), encoding="utf-8")

        after = dict(before)
        after["release"] = plan["desired_release"]
        state_path.write_text(json.dumps(after, sort_keys=True), encoding="utf-8")
        observed = read_json(state_path)
        verified = observed["release"] == plan["desired_release"] and observed["health"] == "healthy"
        if not verified:
            raise RuntimeError("simulated post-change verification failed")

        drill_state = dict(observed)
        drill_state["health"] = "unhealthy"
        state_path.write_text(json.dumps(drill_state, sort_keys=True), encoding="utf-8")
        rollback_triggered = read_json(state_path)["health"] != "healthy"
        if not rollback_triggered:
            raise RuntimeError("rollback drill did not detect the injected verification failure")
        state_path.write_text(json.dumps(before, sort_keys=True), encoding="utf-8")
        rollback_verified = read_json(state_path) == before
        if not rollback_verified:
            raise RuntimeError("rollback drill failed to restore the pre-change state")

        evidence = {
            "operation_id": request["operation_id"],
            "status": "verified",
            "mode": "local-simulation-only",
            "live_target_contacted": False,
            "audit": {"source": audit["source"], "digest": canonical_digest(audit), "trust_level": audit["trust_level"]},
            "plan_digest": selected_plan_digest,
            "target_profile_digest": selected_profile_digest,
            "policy_digest": selected_policy_digest,
            "contract_validation": contract.stdout.strip(),
            "approval_negative_test": blocked.stdout.strip(),
            "approval_exact_test": allowed.stdout.strip(),
            "execution": {"simulated": True, "temporary_state_only": True},
            "verification": {"post_change": verified, "rollback_triggered": rollback_triggered, "rollback_verified": rollback_verified},
            "redaction_status": "no-sensitive-input",
        }

    if output is not None:
        write_evidence(output, evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional path for the synthetic evidence JSON.")
    args = parser.parse_args()
    try:
        evidence = run_demo(args.output)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"DEMO BLOCKED: {error}")
        return 1

    print("AUDIT: synthetic fixture accepted as untrusted data")
    print(f"PLAN: {evidence['plan_digest']}")
    print("GATE NEGATIVE: mismatched approval blocked")
    print("GATE EXACT: exact target, plan, policy, and time-bound approval allowed")
    print("EXECUTION: simulated in a temporary local state file")
    print("VERIFY: desired release and synthetic health verified")
    print("ROLLBACK DRILL: injected failure detected and pre-change state restored")
    print("RESULT: verified (simulation only; no live target contacted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
