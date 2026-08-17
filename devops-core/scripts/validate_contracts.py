#!/usr/bin/env python3
"""Validate secret-free module manifests and target profiles for devops-core."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

MODULE_REQUIRED = {"name": str, "version": str, "kind": str, "capabilities": list}
PROFILE_REQUIRED = {
    "schema_version": str,
    "name": str,
    "environment": str,
    "owner": str,
    "data_classification": str,
    "services": list,
    "access": dict,
}
LITERAL_SECRET_KEYS = {"token", "password", "secret", "private_key", "private-key", "api_key", "api-key"}


def reject_literal_secrets(value: object, path: str = "") -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if str(key).lower() in LITERAL_SECRET_KEYS:
                return f"literal secret field at '{key_path}'"
            problem = reject_literal_secrets(item, key_path)
            if problem:
                return problem
    elif isinstance(value, list):
        for index, item in enumerate(value):
            problem = reject_literal_secrets(item, f"{path}[{index}]")
            if problem:
                return problem
    return None


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_contracts.py <module.yaml|target-profile.yaml>")
        return 2

    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"ERROR: File not found: {path}")
        return 2

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as error:
        print(f"ERROR: Invalid YAML: {error}")
        return 1

    if not isinstance(data, dict):
        print("ERROR: Contract must be a YAML mapping.")
        return 1

    secret_problem = reject_literal_secrets(data)
    if secret_problem:
        print(f"ERROR: Contract contains {secret_problem}. Store a reference, not a value.")
        return 1

    required = MODULE_REQUIRED if path.name == "module.yaml" else PROFILE_REQUIRED
    problems = [
        f"'{key}' must be {expected.__name__}"
        for key, expected in required.items()
        if key not in data or not isinstance(data[key], expected)
    ]
    if problems:
        print(f"ERROR: Invalid contract: {'; '.join(problems)}")
        return 1

    if path.name != "module.yaml":
        if data["schema_version"] != "2.0":
            print("ERROR: Target profile must use schema_version 2.0.")
            return 1
        if data["environment"] not in {"lab", "dev", "staging", "production"}:
            print("ERROR: Target profile environment is invalid.")
            return 1
        if data["data_classification"] not in {"public", "internal", "confidential", "restricted"}:
            print("ERROR: Target profile data_classification is invalid.")
            return 1
        invalid_refs = [key for key, value in data["access"].items() if not isinstance(value, str) or not value.startswith(("profile:", "ref:", "vault:", "oidc:", "ssh-config:"))]
        if invalid_refs:
            print(f"ERROR: Access entries must be opaque credential references: {', '.join(invalid_refs)}")
            return 1

    print(f"OK: {path} is valid and contains no literal secret fields.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
