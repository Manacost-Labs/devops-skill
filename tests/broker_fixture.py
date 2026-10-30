"""Synthetic public registry and ephemeral in-memory owner keys; no real access."""
import base64
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
from pathlib import Path
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("broker_test_contract", ROOT / "devops-platform-contracts/scripts/broker_contract.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

SUBJECT = "sha256:" + "a" * 64
EPOCH = "b" * 64
HANDLER = b'''import json, os, pathlib, sys, time
mode = sys.argv[1]
if mode == 'ignore': time.sleep(30)
value = json.load(sys.stdin)
if mode == 'context':
    import hashlib
    context = value['context']
    canonical = lambda data: json.dumps(data,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode('ascii')
    expected = 'sha256:' + hashlib.sha256(canonical(value['parameters'])).hexdigest()
    valid = value['schema_version']=='2.0' and context['operation_id']=='ops-native-context' and context['task_id']=='context-task' and context['parameters_digest']==expected
    print(json.dumps({'state':'after' if valid else 'exposed'}))
    raise SystemExit(0)
path = pathlib.Path(value['target']['path'])
if mode == 'apply': path.write_text(value['parameters']['value'], encoding='utf-8')
if mode == 'fail':
    path.write_text('after', encoding='utf-8')
    raise SystemExit(23)
if mode == 'slow':
    started = pathlib.Path(value['target']['worker_started'])
    pending = started.with_name(started.name + '.pending')
    with pending.open('x', encoding='ascii') as marker: marker.write(str(os.getpid()))
    pending.replace(started)
    time.sleep(30)
if mode == 'invalid':
    path.write_text('after', encoding='utf-8')
    print('not-json')
    raise SystemExit(0)
if mode == 'snapshot':
    try: pathlib.Path(__file__).write_text('replaced', encoding='utf-8')
    except PermissionError: print(json.dumps({'state':'denied'}))
    else: print(json.dumps({'state':'exposed'}))
    raise SystemExit(0)
if mode == 'probe':
    try: pathlib.Path(value['target']['private_state']).read_text(encoding='utf-8')
    except PermissionError: print(json.dumps({'state':'denied'}))
    else: print(json.dumps({'state':'exposed'}))
else: print(json.dumps({'state':path.read_text(encoding='utf-8')}))
'''


def signed(payload, keys, selected=("owner-key",)):
    result = copy.deepcopy(payload)
    result.pop("signatures", None)
    signature = C.DOMAIN + C.canonical(result)
    result["signatures"] = [{"key_id": name, "signature": base64.b64encode(keys[name].sign(signature)).decode("ascii")} for name in selected]
    return result


def registry(*, executable=None, executable_digest=None, subject=SUBJECT, epoch=EPOCH):
    keys = {name: Ed25519PrivateKey.generate() for name in ("owner-key", "security-key")}
    executable = str(Path(executable or sys.executable).resolve())
    binding = executable_digest or C.digest(Path(executable).read_bytes())
    task = {"target_id": "fixture-target", "action": "inspect_fixture", "risk": "R0", "scope": ["service:fixture"],
        "stateful": False, "destructive": False, "irreversible": False, "external_side_effects": False, "data_classification": "public",
        "executable": {"path": executable, "digest": binding}, "argv": ["-I", "@bundle/handler.py@", "inspect"], "bundle": {"handler.py": C.digest(HANDLER)},
        "parameters": {}, "result_schema": {"state": {"enum": ["before", "after", "denied", "exposed"]}}, "timeout_seconds": 4,
        "recovery": {"required": False, "method": None, "artifact_ref": None, "restore_tested_at": None, "rpo_minutes": None, "rto_minutes": None},
        "verification": {"criteria": ["owner observes intended fixture state"], "observation_window_minutes": 1}, "worker_uid": 1001, "worker_gid": 1001}
    read, write, production, destructive = (copy.deepcopy(task) for _ in range(4))
    write.update(action="configure_fixture", risk="R2", external_side_effects=True, parameters={"value": {"enum": ["before", "after"]}}, argv=["-I", "@bundle/handler.py@", "apply"])
    production.update(action="production_deploy", risk="R3", external_side_effects=True)
    destructive.update(action="destructive_fixture", risk="R4", destructive=True, irreversible=True)
    target = {"name": "synthetic-fixture", "environment": "lab", "owner": "user:fixture-owner", "profile_digest": "sha256:" + "c" * 64,
              "resource": {"path": "/target/value", "private_state": "/protected/state/service.json"}}
    result = {"schema_version": "1.0", "server_id": "fixture-broker", "policy": "default-policy.json", "policy_digest": C.GATE.load_registered_policy("default-policy.json")[1],
        "keys": {name: {"public_key": base64.b64encode(key.public_key().public_bytes_raw()).decode("ascii"), "actor": "user:" + name, "role": "service-owner" if name == "owner-key" else "security-owner", "target_ids": ["fixture-target"], "maximum_mode": "full-auto", "maximum_risk": "R4"} for name, key in keys.items()},
        "clients": {subject: {"principal": "fixture-agent", "epoch": epoch}}, "targets": {"fixture-target": target},
        "tasks": {"inspect-task": read, "configure-task": write, "production-task": production, "destructive-task": destructive}}
    return result, keys


def grant(registry, keys, *, mode="balanced", selected=("owner-key",), identifier="grant-fixture-one", epoch=None, start=None, end=None):
    now = datetime.now(timezone.utc)
    subject = next(iter(registry["clients"]))
    body = {"schema_version": "1.0", "kind": "grant", "id": identifier, "audience": registry["server_id"], "registry_digest": C.digest(registry),
        "not_before": (start or now - timedelta(seconds=10)).isoformat(), "expires": (end or now + timedelta(minutes=10)).isoformat(),
        "subject": subject, "epoch": epoch or registry["clients"][subject]["epoch"], "mode": mode, "task_ids": list(registry["tasks"]), "max_operations": 64,
        "trusted_environment": {"isolation_ref": "fixture:separate-principal", "credential_scope_ref": "fixture:only-owned-resource", "owner_evidence_ref": "fixture:reviewed"} if mode == "full-auto" else None}
    return signed(body, keys, selected)


def call(task="configure-task", *, operation="ops-fixture-one", parameters=None):
    return {"schema_version": "1.0", "operation_id": operation, "task_id": task, "parameters": {"value": "after"} if parameters is None and task == "configure-task" else (parameters or {})}


def admission(registry, keys, call, grant, *, epoch=None, selected=("owner-key",)):
    subject = grant["subject"]
    epoch = epoch or registry["clients"][subject]["epoch"]
    prepared = C.assess(call, grant, None, registry, datetime.now(timezone.utc), subject, epoch, preparation=True)
    payload = {"schema_version": "1.0", "kind": "admission", "id": "admit-fixture-one", "audience": registry["server_id"], "registry_digest": C.digest(registry),
        "not_before": grant["not_before"], "expires": grant["expires"], "grant_digest": prepared["grant_digest"], "call_digest": prepared["call_digest"]}
    return signed(payload, keys, selected)
