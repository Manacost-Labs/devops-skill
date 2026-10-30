#!/usr/bin/env python3
"""Offline Cloudflare snapshot comparison. Never sends requests or authorizes writes."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

LIMIT = 2 * 1024 * 1024
PRODUCTS = {"access", "waf", "tunnel", "workers"}


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("non-finite number")


def digest(value):
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def inspect_tree(value, depth=0):
    if depth > 32:
        raise ValueError("too deep")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("invalid key")
            # Refuse literal credential fields; snapshots must use opaque references.
            if key.lower().replace("-", "_") in {"password", "secret", "token", "api_key", "authorization", "client_secret", "tunnel_secret"}:
                raise ValueError("credential field")
            inspect_tree(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            inspect_tree(item, depth + 1)
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise ValueError("invalid value")


def validate(data):
    if not isinstance(data, dict) or set(data) != {"schema_version", "product", "account_id", "zone_id", "objects"}:
        raise ValueError("snapshot shape")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1 or not isinstance(data["product"], str) or data["product"] not in PRODUCTS:
        raise ValueError("snapshot version/product")
    if any(not isinstance(data[field], str) or not re.fullmatch(r"[a-f0-9]{32}", data[field]) for field in ("account_id", "zone_id")):
        raise ValueError("target identity")
    if not isinstance(data["objects"], list) or not 1 <= len(data["objects"]) <= 64:
        raise ValueError("object count")
    identities = set()
    for obj in data["objects"]:
        if not isinstance(obj, dict) or set(obj) != {"resource", "id", "revision", "configuration"}:
            raise ValueError("object shape")
        for field in ("resource", "id", "revision"):
            if not isinstance(obj[field], str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", obj[field]):
                raise ValueError("object identity/revision")
        identity = (obj["resource"], obj["id"])
        if identity in identities or not isinstance(obj["configuration"], dict):
            raise ValueError("duplicate object or configuration")
        identities.add(identity)
    inspect_tree(data)
    digest(data)  # Reject non-finite values for direct callers as well as JSON input.
    return data


def load(path):
    with Path(path).open("rb") as source:
        raw = source.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("input too large")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=reject_constant)
    return validate(data)


def indexed(data):
    validate(data)
    return {(obj["resource"], obj["id"]): obj for obj in data["objects"]}


def same_scope(*snapshots):
    first = snapshots[0]
    objects = set(indexed(first))
    for data in snapshots[1:]:
        indexed(data)
        if any(data[key] != first[key] for key in ("product", "account_id", "zone_id")) or set(indexed(data)) != objects:
            raise ValueError("scope mismatch")


def fingerprint(data):
    # Object inventory order is immaterial; ordered policies/rules/ingress remain significant.
    return digest({**data, "objects": sorted(data["objects"], key=lambda obj: (obj["resource"], obj["id"]))})


def preflight(expected, current):
    same_scope(expected, current)
    match = fingerprint(expected) == fingerprint(current)
    return {"decision": "snapshot_match" if match else "blocked_drift", "expected_digest": fingerprint(expected), "current_digest": fingerprint(current), "provider_verified": False, "authorizes_write": False}


def reconcile(before, intended, current):
    same_scope(before, intended, current)
    old, desired, actual = map(indexed, (before, intended, current))
    states = []
    changed_states = []
    for identity in sorted(old):
        before_config = digest(old[identity]["configuration"])
        desired_config = digest(desired[identity]["configuration"])
        actual_config = digest(actual[identity]["configuration"])
        if before_config == desired_config:
            if actual_config != before_config:
                state = "conflict"
            else:
                state = "unchanged" if old[identity]["revision"] == actual[identity]["revision"] else "before_configuration_new_revision"
        elif actual_config == desired_config:
            state = "intended_configuration"
        elif actual_config == before_config:
            state = "before_configuration" if old[identity]["revision"] == actual[identity]["revision"] else "before_configuration_new_revision"
        else:
            state = "conflict"
        states.append({"object_digest": digest(identity), "state": state})
        if state != "unchanged":
            changed_states.append(state)
    kinds = set(changed_states)
    if not kinds:
        decision = "no_configuration_change"
    elif "conflict" in kinds or "before_configuration_new_revision" in kinds:
        decision = "blocked_conflict"
    elif len(kinds) > 1:
        decision = "partial"
    else:
        decision = next(iter(kinds))
    return {"decision": decision, "objects": states, "provider_verified": False, "authorizes_write": False, "retry_safe": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("preflight", "rollback-preflight"):
        check = sub.add_parser(command)
        check.add_argument("expected")
        check.add_argument("current")
    check = sub.add_parser("reconcile")
    check.add_argument("before")
    check.add_argument("intended")
    check.add_argument("current")
    args = parser.parse_args(argv)
    try:
        if args.command == "reconcile":
            result = reconcile(load(args.before), load(args.intended), load(args.current))
        else:
            result = preflight(load(args.expected), load(args.current))
            if args.command == "rollback-preflight" and result["decision"] == "snapshot_match":
                result["decision"] = "snapshot_match_requires_recovery_review"
        print(json.dumps(result, sort_keys=True))
        return 3 if result["decision"] in {"blocked_drift", "blocked_conflict", "partial"} else 0
    except (ValueError, TypeError, OSError, RecursionError, OverflowError):
        print('{"decision":"blocked_invalid_input","authorizes_write":false}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
