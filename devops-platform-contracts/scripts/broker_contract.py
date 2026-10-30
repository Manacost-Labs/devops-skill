"""Strict typed execution and Ed25519 admission; no caller-provided argv/risk."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import re
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ROOT = Path(__file__).resolve().parents[2]
MODES = {"safe": 1, "balanced": 2, "semi-auto": 3, "full-auto": 4}
IDENTIFIER = re.compile(r"[a-z][a-z0-9-]{5,79}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
DOMAIN = b"devops-broker-admission-v1\x00"
MAX_INPUT = 1024 * 1024


class Denied(ValueError):
    """Controlled refusal; never include untrusted values or credentials."""


def exact(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise Denied("invalid or unknown contract fields")


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise Denied("duplicate JSON field")
        result[key] = value
    return result


def decode(raw):
    if len(raw) > MAX_INPUT:
        raise Denied("input exceeds limit")
    try:
        result = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(Denied("nonfinite JSON")))
        canonical(result)  # Bound nesting and reject unsupported values too.
        return result
    except (ValueError, UnicodeError, RecursionError) as error:
        raise Denied("invalid JSON contract") from error


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def digest(value):
    return "sha256:" + hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def stamp(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        raise Denied("invalid authorization time") from None


def text(value, limit=256):
    if not isinstance(value, str) or not 1 <= len(value) <= limit or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise Denied("invalid bounded text")
    return value


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise Denied("invalid identifier")
    return value


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


GATE = load_module("broker_consistency_gate", "devops-platform-contracts/scripts/operation_gate.py")


def read_record(path):
    # Reuse bounded descriptor reads and POSIX/reparse/hardlink checks.
    try:
        return GATE.AUTONOMY.read_record(Path(path).absolute())
    except (OSError, ValueError, RecursionError):
        raise Denied("record unavailable, unsafe or malformed") from None


def validate_registry(registry):
    exact(registry, {"schema_version", "server_id", "policy", "policy_digest", "keys", "clients", "targets", "tasks"})
    if registry["schema_version"] != "1.0":
        raise Denied("unsupported registry version")
    identifier(registry["server_id"])
    policy, policy_digest = GATE.load_registered_policy(registry["policy"])
    if registry["policy_digest"] != policy_digest:
        raise Denied("registered policy semantics changed")
    if not isinstance(registry["keys"], dict) or not 1 <= len(registry["keys"]) <= 16:
        raise Denied("trusted keys required")
    fingerprints, actors = set(), set()
    if not isinstance(registry["clients"], dict) or not 1 <= len(registry["clients"]) <= 128:
        raise Denied("registered client identities required")
    principal_epochs = {}
    for subject, client in registry["clients"].items():
        if not DIGEST.fullmatch(subject):
            raise Denied("client certificate fingerprint required")
        exact(client, {"principal", "epoch"})
        identifier(client["principal"])
        if not re.fullmatch(r"[0-9a-f]{64}", client["epoch"]):
            raise Denied("random authority epoch required")
        if client["principal"] in principal_epochs and principal_epochs[client["principal"]] != client["epoch"]:
            raise Denied("one principal must have one initial epoch across client certificates")
        principal_epochs[client["principal"]] = client["epoch"]
    for key_id, key in registry["keys"].items():
        identifier(key_id)
        exact(key, {"public_key", "actor", "role", "target_ids", "maximum_mode", "maximum_risk"})
        if (not isinstance(key["target_ids"], list) or not key["target_ids"] or len(set(key["target_ids"])) != len(key["target_ids"])
                or any(target_id not in registry["targets"] for target_id in key["target_ids"])
                or key["maximum_mode"] not in MODES or key["maximum_risk"] not in policy["risk_classes"]):
            raise Denied("trusted signer scope required")
        raw = base64.b64decode(key["public_key"], validate=True)
        Ed25519PublicKey.from_public_bytes(raw)
        actor = text(key["actor"]).casefold()
        text(key["role"])
        if raw in fingerprints or actor in actors or actor == "service:protected-broker":
            raise Denied("trusted signer identities must be distinct")
        fingerprints.add(raw); actors.add(actor)
    if not isinstance(registry["targets"], dict) or not 1 <= len(registry["targets"]) <= 128 or not isinstance(registry["tasks"], dict) or not 1 <= len(registry["tasks"]) <= 128:
        raise Denied("registered targets and tasks required")
    for target_id, target in registry["targets"].items():
        identifier(target_id)
        exact(target, {"name", "environment", "owner", "profile_digest", "resource"})
        for field in ("name", "owner"):
            text(target[field])
        if target["environment"] not in {"lab", "dev", "staging", "production"} or not DIGEST.fullmatch(target["profile_digest"]):
            raise Denied("invalid registered target")
        if not isinstance(target["resource"], dict) or len(canonical(target["resource"])) > 16384:
            raise Denied("invalid registered resource binding")
    worker_targets = {"worker_uid": {}, "worker_gid": {}}
    for task_id, task in registry["tasks"].items():
        identifier(task_id)
        fields = {"target_id", "action", "risk", "scope", "stateful", "destructive", "irreversible", "external_side_effects", "data_classification", "executable", "argv", "bundle", "parameters", "result_schema", "timeout_seconds", "recovery", "verification", "worker_uid", "worker_gid"}
        exact(task, fields | ({"worker_input"} if "worker_input" in task else set()))
        if not isinstance(task.get("worker_input", "legacy-v1"), str) or task.get("worker_input", "legacy-v1") not in {"legacy-v1", "context-v2"}:
            raise Denied("unsupported worker input protocol")
        if any(type(task[field]) is not int or not 1 <= task[field] <= 2147483647 for field in ("worker_uid", "worker_gid")):
            raise Denied("unprivileged worker identity required")
        for field in worker_targets:
            if task[field] in worker_targets[field] and worker_targets[field][task[field]] != task["target_id"]:
                raise Denied("worker identities cannot span target trust domains")
            worker_targets[field][task[field]] = task["target_id"]
        if task["target_id"] not in registry["targets"] or task["risk"] not in policy["risk_classes"]:
            raise Denied("unknown task target or risk")
        text(task["action"])
        if not isinstance(task["scope"], list) or not 1 <= len(task["scope"]) <= 32 or len(set(task["scope"])) != len(task["scope"]):
            raise Denied("invalid task scope")
        for scope in task["scope"]:
            text(scope)
        for field in ("stateful", "destructive", "irreversible", "external_side_effects"):
            if type(task[field]) is not bool:
                raise Denied("task effects must be booleans")
        exact(task["executable"], {"path", "digest"})
        if not Path(task["executable"]["path"]).is_absolute() or not DIGEST.fullmatch(task["executable"]["digest"]):
            raise Denied("fixed executable identity required")
        if not isinstance(task["argv"], list) or len(task["argv"]) > 64:
            raise Denied("fixed task arguments required")
        for argument in task["argv"]:
            text(argument, 2048)
        if not isinstance(task["bundle"], dict) or not 1 <= len(task["bundle"]) <= 128:
            raise Denied("bounded immutable task bundle required")
        for filename, binding in task["bundle"].items():
            if not re.fullmatch(r"[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*\.[a-zA-Z0-9]+", filename) or not DIGEST.fullmatch(binding):
                raise Denied("invalid bundle path or digest")
        if type(task["timeout_seconds"]) is not int or not 1 <= task["timeout_seconds"] <= 300:
            raise Denied("invalid task timeout")
        validate_parameters(task["parameters"], None)
        validate_parameters(task["result_schema"], None)
    return policy, policy_digest


def validate_parameters(schema, values):
    if not isinstance(schema, dict) or len(schema) > 32:
        raise Denied("invalid parameter schema")
    if values is not None:
        exact(values, schema)
    for name, rule in schema.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", name):
            raise Denied("invalid parameter name")
        if rule == {"type": "digest"}:
            if values is not None and (not isinstance(values[name], str) or not DIGEST.fullmatch(values[name])):
                raise Denied("immutable digest parameter required")
            continue
        if isinstance(rule, dict) and rule.get("type") == "integer":
            exact(rule, {"type", "minimum", "maximum"})
            if type(rule["minimum"]) is not int or type(rule["maximum"]) is not int or not -(2**53) < rule["minimum"] <= rule["maximum"] < 2**53:
                raise Denied("invalid integer bounds")
            if values is not None and (type(values[name]) is not int or not rule["minimum"] <= values[name] <= rule["maximum"]):
                raise Denied("integer parameter outside bounds")
            continue
        # Finite choices and opaque digests deliberately exclude free commands,
        # arbitrary paths, environment values or unreviewed structured payloads.
        exact(rule, {"enum"})
        choices = rule["enum"]
        if not isinstance(choices, list) or not 1 <= len(choices) <= 128 or any(type(item) not in {str, int, bool} for item in choices):
            raise Denied("parameters require finite reviewed choices")
        if any(isinstance(item, str) and (not item or len(item) > 256) for item in choices):
            raise Denied("invalid parameter choice")
        if values is not None and not any(type(values[name]) is type(choice) and values[name] == choice for choice in choices):
            raise Denied("parameter outside registered choices")


def worker_input(registry, call, assessed):
    """Authoritative task input after admission; never copied from parameters.

    Legacy task bytes are preserved. Opt-in changes the signed registry digest,
    so an existing grant cannot silently acquire the new input contract.
    """
    if assessed["preparation_only"]:
        raise Denied("a planning result cannot become worker admission")
    task = assessed["task"]
    value = {"parameters": call["parameters"], "target": registry["targets"][task["target_id"]]["resource"]}
    if task.get("worker_input", "legacy-v1") == "context-v2":
        execution = assessed["request"]["execution"]
        value.update(schema_version="2.0", context={
            "operation_id": call["operation_id"], "task_id": call["task_id"], "target_id": task["target_id"],
            "call_digest": assessed["call_digest"], "grant_digest": assessed["grant_digest"],
            "registry_digest": assessed["registry_digest"], "epoch": assessed["current_epoch"],
            "not_before": execution["window_start"], "expires": execution["window_end"],
            "parameters_digest": digest(call["parameters"]), "target_digest": digest(value["target"]),
        })
    return canonical(value)


def verified(envelope, registry, now, *, kind, fields):
    exact(envelope, set(fields) | {"signatures"})
    payload = {key: value for key, value in envelope.items() if key != "signatures"}
    if payload["schema_version"] != "1.0" or payload["kind"] != kind or payload["audience"] != registry["server_id"] or payload["registry_digest"] != digest(registry):
        raise Denied("authorization context changed")
    identifier(payload["id"])
    start, end = stamp(payload["not_before"]), stamp(payload["expires"])
    policy, _ = GATE.load_registered_policy(registry["policy"])
    if not start <= now < end or (end - start).total_seconds() > min(policy["approval_ttl_minutes"], policy["autonomy"]["grant_ttl_minutes"]) * 60:
        raise Denied("authorization expired or outside permitted window")
    signatures = envelope["signatures"]
    if not isinstance(signatures, list) or not 1 <= len(signatures) <= 16:
        raise Denied("independent signature required")
    signers = {}
    for signature in signatures:
        exact(signature, {"key_id", "signature"})
        key_id = signature["key_id"]
        if key_id not in registry["keys"] or key_id in signers:
            raise Denied("unknown or duplicate signer")
        key = registry["keys"][key_id]
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(key["public_key"], validate=True)).verify(base64.b64decode(signature["signature"], validate=True), DOMAIN + canonical(payload))
        except Exception:
            raise Denied("authorization signature invalid") from None
        signers[key_id] = key
    return payload, signers


GRANT_FIELDS = {"schema_version", "kind", "id", "audience", "registry_digest", "not_before", "expires", "subject", "epoch", "mode", "task_ids", "max_operations", "trusted_environment"}
ADMISSION_FIELDS = {"schema_version", "kind", "id", "audience", "registry_digest", "not_before", "expires", "grant_digest", "call_digest"}


def validate_grant(envelope, registry, now, subject):
    policy, _ = validate_registry(registry)
    grant_body, grant_signers = verified(envelope, registry, now, kind="grant", fields=GRANT_FIELDS)
    if subject not in registry["clients"] or grant_body["subject"] != subject or not re.fullmatch(r"[0-9a-f]{64}", grant_body["epoch"]):
        raise Denied("grant does not bind authenticated client identity")
    mode = grant_body["mode"]
    if type(grant_body["max_operations"]) is not int or not 1 <= grant_body["max_operations"] <= 1024:
        raise Denied("finite operation budget required")
    if mode not in MODES or MODES[mode] > MODES[policy["autonomy"]["maximum_mode"]]:
        raise Denied("mode exceeds protected policy")
    tasks = grant_body["task_ids"]
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 128 or len(set(tasks)) != len(tasks) or any(item not in registry["tasks"] for item in tasks):
        raise Denied("invalid granted task set")
    for key in grant_signers.values():
        if MODES[grant_body["mode"]] > MODES[key["maximum_mode"]] or any(registry["tasks"][task_id]["target_id"] not in key["target_ids"] or int(registry["tasks"][task_id]["risk"][1]) > int(key["maximum_risk"][1]) for task_id in tasks):
            raise Denied("grant exceeds signer authority")
    if mode == "full-auto":
        exact(grant_body["trusted_environment"], {"isolation_ref", "credential_scope_ref", "owner_evidence_ref"})
        for value in grant_body["trusted_environment"].values():
            text(value)
    elif grant_body["trusted_environment"] is not None:
        raise Denied("unexpected trust declaration")
    return grant_body, grant_signers


def assess(call, grant, admission, registry, now, subject, epoch, ceiling="safe", *, preparation=False):
    policy, policy_digest = validate_registry(registry)
    exact(call, {"schema_version", "operation_id", "task_id", "parameters"})
    if call["schema_version"] != "1.0":
        raise Denied("unsupported call version")
    identifier(call["operation_id"])
    if not re.fullmatch(r"ops-[a-z0-9-]{6,76}", call["operation_id"]):
        raise Denied("invalid operation identifier")
    grant_body, grant_signers = validate_grant(grant, registry, now, subject)
    mode = grant_body["mode"]
    if call["task_id"] not in grant_body["task_ids"]:
        raise Denied("task outside issued scope")
    stale_epoch = grant_body["epoch"] != epoch
    if stale_epoch:
        if ceiling not in MODES:
            raise Denied("invalid persisted ceiling")
        mode = min((mode, ceiling), key=MODES.get)
    task = registry["tasks"][call["task_id"]]
    validate_parameters(task["parameters"], call["parameters"])
    call_digest = digest({"call": call, "grant_digest": digest(grant_body), "registry_digest": digest(registry), "epoch": epoch})
    production = registry["targets"][task["target_id"]]["environment"] == "production"
    exact_required = (int(task["risk"][1]) > MODES[mode] or task["destructive"] or task["irreversible"]
                      or production and task["external_side_effects"] and not policy["autonomy"]["allow_production"])
    if stale_epoch and exact_required and not preparation:
        raise Denied("restriction cancelled prior higher-risk authority; fresh epoch grant required")
    signers, authority = grant_signers, grant_body
    pending = exact_required and admission is None and preparation
    if exact_required and not pending:
        authority, signers = verified(admission, registry, now, kind="admission", fields=ADMISSION_FIELDS)
        if authority["grant_digest"] != digest(grant_body) or authority["call_digest"] != call_digest:
            raise Denied("exact admission does not bind this call")
    elif admission is not None:
        raise Denied("unexpected exact admission")
    for key in signers.values():
        if task["target_id"] not in key["target_ids"] or int(task["risk"][1]) > int(key["maximum_risk"][1]):
            raise Denied("exact admission exceeds signer authority")
    minimum = max(1, policy["minimum_approvals"][task["risk"]])
    if not preparation and (len(signers) < minimum or minimum > 1 and len({key["role"] for key in signers.values()}) < 2):
        raise Denied("insufficient independent signers")
    target = {key: value for key, value in registry["targets"][task["target_id"]].items() if key != "resource"}
    start = max(stamp(grant_body["not_before"]), stamp(authority["not_before"]))
    end = min(stamp(grant_body["expires"]), stamp(authority["expires"]))
    request = {
        "schema_version": "2.0", "operation_id": call["operation_id"], "objective": "Execute registered immutable task",
        "data_classification": task["data_classification"], "policy": {"id": policy["policy_id"], "version": policy["version"], "digest": policy_digest},
        "target": target, "change": {key: task[key] for key in ("action", "risk", "scope", "stateful", "destructive", "irreversible", "external_side_effects")},
        "execution": {"executor": "service:protected-broker", "requested_at": now.isoformat(), "window_start": start.isoformat(), "window_end": end.isoformat(), "idempotency_key": call["operation_id"], "change_lock_ref": "broker:exclusive-target-lock"},
        "approvals": [], "recovery": task["recovery"], "verification": task["verification"], "exception": None,
    }
    request["change"]["plan_digest"] = call_digest
    operation_digest = GATE.operation_digest(request)
    # These are consistency inputs derived ONLY after cryptographic admission.
    # The journal separately records grant vs exact admission and real key IDs.
    request["approvals"] = [{"approver": key["actor"], "role": key["role"], "target": target["name"], "plan_digest": call_digest,
        "operation_digest": operation_digest, "policy_digest": policy_digest, "approved_at": start.isoformat(), "expires_at": end.isoformat(), "evidence_ref": "signature:" + key_id} for key_id, key in signers.items()]
    errors = GATE.validate(request, policy, policy_digest, now, include_chat_context=False)
    if errors and not preparation:
        raise Denied("registered operation failed core contract: " + "; ".join(errors))
    return {"call_digest": call_digest, "grant_digest": digest(grant_body), "registry_digest": digest(registry), "mode": mode,
            "exact_required": exact_required, "signer_ids": sorted(signers), "request": request, "task": task,
            "preparation_only": preparation, "contract_errors": errors, "current_epoch": epoch, "grant_refresh_required": stale_epoch}
