#!/usr/bin/env python3
"""Append or verify canonical JSON operation records linked by SHA-256."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

GENESIS = "sha256:" + "0" * 64
FORBIDDEN_KEYS = {"token", "password", "secret", "private_key", "private-key", "api_key", "api-key", "authorization", "cookie"}
REQUIRED = {"schema_version", "operation_id", "policy_id", "target", "target_profile_digest", "environment", "risk", "plan_digest", "modules", "actor", "approval_refs", "changes", "verification", "rollback", "status", "started_at", "finished_at"}
STATUSES = {"verified", "partially_verified", "rolled_back", "blocked"}


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def secret_path(value: Any, path: str = "") -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            current = f"{path}.{key}" if path else str(key)
            if str(key).lower() in FORBIDDEN_KEYS:
                return current
            found = secret_path(item, current)
            if found: return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = secret_path(item, f"{path}[{index}]")
            if found: return found
    return None


def record_hash(record: dict[str, Any]) -> str:
    payload = {key: value for key, value in record.items() if key != "record_hash"}
    return "sha256:" + hashlib.sha256(canonical(payload)).hexdigest()


def validate_record(record: dict[str, Any]) -> None:
    missing = REQUIRED - set(record)
    if missing: raise ValueError("record missing required fields: " + ", ".join(sorted(missing)))
    if record.get("schema_version") != "2.0": raise ValueError("record schema_version must be 2.0")
    if record.get("status") not in STATUSES: raise ValueError("record status is invalid")
    for field in ("target_profile_digest", "plan_digest"):
        value = record.get(field)
        if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
            raise ValueError(f"record {field} must be a SHA-256 digest")


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists(): return []
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip(): continue
        value = json.loads(line)
        if not isinstance(value, dict): raise ValueError(f"line {line_number} is not an object")
        records.append(value)
    return records


def verify(records: list[dict[str, Any]]) -> str:
    previous = GENESIS
    seen: set[str] = set()
    for index, record in enumerate(records, 1):
        operation_id = record.get("operation_id")
        if not operation_id or operation_id in seen: raise ValueError(f"record {index} has missing or duplicate operation_id")
        validate_record(record)
        if record.get("previous_hash") != previous: raise ValueError(f"record {index} previous_hash mismatch")
        actual = record_hash(record)
        if record.get("record_hash") != actual: raise ValueError(f"record {index} hash mismatch")
        if secret_path(record): raise ValueError(f"record {index} contains forbidden sensitive field {secret_path(record)}")
        seen.add(str(operation_id))
        previous = actual
    return previous


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("verify")
    check.add_argument("ledger", type=Path)
    append = sub.add_parser("append")
    append.add_argument("ledger", type=Path)
    append.add_argument("record", type=Path, help="Secret-free JSON operation record without chain fields.")
    args = parser.parse_args()
    try:
        records = read_records(args.ledger)
        tip = verify(records)
        if args.command == "verify":
            print(f"OK: {len(records)} ledger record(s); tip={tip}")
            return 0
        incoming = json.loads(args.record.read_text(encoding="utf-8-sig"))
        if not isinstance(incoming, dict): raise ValueError("record must be a JSON object")
        if "previous_hash" in incoming or "record_hash" in incoming: raise ValueError("input record must not set chain fields")
        validate_record(incoming)
        if secret_path(incoming): raise ValueError(f"record contains forbidden sensitive field {secret_path(incoming)}")
        incoming["previous_hash"] = tip
        incoming["record_hash"] = record_hash(incoming)
        verify(records + [incoming])
        args.ledger.parent.mkdir(parents=True, exist_ok=True)
        with args.ledger.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(canonical(incoming).decode("utf-8") + "\n")
        print(f"OK: appended {incoming.get('operation_id')} hash={incoming['record_hash']}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
