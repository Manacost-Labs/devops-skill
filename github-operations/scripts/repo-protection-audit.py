#!/usr/bin/env python3
"""Read-only audit of GitHub repository protection state.

Usage:
    python github-operations/scripts/repo-protection-audit.py --repo owner/name
    python github-operations/scripts/repo-protection-audit.py --from-file snapshot.json

Online mode performs GET-only ``gh api`` calls. Offline mode audits a saved
snapshot with the same shape, for air-gapped review and deterministic tests:

    {"repository": {...}, "branch_protection": {... or null},
     "rulesets": [...], "environments": {"environments": [...]}}

The script never mutates anything. Exit code 0 reports the audit; with
``--strict`` any finding exits 1.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def gh_get(path: str) -> Any | None:
    result = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def collect_online(repo: str) -> dict[str, Any]:
    repository = gh_get(f"repos/{repo}")
    if not isinstance(repository, dict):
        raise SystemExit(f"ERROR: cannot read repository {repo}; check gh auth and repository name")
    default_branch = repository.get("default_branch")
    return {
        "repository": repository,
        "branch_protection": gh_get(f"repos/{repo}/branches/{default_branch}/protection"),
        "rulesets": gh_get(f"repos/{repo}/rulesets") or [],
        "environments": gh_get(f"repos/{repo}/environments") or {"environments": []},
    }


def audit(snapshot: dict[str, Any]) -> dict[str, Any]:
    repository = snapshot.get("repository") or {}
    protection = snapshot.get("branch_protection")
    rulesets = snapshot.get("rulesets") or []
    environments = (snapshot.get("environments") or {}).get("environments") or []
    findings: list[str] = []

    default_branch = repository.get("default_branch", "unknown")
    active_rulesets = [ruleset for ruleset in rulesets if ruleset.get("enforcement") == "active"]
    if not isinstance(protection, dict) and not active_rulesets:
        findings.append(f"default branch '{default_branch}' has no classic protection and no active ruleset")
    if isinstance(protection, dict):
        if not (protection.get("enforce_admins") or {}).get("enabled"):
            findings.append("classic protection does not apply to administrators (admin bypass possible)")
        reviews = protection.get("required_pull_request_reviews")
        if not isinstance(reviews, dict):
            findings.append("classic protection does not require pull request reviews")
        checks = protection.get("required_status_checks")
        if not isinstance(checks, dict) or not (checks.get("contexts") or checks.get("checks")):
            findings.append("classic protection does not require any status checks")
        if (protection.get("allow_force_pushes") or {}).get("enabled"):
            findings.append("classic protection allows force pushes")
    for ruleset in rulesets:
        name = ruleset.get("name", "unnamed")
        if ruleset.get("enforcement") != "active":
            findings.append(f"ruleset '{name}' exists but enforcement is '{ruleset.get('enforcement')}', not active")
        bypass = ruleset.get("bypass_actors") or []
        if bypass:
            findings.append(f"ruleset '{name}' has {len(bypass)} bypass actor(s); enumerate and justify each")
    for environment in environments:
        name = environment.get("name", "unnamed")
        rules = environment.get("protection_rules") or []
        if not rules:
            findings.append(f"environment '{name}' has no protection rules (no reviewers, no wait timer)")

    return {
        "repository": repository.get("full_name", "unknown"),
        "default_branch": default_branch,
        "classic_protection_present": isinstance(protection, dict),
        "rulesets": [
            {"name": ruleset.get("name"), "enforcement": ruleset.get("enforcement"),
             "bypass_actors": len(ruleset.get("bypass_actors") or [])}
            for ruleset in rulesets
        ],
        "environments": [
            {"name": environment.get("name"), "protection_rules": len(environment.get("protection_rules") or [])}
            for environment in environments
        ],
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--repo", help="Repository as owner/name; uses GET-only gh api calls.")
    group.add_argument("--from-file", type=Path, help="Audit a saved JSON snapshot instead of the live API.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any finding is reported.")
    args = parser.parse_args()
    if args.repo and not REPO.fullmatch(args.repo):
        print("ERROR: --repo must be owner/name")
        return 2
    snapshot = json.loads(args.from_file.read_text(encoding="utf-8-sig")) if args.from_file else collect_online(args.repo)
    if not isinstance(snapshot, dict):
        print("ERROR: snapshot must be a JSON object")
        return 2
    report = audit(snapshot)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.strict and report["findings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
