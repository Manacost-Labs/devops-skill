#!/usr/bin/env python3
"""Bounded delegated authority. Records come only from an operator-owned external store."""
from __future__ import annotations

import hashlib
import argparse
import importlib.util
import json
import os
import re
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODES = {"safe": 1, "balanced": 2, "semi-auto": 3, "full-auto": 4}
AUTHORITY_ENV = "DEVOPS_AUTHORITY_DIR"
IDENTIFIER = re.compile(r"authority-[a-z0-9][a-z0-9-]{5,79}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
ACTION = re.compile(r"[a-z0-9_-]{2,80}")
MAX_BYTES = 65536
RECORD_FIELDS = {"schema_version", "authorization_id", "status", "mode", "policy", "target", "executor",
                 "actions", "scope", "data_classifications", "allow_stateful", "allow_external_side_effects",
                 "window_start", "window_end", "trusted_environment", "authorizations"}
APPROVAL_FIELDS = {"approver", "role", "payload_digest", "approved_at", "expires_at", "evidence_ref"}


class AuthorityError(ValueError):
    """Controlled diagnostic containing no record values or filesystem paths."""


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def payload_digest(record):
    return digest({key: value for key, value in record.items() if key != "authorizations"})


def exact(value, fields, label):
    if not isinstance(value, dict) or set(value) != fields:
        raise AuthorityError(label + " has missing or unknown fields")


def text(value, label, minimum=1, maximum=500):
    if not isinstance(value, str) or not minimum <= len(value) <= maximum or value != value.strip() or any(ord(c) < 32 for c in value):
        raise AuthorityError(label + " is invalid")
    return value


def timestamp(value, label):
    text(value, label)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise AuthorityError()
        return result.astimezone(timezone.utc)
    except ValueError:
        raise AuthorityError(label + " requires an RFC3339 timestamp with timezone") from None


def unique_list(value, label):
    if not isinstance(value, list) or not 1 <= len(value) <= 128:
        raise AuthorityError(label + " requires 1-128 exact entries")
    for item in value:
        text(item, label)
        if any(c in item for c in "*?"):
            raise AuthorityError(label + " does not accept wildcard selectors")
    if len(set(value)) != len(value):
        raise AuthorityError(label + " has duplicate entries")
    return value


def no_links(path):
    for part in (path, *path.parents):
        metadata = part.lstat()
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
            raise AuthorityError("authority path must be non-reparse and non-symlink")


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AuthorityError("duplicate authority JSON key")
        result[key] = value
    return result


def read_record(path):
    no_links(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_size > MAX_BYTES:
            raise AuthorityError("authority must be one bounded single-link regular file")
        raw = source.read(MAX_BYTES+1)
    if len(raw) > MAX_BYTES:
        raise AuthorityError("authority exceeds input limit")
    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite authority JSON")))
    if not isinstance(value, dict):
        raise AuthorityError("authority record must be an object")
    return value


def load_authorization(identifier, authority_dir=None):
    if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
        raise AuthorityError("authorization ID is invalid")
    configured = authority_dir if authority_dir is not None else os.environ.get(AUTHORITY_ENV)
    if not configured:
        raise AuthorityError("an operator-owned external authority store is required")
    path = Path(configured)
    if not path.is_absolute():
        raise AuthorityError("authority store must be absolute")
    no_links(path)
    resolved = path.resolve(strict=True)
    if not resolved.is_dir() or resolved == ROOT or ROOT in resolved.parents:
        raise AuthorityError("authority store must be outside the runtime/source tree")
    return read_record(resolved/(identifier+".json"))


def validate_record(record, policy, policy_digest, now):
    exact(record, RECORD_FIELDS, "authority record")
    if record["schema_version"] != "1.0" or record["status"] != "active":
        raise AuthorityError("authority record must be active schema 1.0")
    if not isinstance(record["authorization_id"], str) or not IDENTIFIER.fullmatch(record["authorization_id"]):
        raise AuthorityError("authorization ID is invalid")
    mode = record["mode"]
    if not isinstance(mode, str) or mode not in MODES or mode == "safe":
        raise AuthorityError("delegated authority requires balanced, semi-auto or full-auto")
    controls = policy["autonomy"]
    if MODES[mode] > MODES[controls["maximum_mode"]]:
        raise AuthorityError("selected policy does not permit this autonomy mode")
    exact(record["policy"], {"id", "version", "digest"}, "authority policy")
    if record["policy"] != {"id": policy["policy_id"], "version": policy["version"], "digest": policy_digest}:
        raise AuthorityError("authority policy binding changed")
    exact(record["target"], {"name", "environment", "owner", "profile_digest"}, "authority target")
    for field in ("name", "owner"):
        text(record["target"][field], "authority target."+field)
    if record["target"]["environment"] not in {"lab", "dev", "staging", "production"}:
        raise AuthorityError("authority environment is invalid")
    if not isinstance(record["target"]["profile_digest"], str) or not DIGEST.fullmatch(record["target"]["profile_digest"]):
        raise AuthorityError("authority target profile digest is invalid")
    if record["target"]["environment"] == "production" and not controls["allow_production"]:
        raise AuthorityError("policy forbids delegated production authority")
    text(record["executor"], "authority executor", 3)
    for field in ("actions", "scope", "data_classifications"):
        unique_list(record[field], "authority."+field)
    if any(not ACTION.fullmatch(action) for action in record["actions"]):
        raise AuthorityError("authority action is invalid")
    if not set(record["data_classifications"]) <= set(policy["data"]["allowed_classifications"]):
        raise AuthorityError("authority data classifications exceed policy")
    for field in ("allow_stateful", "allow_external_side_effects"):
        if type(record[field]) is not bool:
            raise AuthorityError("authority."+field+" must be boolean")
    start, end = timestamp(record["window_start"], "authority start"), timestamp(record["window_end"], "authority end")
    ttl = min(controls["grant_ttl_minutes"], policy["approval_ttl_minutes"])
    if not start <= now < end or (end-start).total_seconds() > ttl*60:
        raise AuthorityError("authority window is expired, not open or exceeds policy TTL")
    trust = record["trusted_environment"]
    if trust is not None:
        exact(trust, {"isolation_ref", "credential_scope_ref", "owner_evidence_ref"}, "trusted environment")
        for value in trust.values():
            text(value, "trusted environment reference", 4)
    if mode == "full-auto" and trust is None:
        raise AuthorityError("full-auto requires explicit isolation, credential and owner evidence")
    approvals = record["authorizations"]
    if not isinstance(approvals, list) or not 1 <= len(approvals) <= 16:
        raise AuthorityError("authority requires attributable authorizations")
    actors, roles = set(), set()
    binding = payload_digest(record)
    for approval in approvals:
        exact(approval, APPROVAL_FIELDS, "authority authorization")
        actor = text(approval["approver"], "authority approver", 3)
        role = text(approval["role"], "authority approver role", 2)
        if actor.casefold() == record["executor"].casefold():
            raise AuthorityError("executor cannot issue its own delegated authority")
        if approval["payload_digest"] != binding:
            raise AuthorityError("authority authorization payload binding changed")
        text(approval["evidence_ref"], "authority approval evidence", 4)
        approved, expires = timestamp(approval["approved_at"], "authority approved"), timestamp(approval["expires_at"], "authority expires")
        if not approved <= start <= now < end <= expires or (expires-approved).total_seconds() > ttl*60:
            raise AuthorityError("authority authorization is stale or does not cover its window")
        actors.add(actor.casefold()); roles.add(role.casefold())
    minimum = max(1, policy["minimum_approvals"]["R"+str(MODES[mode])])
    if len(actors) < minimum or (minimum > 1 and len(roles) < 2):
        raise AuthorityError("authority lacks required independent authorizers/roles")


def assess(request, policy, policy_digest, now, authority_dir=None):
    """Return delegated eligibility/manual-boundary flag/reasons. No ambient mode upgrades."""
    if "autonomy" not in request:
        return False, False, []
    selection = request["autonomy"]
    try:
        exact(selection, {"mode", "authorization_id", "authorization_digest"}, "autonomy selection")
        mode = selection["mode"]
        if not isinstance(mode, str) or mode not in MODES:
            raise AuthorityError("unknown autonomy mode")
        if mode == "safe":
            if selection["authorization_id"] is not None or selection["authorization_digest"] is not None:
                raise AuthorityError("safe mode does not consume delegated authority")
            return False, False, []
        record = load_authorization(selection["authorization_id"], authority_dir)
        if selection["authorization_digest"] != digest(record):
            raise AuthorityError("authority record digest changed or was revoked")
        validate_record(record, policy, policy_digest, now)
        if record["authorization_id"] != selection["authorization_id"] or record["mode"] != mode:
            raise AuthorityError("authority ID or selected mode does not match")
        if record["target"] != request.get("target"):
            raise AuthorityError("authority target/owner/profile/environment does not match")
        execution, change = request.get("execution"), request.get("change")
        if not isinstance(execution, dict) or execution.get("executor") != record["executor"]:
            raise AuthorityError("authority executor does not match")
        if not isinstance(change, dict) or change.get("risk") not in {"R0", "R1", "R2", "R3", "R4"}:
            raise AuthorityError("authority operation risk is invalid")
        if type(change.get("irreversible")) is not bool:
            raise AuthorityError("delegated modes require explicit irreversible classification")
        start, end = timestamp(execution.get("window_start"), "operation start"), timestamp(execution.get("window_end"), "operation end")
        if start < timestamp(record["window_start"], "authority start") or end > timestamp(record["window_end"], "authority end"):
            raise AuthorityError("operation window exceeds delegated authority")
        scope = change.get("scope")
        if not isinstance(scope, list) or any(not isinstance(item, str) for item in scope):
            raise AuthorityError("operation scope is invalid")
        covered = (int(change["risk"][1]) <= MODES[mode] and change.get("action") in record["actions"]
                   and set(scope) <= set(record["scope"]) and request.get("data_classification") in record["data_classifications"]
                   and (not change.get("stateful") or record["allow_stateful"])
                   and (not change.get("external_side_effects") or record["allow_external_side_effects"])
                   and change.get("destructive") is False and change["irreversible"] is False and request.get("exception") is None)
        return covered, not covered, []
    except AuthorityError as error:
        return False, False, [str(error)]
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        # Never echo record contents, path details or target exception text.
        return False, False, ["delegated authority invalid, unavailable, expired or outside trusted binding"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--draft-from", type=Path, help="Prepare unapproved authority from a v2 operation.")
    group.add_argument("--digests", type=Path, help="Print hashes only; never grants authority.")
    parser.add_argument("--mode", choices=list(MODES))
    parser.add_argument("--authorization-id")
    parser.add_argument("--policy", default="default-policy.json")
    parser.add_argument("--window-minutes", type=int, default=60)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.digests:
            record = read_record(args.digests.absolute())
            print("PAYLOAD: " + payload_digest(record))
            print("RECORD: " + digest(record))
            print("Hashes do not establish authorization or identity.")
            return 0
        if args.mode not in MODES or args.mode == "safe" or not IDENTIFIER.fullmatch(args.authorization_id or ""):
            raise AuthorityError("a delegated mode and valid authorization ID are required")
        if args.output is None or args.output.exists():
            raise AuthorityError("a new draft output path is required")
        if os.environ.get(AUTHORITY_ENV):
            store = Path(os.environ[AUTHORITY_ENV]).resolve()
            output = args.output.resolve()
            if output == store or store in output.parents:
                raise AuthorityError("drafts must not be written into the active authority store")
        spec = importlib.util.spec_from_file_location("authority_preparation_gate", Path(__file__).with_name("operation_gate.py"))
        gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
        policy, policy_digest = gate.load_registered_policy(args.policy)
        if MODES[args.mode] > MODES[policy["autonomy"]["maximum_mode"]]:
            raise AuthorityError("policy forbids this autonomy mode")
        if not 1 <= args.window_minutes <= min(policy["approval_ttl_minutes"], policy["autonomy"]["grant_ttl_minutes"]):
            raise AuthorityError("draft window exceeds policy")
        request = read_record(args.draft_from.absolute())
        if request.get("schema_version") != "2.0" or request.get("policy") != {"id": policy["policy_id"], "version": policy["version"], "digest": policy_digest}:
            raise AuthorityError("operation policy/schema binding is invalid")
        target, execution, change = request["target"], request["execution"], request["change"]
        exact(target, {"name", "environment", "owner", "profile_digest"}, "target")
        now = datetime.now(timezone.utc)
        record = {"schema_version": "1.0", "authorization_id": args.authorization_id, "status": "draft",
                  "mode": args.mode, "policy": request["policy"], "target": target, "executor": execution["executor"],
                  "actions": [change["action"]], "scope": list(change["scope"]),
                  "data_classifications": [request["data_classification"]], "allow_stateful": change["stateful"],
                  "allow_external_side_effects": change["external_side_effects"],
                  "window_start": now.isoformat(), "window_end": (now+timedelta(minutes=args.window_minutes)).isoformat(),
                  "trusted_environment": None if args.mode != "full-auto" else {"isolation_ref": "", "credential_scope_ref": "", "owner_evidence_ref": ""},
                  "authorizations": []}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(record, stream, indent=2); stream.write("\n")
        print("WROTE: unapproved draft. Operator review and external protected-store issuance are required once.")
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print("BLOCKED: invalid authority preparation input; no authority was issued")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
