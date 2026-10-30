"""Local planning-mode workflow; signed broker grants alone admit execution."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
import getpass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

class ChatError(ValueError):
    """Controlled workflow diagnostic without raw event content."""


ROOT = Path(__file__).resolve().parents[2]
SESSION = re.compile(r"[A-Za-z0-9._:-]{6,128}")
CONFIRM = re.compile(r"(?:подтверждаю границы|confirm boundaries) ([0-9a-f]{16})", re.IGNORECASE)
SAFE_MESSAGES = {"safe", "/devops safe", "режим safe", "работай в safe", "переключись в safe", "безопасный режим", "отмени допуск", "revoke devops"}
CARD_FIELDS = {"schema_version", "runtime_id", "session_id", "workspace", "profile_path", "base_selection_digest", "base_safety_epoch", "created_at", "confirm_before", "window_end", "mode", "policy", "target", "executor", "actions", "scope", "data_classifications", "allow_stateful", "allow_external_side_effects", "trusted_environment"}


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def authority():
    return module("chat_authority", ROOT/"devops-platform-contracts/scripts/autonomy.py")


def gate():
    return module("chat_gate", ROOT/"devops-platform-contracts/scripts/operation_gate.py")


def runtime_id():
    return hashlib.sha256(os.path.normcase(str(ROOT.resolve())).encode()).hexdigest()


def state_root():
    return ROOT.parent/".devops-skill-state"/runtime_id()[:16]


def state_file():
    return state_root()/"config.json"


def session_id(value=None):
    value = value or os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID")
    if not isinstance(value, str) or not SESSION.fullmatch(value):
        raise ChatError("a host session ID is required; never infer a session from the workspace")
    return value


def session_key(value):
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def workspace(value=None):
    result = Path(value or Path.cwd()).resolve(strict=True)
    if not result.is_dir():
        raise ChatError("workspace must be an existing directory")
    return str(result)


def same_path(left, right):
    return os.path.normcase(left) == os.path.normcase(right)


def pending_path(sid):
    return ROOT/"operations/chat-modes"/session_key(sid)/"pending.json"


def latch_path(sid):
    # Runtime replacement must never restore an older cancellation snapshot.
    return state_root()/"restrictions"/(session_key(sid)+".json")


def selection_path(sid):
    return state_root()/"sessions"/(session_key(sid)+".json")


def observed_path(sid):
    return state_root()/"observed"/(session_key(sid)+".json")


def safety_epoch(sid):
    path = latch_path(sid)
    return authority().digest(read(path) if path.exists() or path.is_symlink() else None)


def read(path):
    return authority().read_record(path.absolute())


def atomic_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    authority().no_links(path.parent)
    if path.exists() or path.is_symlink():
        read(path)  # Reject links, hardlinks, nonregular and malformed state.
    temporary = path.with_name(".tmp-"+uuid.uuid4().hex)
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        support = module("chat_sync", ROOT/"tools/runtime_lock.py")
        support.sync_directory(path.parent)
    finally:
        if temporary.exists(): temporary.unlink()


def config(required=False):
    path = state_file()
    if not path.exists() and not path.is_symlink():
        if required: raise ChatError("chat adapter is not prepared; run devops_mode.py setup --apply")
        return None
    value = read(path)
    if set(value) != {"schema_version", "runtime_id", "policy", "operator", "role", "hook_path", "authority_dir"} or value["schema_version"] != "1.0" or value["runtime_id"] != runtime_id():
        raise ChatError("invalid chat adapter configuration")
    for key in ("operator", "role", "hook_path", "policy"):
        authority().text(value[key], "chat configuration", 2)
    return value


def raw_selection(sid):
    path = selection_path(sid)
    if not path.exists() and not path.is_symlink(): return None
    value = read(path)
    expected = {"schema_version", "runtime_id", "session_id", "workspace", "selection", "profile_path", "card_digest", "safety_epoch", "updated_at"}
    if set(value) != expected or value["schema_version"] != "1.0" or value["runtime_id"] != runtime_id() or value["session_id"] != sid:
        raise ChatError("invalid chat session selection")
    return value


def profile_digest(path):
    result = subprocess.run([sys.executable, str(ROOT/"devops-core/scripts/profile_digest.py"), str(path)],
                            capture_output=True, text=True, check=False, timeout=10)
    value = result.stdout.strip()
    if result.returncode or not authority().DIGEST.fullmatch(value):
        raise ChatError("target profile is invalid or changed")
    return value


def context(sid=None, cwd=None):
    settings = config()
    if sid is None and not (os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID")): return None
    sid = session_id(sid)
    selected = raw_selection(sid)
    if selected is not None and settings is None: raise ChatError("chat configuration is unavailable; no mode fallback permitted")
    if selected is None:
        path = latch_path(sid)
        if not path.exists() and not path.is_symlink(): return None
        restriction = read(path)
        if restriction.get("session_id") != sid or restriction.get("safe") is not True: raise ChatError("invalid Safe restriction")
        selected = {"schema_version": "1.0", "runtime_id": runtime_id(), "session_id": sid, "workspace": workspace(cwd),
                    "selection": {"mode": "safe", "authorization_id": None, "authorization_digest": None},
                    "profile_path": None, "card_digest": None, "safety_epoch": safety_epoch(sid), "updated_at": restriction.get("requested_at")}
    if not same_path(selected["workspace"], workspace(cwd)):
        raise ChatError("chat mode belongs to another workspace; prepare new boundaries")
    if selected["safety_epoch"] != safety_epoch(sid):
        selected = dict(selected, selection={"mode": "safe", "authorization_id": None, "authorization_digest": None})
    selection = selected["selection"]
    authority().exact(selection, {"mode", "authorization_id", "authorization_digest"}, "chat mode selection")
    if selection["mode"] not in authority().MODES: raise ChatError("invalid selected chat mode")
    return dict(selected, policy_name=settings["policy"] if settings else None)


def authority_directory():
    settings = config()
    return Path(settings["authority_dir"]) if settings else None


def enforce(request, policy, policy_digest, now):
    """Fail closed on active chat context; never silently replace request facts."""
    selected = context()
    if selected is None: return []
    errors = []
    if request.get("autonomy") != selected["selection"]:
        errors.append("operation does not match selected chat mode/authority; re-plan within current boundaries")
    settings = config()
    if settings and policy["policy_id"] != gate().REGISTERED_POLICIES.get(settings["policy"]):
        errors.append("chat policy cannot be replaced by another registered policy")
    if selected["selection"]["mode"] != "safe":
        target = request.get("target")
        if not isinstance(target, dict) or profile_digest(selected["profile_path"]) != target.get("profile_digest"):
            errors.append("chat target profile changed; new boundaries required")
    return errors


def validate_binding(record):
    binding = record.get("chat_binding")
    if binding is None: return
    authority().exact(binding, {"runtime_id", "session_id", "workspace", "card_digest"}, "chat authority binding")
    selected = context()
    if (selected is None or binding["runtime_id"] != runtime_id() or binding["session_id"] != selected["session_id"]
            or not same_path(binding["workspace"], selected["workspace"]) or binding["card_digest"] != selected["card_digest"]
            or selected["selection"].get("authorization_id") != record["authorization_id"]
            or selected["selection"].get("authorization_digest") != authority().digest(record)):
        raise ChatError("chat authority is not active for this host session/workspace")


def hook_command(relative):
    """Literal launcher; registering a hook never trusts or activates it."""
    if os.name == "nt":
        quote = lambda value: "'"+str(value).replace("'", "''")+"'"
        script = "$OutputEncoding=[Console]::InputEncoding=[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); & "+quote(sys.executable)+" -I "+quote(ROOT/relative)+"; exit $LASTEXITCODE"
        return "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand "+base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return __import__("shlex").join([sys.executable, "-I", str(ROOT/relative)])


def setup(codex_home, policy_name, apply):
    settings = config()
    policy_name = policy_name or (settings["policy"] if settings else "default-policy.json")
    gate().load_registered_policy(policy_name)
    if settings and settings["policy"] != policy_name: raise ChatError("setup cannot change existing chat policy")
    home = codex_home.expanduser().absolute()
    hook_path = home/"hooks.json"
    command = hook_command("tools/hooks/chat_mode_hook.py")
    value = read(hook_path) if hook_path.exists() or hook_path.is_symlink() else {"hooks": {}}
    original_hooks = authority().digest(value)
    if not isinstance(value.get("hooks"), dict): raise ChatError("existing hook configuration is malformed")
    entry = {"hooks": [{"type": "command", "command": command, "timeout": 15, "statusMessage": "Checking DevOps mode boundaries"}]}
    for event in ("UserPromptSubmit", "SessionStart"):
        groups = value["hooks"].setdefault(event, [])
        if not isinstance(groups, list): raise ChatError("existing hook event must be a list")
        if entry not in groups: groups.append(entry)
    guard = {"matcher": "*", "hooks": [{"type": "command", "command": hook_command("tools/hooks/codex_pretooluse_gate.py"), "timeout": 15, "statusMessage": "Checking protected DevOps tool path"}]}
    groups = value["hooks"].setdefault("PreToolUse", [])
    if not isinstance(groups, list): raise ChatError("existing tool hook event must be a list")
    if guard not in groups: groups.append(guard)
    if settings is None:
        settings = {"schema_version": "1.0", "runtime_id": runtime_id(), "policy": policy_name,
                    "authority_dir": str(Path(os.environ.get("DEVOPS_AUTHORITY_DIR") or state_root()/"authorities").absolute()),
                    "operator": "host-user:"+getpass.getuser(), "role": "interactive-operator", "hook_path": str(hook_path)}
    elif settings["hook_path"] != str(hook_path): raise ChatError("setup cannot silently relocate trusted hooks")
    print("CHAT SETUP: hook configuration and private state are prepared automatically; no mode is activated.")
    print("HOST TRUST REQUIRED ONCE: review/trust the exact hook in Codex; do not bypass host trust. Same-user/full-access execution is not independent issuer isolation.")
    if not apply:
        print("DRY RUN: add --apply to write the reversible setup.")
        return
    if config() is not None and authority().digest(value) == original_hooks:
        print("ALREADY PREPARED: existing hooks/settings preserved; host trust is still required.")
        return
    if hook_path.exists():
        backup = hook_path.with_name("hooks.devops-backup-"+uuid.uuid4().hex+".json")
        atomic_write(backup, read(hook_path))
    for directory in (Path(settings["authority_dir"]), state_root()/"sessions"):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700); authority().no_links(directory)
        if directory.resolve() == ROOT or ROOT in directory.resolve().parents: raise ChatError("issued authority must remain outside the runtime")
    atomic_write(state_file(), settings)
    atomic_write(hook_path, value)
    print("PREPARED: ask the host to trust/load these hooks; installing config does not establish trust or protected-store isolation.")


def prepare(args):
    import yaml
    settings = config(True)
    sid = session_id(args.session_id); cwd = workspace(args.workspace)
    selected = raw_selection(sid)
    policy_name = args.policy or settings["policy"]
    if policy_name != settings["policy"]: raise ChatError("chat policy is pinned by setup")
    g = gate(); policy, pdigest = g.load_registered_policy(policy_name)
    a = authority()
    if a.MODES[args.mode] > a.MODES[policy["autonomy"]["maximum_mode"]]: raise ChatError("organization policy forbids this mode")
    if args.mode == "safe":
        print(safe(sid)); return
    if max(policy["minimum_approvals"]["R"+str(rank)] for rank in range(a.MODES[args.mode]+1)) > 1:
        raise ChatError("policy requires multiple independent owners; use the trusted external issuer instead of a one-user callback")
    if not args.target_profile: raise ChatError("prepare a validated target profile before asking for confirmation")
    profile_path = Path(args.target_profile).absolute()
    fingerprint = profile_digest(profile_path)
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8-sig"))
    target = {key: profile[key] for key in ("name", "environment", "owner")}; target["profile_digest"] = fingerprint
    if target["environment"] == "production" and not policy["autonomy"]["allow_production"]: raise ChatError("policy forbids delegated production")
    actions = a.unique_list(args.action, "actions"); scope = a.unique_list(args.scope, "scope")
    if any(not a.ACTION.fullmatch(item) for item in actions) or set(actions) & set(policy["deny_by_default"]): raise ChatError("invalid or policy-denied action")
    classification = args.data_classification or profile["data_classification"]
    if classification not in policy["data"]["allowed_classifications"]: raise ChatError("data classification is outside policy")
    ttl = min(policy["approval_ttl_minutes"], policy["autonomy"]["grant_ttl_minutes"])
    minutes = args.minutes if args.minutes is not None else min(60, ttl)
    if not 1 <= minutes <= ttl: raise ChatError("requested window exceeds policy")
    now = datetime.now(timezone.utc)
    trust = None
    if args.mode == "full-auto":
        trust = {"isolation_ref": args.isolation_ref, "credential_scope_ref": args.credential_scope_ref, "owner_evidence_ref": args.owner_evidence_ref}
        for item in trust.values(): a.text(item, "real Full Auto evidence reference", 4)
    a.text(args.executor, "executor", 3)
    if selected and same_path(selected["workspace"], cwd) and selected["selection"]["mode"] == args.mode and selected["safety_epoch"] == safety_epoch(sid):
        try:
            existing = read(authority_directory()/(selected["selection"]["authorization_id"]+".json"))
            a.validate_record(existing, policy, pdigest, now)
            if (a.digest(existing) == selected["selection"]["authorization_digest"] and existing["target"] == target
                    and existing["executor"] == args.executor and set(actions) <= set(existing["actions"])
                    and set(scope) <= set(existing["scope"]) and classification in existing["data_classifications"]
                    and (not args.stateful or existing["allow_stateful"]) and (not args.external_side_effects or existing["allow_external_side_effects"])
                    and trust == existing["trusted_environment"] and args.minutes is None):
                print("PLANNING_ALREADY_SELECTED: reuse existing boundaries and original expiry; no additional confirmation.")
                return
        except (OSError, ValueError, KeyError, TypeError):
            pass  # New explicit confirmation is required; never silently renew.
    body = {"schema_version": "1.0", "runtime_id": runtime_id(), "session_id": sid, "workspace": cwd,
            "profile_path": str(profile_path), "base_selection_digest": a.digest(selected), "base_safety_epoch": safety_epoch(sid), "created_at": now.isoformat(),
            "confirm_before": (now+timedelta(minutes=min(10, minutes))).isoformat(),
            "window_end": (now+timedelta(minutes=minutes)).isoformat(), "mode": args.mode,
            "policy": {"id": policy["policy_id"], "version": policy["version"], "digest": pdigest},
            "target": target, "executor": args.executor, "actions": actions, "scope": scope,
            "data_classifications": [classification], "allow_stateful": args.stateful,
            "allow_external_side_effects": args.external_side_effects, "trusted_environment": trust}
    existing = pending_path(sid)
    if existing.exists() and args.minutes is None:
        prior = read(existing)
        stable = CARD_FIELDS - {"created_at", "confirm_before", "window_end"}
        if (set(prior) == CARD_FIELDS and all(prior[key] == body[key] for key in stable)
                and now < a.timestamp(prior["confirm_before"], "confirmation expiry")):
            print(render(prior, a.digest(prior)[7:23]))
            return
    token = a.digest(body)[7:23]
    # Preparation does not consume existing authority and cannot activate anything.
    atomic_write(existing, body)
    print(render(body, token))


def render(body, token):
    trust = body["trusted_environment"]
    trust_text = ("Проверенное владельцем окружение: изоляция "+trust["isolation_ref"]+", ограничения доступа "+trust["credential_scope_ref"]+", решение владельца "+trust["owner_evidence_ref"]+"\n") if trust else ""
    return (f"Режим: {body['mode']}\nОкружение: {body['target']['name']} ({body['target']['environment']}); владелец: {body['target']['owner']}\n"
            f"Действия: {', '.join(body['actions'])}\nРесурсы: {', '.join(body['scope'])}\n"
            f"Данные: {', '.join(body['data_classifications'])}; изменение состояния: {'разрешено' if body['allow_stateful'] else 'не разрешено'}; внешние последствия: {'разрешены' if body['allow_external_side_effects'] else 'не разрешены'}\n"
            f"Срок: после подтверждения до {body['window_end']}\nПолитика: {body['policy']['id']}; исполнитель: {body['executor']}\n"
            f"Подтвердить до: {body['confirm_before']}\n"
            f"Рабочая область: {body['workspace']}\n"+trust_text+
            "Разрушительные/необратимые действия и выход за границы требуют отдельного допуска. Проверка, восстановление и журнал сохраняются.\n"
            "Подтверждение выбирает границы планирования. Исполнение требует отдельного подписанного допуска защищённого брокера.\n"
            f"Для выбора границ ответьте: Подтверждаю границы {token}\nДля отмены: Safe")


def safe(sid=None, *, contact_broker=True):
    sid = session_id(sid)
    remote = False
    profile = ROOT/"broker-client.json"
    if contact_broker and (profile.exists() or profile.is_symlink()):
        client = module("chat_broker_restriction_client", ROOT/"tools/devops_exec.py")
        result = client.call_broker(read(profile), {"mode": "safe", "grant": None}, "restrict")
        if result.get("status") != "restricted" or result.get("mode") != "safe":
            raise ChatError("broker Safe acknowledgement unavailable; do not claim restriction took effect")
        remote = True
    atomic_write(latch_path(sid), {"safe": True, "session_id": sid, "nonce": uuid.uuid4().hex, "requested_at": datetime.now(timezone.utc).isoformat()})
    return ("SAFE: protected broker cancelled prior higher-mode grants for this client identity; no confirmation required."
            if remote else "SAFE: local planning restricted only; broker not configured. This is not remote execution revocation.")


def status(sid=None):
    print("PLANNING ONLY: chat events and local JSON do not authorize execution; the protected broker checks signed scope.")
    settings = config()
    if settings is None:
        print("SETUP_REQUIRED: the agent can prepare setup automatically; no mode is activated.")
        return
    sid = session_id(sid)
    seen = observed_path(sid)
    if not seen.exists():
        print("HOST_HOOK_NOT_OBSERVED: setup files exist but no callback for this session; review/trust/load the hook in Codex before requesting scope confirmation.")
        return
    observed = read(seen)
    if observed.get("session_id") != sid or observed.get("runtime_id") != runtime_id(): raise ChatError("invalid host callback observation")
    selected = context(sid)
    if selected is None: print("SAFE: no active chat selection; host hook trust cannot be inferred from setup files.")
    else:
        if selected["selection"]["mode"] != "safe":
            record = read(authority_directory()/(selected["selection"]["authorization_id"]+".json"))
            policy, pdigest = gate().load_registered_policy(settings["policy"])
            authority().validate_record(record, policy, pdigest, datetime.now(timezone.utc))
            if authority().digest(record) != selected["selection"]["authorization_digest"]: raise ChatError("authority changed")
            if profile_digest(selected["profile_path"]) != record["target"]["profile_digest"]: raise ChatError("target profile changed; prepare new boundaries")
        print(json.dumps(selected, ensure_ascii=False, sort_keys=True))


def revoke_record(selected):
    if not selected or selected["selection"]["mode"] == "safe": return
    path = authority_directory()/(selected["selection"]["authorization_id"]+".json")
    if path.exists():
        record = read(path); record["status"] = "revoked"; atomic_write(path, record)


def host_event(event):
    """Only the trusted host hook calls this. Stdin alone is not authentication."""
    if not isinstance(event.get("session_id"), str) or not SESSION.fullmatch(event["session_id"]):
        raise ChatError("host session identity is required")
    if not isinstance(event.get("cwd"), str) or not Path(event["cwd"]).is_absolute():
        raise ChatError("actual host workspace is required")
    settings = config(True); sid = session_id(event["session_id"]); cwd = workspace(event["cwd"])
    kind = event.get("hook_event_name")
    if kind not in {"SessionStart", "UserPromptSubmit"}: raise ChatError("unsupported host event")
    if kind == "UserPromptSubmit" and (not isinstance(event.get("turn_id"), str) or not SESSION.fullmatch(event["turn_id"])):
        raise ChatError("actual host turn reference is required")
    atomic_write(observed_path(sid), {"runtime_id": runtime_id(), "session_id": sid, "workspace": cwd,
                                     "observed_at": datetime.now(timezone.utc).isoformat(), "event": kind})
    if kind == "SessionStart":
        selected = context(sid, cwd)
        return "DevOps chat modes ready. Prepare boundaries with devops_mode.py; only a direct exact confirmation activates them. Current mode: "+(selected["selection"]["mode"] if selected else "safe")
    prompt = event.get("prompt")
    if not isinstance(prompt, str) or len(prompt) > 65536: raise ChatError("invalid host prompt")
    normalized = " ".join(prompt.strip().split())
    match = CONFIRM.fullmatch(normalized)
    if not match and normalized.casefold() not in SAFE_MESSAGES: return None
    if not match:
        safe(sid)  # Cancellation must restrict immediately, even if issuance owns the lock.
    support = module("chat_host_lock", ROOT/"tools/runtime_lock.py")
    try:
        lock = support.runtime_lock(ROOT.parent/(".chat-coordination-"+runtime_id()[:16]))
        lock.__enter__()
    except support.RuntimeLockError:
        if not match: return "SAFE: restriction applied immediately; issuer metadata cleanup is pending. Previously prepared higher-mode plans are blocked."
        raise
    try:
        previous = raw_selection(sid)
        now = datetime.now(timezone.utc); a = authority()
        if not match:
            revoke_record(previous)
            value = {"schema_version": "1.0", "runtime_id": runtime_id(), "session_id": sid, "workspace": cwd,
                     "selection": {"mode": "safe", "authorization_id": None, "authorization_digest": None},
                     "profile_path": None, "card_digest": None, "safety_epoch": safety_epoch(sid), "updated_at": now.isoformat()}
            atomic_write(selection_path(sid), value)
            return "SAFE: user revoked the chat authority; previously prepared higher-mode plans must not execute."
        body = read(pending_path(sid)); a.exact(body, CARD_FIELDS, "chat boundaries"); card_digest = a.digest(body)
        if match[1].casefold() != card_digest[7:23]: raise ChatError("confirmation does not match current boundaries")
        if body.get("runtime_id") != runtime_id() or body.get("session_id") != sid or not same_path(body.get("workspace", ""), cwd): raise ChatError("confirmation belongs to another session/workspace")
        if body["base_safety_epoch"] != safety_epoch(sid): raise ChatError("newer Safe cancellation wins; prepare new boundaries")
        if profile_digest(body["profile_path"]) != body["target"]["profile_digest"]: raise ChatError("profile changed after preparation")
        # A duplicate confirmation never extends permission or revives a revoked selection.
        if previous and previous["card_digest"] == card_digest and previous["selection"]["mode"] != "safe":
            record = read(authority_directory()/(previous["selection"]["authorization_id"]+".json"))
            policy, pdigest = gate().load_registered_policy(settings["policy"])
            a.validate_record(record, policy, pdigest, now)
            if a.digest(record) != previous["selection"]["authorization_digest"]: raise ChatError("prior authority changed")
            return "PLANNING_ALREADY_SELECTED: same boundaries and original expiry; no new confirmation needed."
        if a.digest(previous) != body["base_selection_digest"]: raise ChatError("selection changed after preparation; old confirmation cannot reactivate it")
        if not a.timestamp(body["created_at"], "card created") <= now < a.timestamp(body["confirm_before"], "card expiry"): raise ChatError("confirmation card expired or not open")
        policy, pdigest = gate().load_registered_policy(settings["policy"])
        if body["policy"] != {"id": policy["policy_id"], "version": policy["version"], "digest": pdigest}: raise ChatError("policy changed after preparation")
        identifier = "authority-chat-"+session_key(sid)[:12]+"-"+match[1].casefold()
        path = authority_directory()/(identifier+".json")
        if path.exists():
            record = read(path)  # Recover an interrupted issuance without refreshing its clock.
        else:
            fields = ("mode", "policy", "target", "executor", "actions", "scope", "data_classifications", "allow_stateful", "allow_external_side_effects", "window_end", "trusted_environment")
            record = {key: body[key] for key in fields}
            record.update(schema_version="1.0", authorization_id=identifier, status="active", window_start=now.isoformat(), authorizations=[],
                          chat_binding={"runtime_id": runtime_id(), "session_id": sid, "workspace": cwd, "card_digest": card_digest})
            record["authorizations"] = [{"approver": settings["operator"], "role": settings["role"], "payload_digest": a.payload_digest(record),
                                          "approved_at": now.isoformat(), "expires_at": record["window_end"],
                                          "evidence_ref": "host-prompt:"+sid+":"+event["turn_id"]+":"+match[1].casefold()}]
        a.validate_record(record, policy, pdigest, now)
        if record.get("chat_binding") != {"runtime_id": runtime_id(), "session_id": sid, "workspace": cwd, "card_digest": card_digest}: raise ChatError("interrupted authority does not match boundaries")
        atomic_write(path, record)
        revoke_record(previous)
        value = {"schema_version": "1.0", "runtime_id": runtime_id(), "session_id": sid, "workspace": cwd,
                 "selection": {"mode": body["mode"], "authorization_id": identifier, "authorization_digest": a.digest(record)},
                 "profile_path": body["profile_path"], "card_digest": card_digest, "safety_epoch": body["base_safety_epoch"], "updated_at": now.isoformat()}
        atomic_write(selection_path(sid), value)
        if safety_epoch(sid) != body["base_safety_epoch"]:
            return "SAFE: a newer cancellation wins over this confirmation; higher-mode launches remain blocked."
        return "PLANNING_SELECTED: "+body["mode"]+" until "+record["window_end"]+". Reuse these boundaries without new human questions; retain fresh gate/recovery/verification/journal checks."
    finally:
        lock.__exit__(None, None, None)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    install = commands.add_parser("setup", allow_abbrev=False)
    install.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME") or Path.home()/".codex"))
    install.add_argument("--policy"); install.add_argument("--apply", action="store_true")
    prepare_parser = commands.add_parser("prepare", allow_abbrev=False)
    prepare_parser.add_argument("--mode", choices=list(authority().MODES), required=True)
    prepare_parser.add_argument("--target-profile"); prepare_parser.add_argument("--session-id"); prepare_parser.add_argument("--workspace")
    prepare_parser.add_argument("--policy"); prepare_parser.add_argument("--executor", default="service:codex")
    prepare_parser.add_argument("--action", action="append", default=[]); prepare_parser.add_argument("--scope", action="append", default=[])
    prepare_parser.add_argument("--data-classification"); prepare_parser.add_argument("--minutes", type=int)
    prepare_parser.add_argument("--stateful", action="store_true"); prepare_parser.add_argument("--external-side-effects", action="store_true")
    for name in ("isolation-ref", "credential-scope-ref", "owner-evidence-ref"): prepare_parser.add_argument("--"+name)
    for name in ("status", "safe"):
        commands.add_parser(name, allow_abbrev=False).add_argument("--session-id")
    args = parser.parse_args()
    try:
        if args.command == "setup": setup(args.codex_home, args.policy, args.apply)
        elif args.command == "prepare": prepare(args)
        elif args.command == "safe": print(safe(args.session_id))
        else: status(args.session_id)
        return 0
    except ChatError as error:
        print("BLOCKED: "+str(error))
        return 2
    except (OSError, ValueError, TypeError, KeyError, RecursionError, subprocess.SubprocessError):
        print("BLOCKED: invalid, changed or unavailable chat boundaries/configuration; no authority issued by this command.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
