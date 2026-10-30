#!/usr/bin/env python3
"""Isolated TLS broker. Install runtime/registry/store under a separate principal.

The public API never accepts commands, environment, paths, risk or authorizer
labels. Only operator-registered immutable tasks and finite parameters execute.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import secrets
import signal
import ssl
import stat
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


C = module("protected_broker_contract", ROOT / "devops-platform-contracts/scripts/broker_contract.py")
LOCK = module("protected_broker_lock", ROOT / "tools/runtime_lock.py")
OUTPUT_LIMIT = 1024 * 1024


class NotLaunched(C.Denied):
    """Final admission or OS creation refused before a worker started."""


def regular(path, maximum):
    C.GATE.AUTONOMY.no_links(path.absolute())
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        state = os.fstat(stream.fileno())
        if not stat.S_ISREG(state.st_mode) or state.st_nlink != 1 or state.st_size > maximum:
            raise C.Denied("bounded single-link regular input required")
        content = stream.read(maximum + 1)
    if len(content) > maximum:
        raise C.Denied("input limit exceeded")
    return content


def atomic(path, value):
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    C.GATE.AUTONOMY.no_links(path.parent.absolute())
    if path.exists() or path.is_symlink():
        C.read_record(path)
    temporary = path.with_name(".pending-" + uuid.uuid4().hex)
    try:
        with temporary.open("xb") as stream:
            stream.write(C.canonical(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        for directory in dict.fromkeys([path.parent, *(item.parent for item in missing)]):
            LOCK.sync_directory(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


def immutable(path):
    """Check managed Linux paths; external provisioning remains the trust root."""
    path = Path(path).absolute()
    C.GATE.AUTONOMY.no_links(path)
    for item in (path, *path.parents):
        state = item.stat()
        if state.st_mode & stat.S_ISVTX and stat.S_ISDIR(state.st_mode) and item != path:
            # Sticky /tmp parent cannot replace an existing root-owned child.
            # The directory owner itself can replace children despite sticky;
            # a writable sticky ancestor owned by the agent is not protection.
            if state.st_uid != 0:
                raise C.Denied("sticky managed ancestors must be root-owned")
            continue
        if os.statvfs(item).f_flag & os.ST_RDONLY:
            continue
        if state.st_uid != 0 or state.st_mode & 0o022:
            raise C.Denied("managed paths must be read-only or root-owned without shared writes")


def verify_deployment(config):
    for name in ("registry", "bundle_dir", "certificate", "private_key", "client_ca"):
        immutable(Path(config[name]))
    immutable(ROOT)
    immutable(Path(sys.executable).resolve())
    private = Path(config["state_dir"])
    metadata = private.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise C.Denied("broker state must be private to the supervisor")
    workers = Path(config["worker_dir"])
    metadata = workers.stat()
    if metadata.st_uid != 0 or metadata.st_mode & 0o022:
        raise C.Denied("worker scratch parent must be supervisor-controlled")
    immutable(private)
    immutable(workers)


class Broker:
    def __init__(self, registry_path, bundle_dir, state_dir, worker_dir):
        self.registry_path = Path(registry_path).absolute()
        self.bundle_dir = Path(bundle_dir).absolute()
        self.state_dir = Path(state_dir).absolute()
        self.worker_dir = Path(worker_dir).absolute()
        self.mutex = threading.Lock()
        self.admission_lock = threading.Lock()
        self.signal_lock = threading.Lock()
        self.audit_lock = threading.Lock()
        self.restriction_signals = {}
        self.volatile_restrictions = {}
        self.poisoned = False
        self.closed = False
        for path in (self.bundle_dir, self.state_dir, self.worker_dir):
            C.GATE.AUTONOMY.no_links(path)
            if not path.is_dir():
                raise C.Denied("provisioned broker directories required")
        initial = C.read_record(self.registry_path)
        C.validate_registry(initial)
        self.clients = initial["clients"]
        if self.state_dir == self.worker_dir or self.state_dir in self.worker_dir.parents or self.worker_dir in self.state_dir.parents:
            raise C.Denied("worker scratch must be separate from protected broker state")
        for name in ("journal", "restrictions", "targets"):
            path = self.state_dir / name
            path.mkdir(mode=0o700, exist_ok=True)
            C.GATE.AUTONOMY.no_links(path)
        LOCK.sync_directory(self.state_dir)
        LOCK.sync_directory(self.state_dir.parent)
        self.process_lock = LOCK.runtime_lock(self.state_dir)
        self.process_lock.__enter__()
        try:
            self.boot = self.state_dir / "service.json"
            if self.boot.exists() and C.read_record(self.boot).get("clean") is not True:
                raise C.Denied("unclean broker shutdown requires owner reconciliation")
            atomic(self.boot, {"clean": False})
            self.audit_verify()
        except Exception:
            self.process_lock.__exit__(None, None, None)
            raise

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if not self.poisoned and not self.mutex.locked() and not any((self.state_dir / "targets").iterdir()):
                atomic(self.boot, {"clean": True})
        finally:
            self.process_lock.__exit__(None, None, None)

    def context(self, packet, subject, *, preparation=False):
        C.exact(packet, {"call", "grant", "admission"})
        registry = C.read_record(self.registry_path)
        C.validate_registry(registry)
        if sys.platform.startswith("linux") and os.geteuid() == 0:
            for task in registry["tasks"].values():
                immutable(Path(task["executable"]["path"]))
        if subject not in registry["clients"] or self.poisoned:
            raise C.Denied("client identity or durable service state unavailable")
        state = self.principal_state(registry, subject)
        if packet["grant"].get("epoch") not in [state["epoch"], *state["previous_epochs"]]:
            raise C.Denied("unrecognized authorization generation")
        result = C.assess(packet["call"], packet["grant"], packet["admission"], registry, datetime.now(timezone.utc), subject, state["epoch"], state["ceiling"], preparation=preparation)
        policy, _ = C.GATE.load_registered_policy(registry["policy"])
        if policy["ledger"]["external_immutable_sink_required"]:
            if not preparation:
                raise C.Denied("required independent immutable audit sink is not configured")
            result["contract_errors"].append("required independent immutable audit sink is not configured")
        return registry, result

    def audit_verify(self):
        path = self.state_dir / "audit.jsonl"
        previous, seen = "sha256:" + "0" * 64, set()
        if path.exists() or path.is_symlink():
            for raw in regular(path, 16 * 1024 * 1024).splitlines():
                record = C.decode(raw)
                C.exact(record, {"event_id", "previous_hash", "payload", "record_hash"})
                payload = {key: value for key, value in record.items() if key != "record_hash"}
                if record["previous_hash"] != previous or record["record_hash"] != C.digest(payload) or record["event_id"] in seen:
                    raise C.Denied("broker audit chain invalid")
                previous = record["record_hash"]
                seen.add(record["event_id"])
        return previous, seen

    def audit_append(self, event_id, payload):
        with self.audit_lock:
            previous, seen = self.audit_verify()
            if event_id in seen or len(seen) >= 8192:
                raise C.Denied("audit identity or capacity unavailable")
            record = {"event_id": event_id, "previous_hash": previous, "payload": payload}
            record["record_hash"] = C.digest(record)
            path = self.state_dir / "audit.jsonl"
            flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
            with os.fdopen(os.open(path, flags, 0o600), "ab") as stream:
                metadata = os.fstat(stream.fileno())
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise C.Denied("regular private audit file required")
                stream.write(C.canonical(record) + b"\n")
                stream.flush(); os.fsync(stream.fileno())
            LOCK.sync_directory(path.parent)

    def principal_state(self, registry, subject):
        if subject not in registry["clients"] or registry["clients"][subject] != self.clients.get(subject):
            raise C.Denied("unregistered client identity")
        principal = registry["clients"][subject]["principal"]
        restriction = self.state_dir / "restrictions" / (C.digest(principal)[7:] + ".json")
        state = {"principal": principal, "epoch": registry["clients"][subject]["epoch"], "ceiling": "full-auto", "previous_epochs": []}
        if restriction.exists() or restriction.is_symlink():
            state = C.read_record(restriction)
            C.exact(state, {"principal", "epoch", "ceiling", "previous_epochs"})
            if state["principal"] != principal:
                raise C.Denied("restriction binding changed")
        return self.volatile_restrictions.get(principal, state)

    def signal_restriction(self, subject, delta):
        with self.signal_lock:
            principal = self.clients.get(subject, {}).get("principal", subject)
            self.restriction_signals[principal] = self.restriction_signals.get(principal, 0) + delta

    def snapshot(self, task, registry, call, run_dir):
        # All source files must reside in the broker-only bundle directory.
        # Snapshot verified descriptor bytes into a new private execution tree;
        # later replacements of any original source cannot change this launch.
        run_dir.mkdir(mode=0o711)
        bundle = run_dir / "bundle"
        bundle.mkdir(mode=0o700)
        total_bytes = 0
        for filename, expected in task["bundle"].items():
            source = self.bundle_dir / filename
            content = regular(source, 4 * 1024 * 1024)
            total_bytes += len(content)
            if total_bytes > 16 * 1024 * 1024:
                raise C.Denied("task bundle exceeds execution bound")
            if C.digest(content) != expected:
                raise C.Denied("task bundle identity changed")
            target = bundle / filename
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open("xb") as output:
                output.write(content)
            target.chmod(0o444)
        for directory in sorted((path for path in bundle.rglob("*") if path.is_dir()), reverse=True):
            directory.chmod(0o555)
        bundle.chmod(0o555)
        executable = Path(task["executable"]["path"])
        if C.digest(regular(executable, 128 * 1024 * 1024)) != task["executable"]["digest"]:
            raise C.Denied("registered executable identity changed")
        argv = [str(executable)]
        for argument in task["argv"]:
            if argument.startswith("@bundle/") and argument.endswith("@"):
                filename = argument[len("@bundle/"):-1]
                if filename not in task["bundle"]:
                    raise C.Denied("unregistered task input")
                argv.append(str(bundle / filename))
            elif "@bundle" in argument:
                raise C.Denied("ambiguous bundle argument")
            else:
                argv.append(argument)
        home = run_dir / "home"
        home.mkdir(mode=0o700)
        work = run_dir / "work"
        work.mkdir(mode=0o700)
        for path in (home, work):
            os.chown(path, task["worker_uid"], task["worker_gid"])
        # No caller environment, inherited cloud keys, PATH plugins or user RCs.
        environment = {"PATH": str(executable.parent), "HOME": str(home), "LANG": "C.UTF-8", "PYTHONNOUSERSITE": "1"}
        value = {"parameters": call["parameters"], "target": registry["targets"][task["target_id"]]["resource"]}
        return argv, environment, C.canonical(value)

    def launch(self, argv, environment, payload, run_dir, task, final_check):
        if os.name != "posix":
            raise C.Denied("isolated broker execution currently requires a Unix service principal")
        output = {"stdout": bytearray(), "stderr": bytearray()}
        overflow = threading.Event()
        with self.admission_lock:
            try:
                admitted = final_check()
                # No filesystem/crypto work follows this final admission point.
                # A restriction signals before waiting for the admission lock.
                with self.signal_lock:
                    if self.restriction_signals.get(admitted["principal"], 0):
                        raise C.Denied("restriction pending")
                now = datetime.now(timezone.utc)
                if not C.stamp(admitted["window_start"]) <= now < C.stamp(admitted["window_end"]):
                    raise C.Denied("admission expired at launch point")
                process = subprocess.Popen([sys.executable, "-I", str(ROOT / "tools/broker_worker.py"), str(task["timeout_seconds"]), "--", *argv],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=run_dir / "work", env=environment,
                    start_new_session=True, user=task["worker_uid"], group=task["worker_gid"], extra_groups=[], umask=0o077)
            except Exception:
                raise NotLaunched("final admission or worker creation refused") from None

        def kill():
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        def read(name, stream):
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                remaining = OUTPUT_LIMIT - len(output[name])
                output[name].extend(chunk[:max(remaining, 0)])
                if len(chunk) > remaining:
                    overflow.set(); kill()
            stream.close()

        readers = [threading.Thread(target=read, args=(name, getattr(process, name)), daemon=True) for name in output]
        for reader in readers:
            reader.start()
        def write():
            try:
                process.stdin.write(payload)
            except (BrokenPipeError, OSError):
                pass
            finally:
                process.stdin.close()

        writer = threading.Thread(target=write, daemon=True)
        writer.start()
        uncertain = False
        try:
            process.wait(timeout=task["timeout_seconds"])
        except (subprocess.TimeoutExpired, BrokenPipeError, OSError):
            uncertain = True; kill(); process.wait(timeout=5)
        finally:
            writer.join(timeout=2)
            for reader in readers:
                reader.join(timeout=2)
            if writer.is_alive() or any(reader.is_alive() for reader in readers):
                uncertain = True; kill()
        # Output may contain secrets or application data: keep it out of API and
        # journal. Task acceptance is a separately observed owner responsibility.
        structured = None
        try:
            structured = C.decode(bytes(output["stdout"]))
            C.validate_parameters(task["result_schema"], structured)
        except Exception:
            structured = None
        return {"status": "outcome_unknown" if uncertain or overflow.is_set() or structured is None else "executed", "exit_code": process.returncode,
                "stdout_digest": C.digest(bytes(output["stdout"])), "stderr_digest": C.digest(bytes(output["stderr"])),
                "result_valid": structured is not None, "result": structured}

    def dispatch(self, route, packet, subject):
        if route == "describe":
            C.exact(packet, {"grant"})
            registry = C.read_record(self.registry_path)
            C.validate_registry(registry)
            grant, _ = C.validate_grant(packet["grant"], registry, datetime.now(timezone.utc), subject)
            if grant["subject"] != subject or subject not in registry["clients"]:
                raise C.Denied("grant belongs to another client")
            tasks = grant["task_ids"]
            if not isinstance(tasks, list) or any(task_id not in registry["tasks"] for task_id in tasks):
                raise C.Denied("unknown granted tasks")
            state = self.principal_state(registry, subject)
            return {"status": "described", "current_epoch": state["epoch"], "registry_digest": C.digest(registry),
                    "tasks": {task_id: {key: registry["tasks"][task_id][key] for key in ("target_id", "risk", "action", "scope", "parameters")} for task_id in tasks}}
        if route == "restrict":
            C.exact(packet, {"mode", "grant"})
            self.signal_restriction(subject, 1)
            try:
                return self.restrict(packet, subject)
            finally:
                self.signal_restriction(subject, -1)
        return self.dispatch_work(route, packet, subject)

    def restrict(self, packet, subject):
        with self.admission_lock:
            registry = C.read_record(self.registry_path)
            C.validate_registry(registry)
            if subject not in registry["clients"]:
                raise C.Denied("unregistered client identity")
            principal = registry["clients"][subject]["principal"]
            mode = packet["mode"]
            if mode not in C.MODES:
                raise C.Denied("unknown restriction mode")
            previous = self.principal_state(registry, subject)
            if C.MODES[mode] > C.MODES[previous["ceiling"]]:
                raise C.Denied("restriction cannot raise the persisted ceiling")
            if mode != "safe":
                grant, _ = C.validate_grant(packet["grant"], registry, datetime.now(timezone.utc), subject)
                if grant["subject"] != subject or grant["mode"] not in C.MODES:
                    raise C.Denied("restriction does not bind client")
                if grant["epoch"] not in [previous["epoch"], *previous["previous_epochs"]]:
                    raise C.Denied("unrecognized authorization generation")
                if C.MODES[mode] > C.MODES[grant["mode"]]:
                    raise C.Denied("restriction cannot increase issued authority")
            epoch = secrets.token_hex(32)
            history = [*previous["previous_epochs"], previous["epoch"]]
            if len(history) > 1024:
                if mode != "safe":
                    raise C.Denied("restriction history requires owner reconciliation")
                history = []  # Old grants become wholly unusable; Safe still works.
            state = {"principal": principal, "epoch": epoch, "ceiling": mode, "previous_epochs": history}
            self.volatile_restrictions[principal] = state
            try:
                atomic(self.state_dir / "restrictions" / (C.digest(principal)[7:] + ".json"), state)
                self.audit_append("restriction-" + uuid.uuid4().hex, {"subject": subject, "mode": mode, "epoch_digest": C.digest(epoch)})
            except Exception:
                self.poisoned = True
                raise
        return {"status": "restricted", "mode": mode, "current_epoch": epoch}


    def dispatch_work(self, route, packet, subject):
        if route == "status":
            C.exact(packet, {"operation_id"})
            C.identifier(packet["operation_id"])
            if subject not in C.read_record(self.registry_path)["clients"]:
                raise C.Denied("unregistered client identity")
            entry = C.read_record(self.state_dir / "journal" / (packet["operation_id"] + ".json"))
            if entry["principal"] != self.clients[subject]["principal"]:
                raise C.Denied("receipt belongs to another client")
            return {key: entry[key] for key in ("status", "exit_code", "call_digest", "result_valid", "result") if key in entry}
        if not self.mutex.acquire(blocking=False):
            raise C.Denied("broker busy; reconcile before retry")
        try:
            return self.perform(route, packet, subject)
        finally:
            self.mutex.release()

    def perform(self, route, packet, subject):
        registry, result = self.context(packet, subject, preparation=route == "prepare")
        if route == "prepare":
            return {"status": "blocked_proposal" if result["contract_errors"] else "prepared", "call_digest": result["call_digest"], "grant_digest": result["grant_digest"],
                    "registry_digest": result["registry_digest"], "mode": result["mode"], "risk": result["task"]["risk"], "exact_admission_required": result["exact_required"],
                    "current_epoch": result["current_epoch"], "grant_refresh_required": result["grant_refresh_required"], "contract_errors": result["contract_errors"]}
        if route != "execute":
            raise C.Denied("unknown broker route")
        call = packet["call"]
        journal = self.state_dir / "journal" / (call["operation_id"] + ".json")
        if journal.exists() or journal.is_symlink():
            previous = C.read_record(journal)
            if previous["call_digest"] != result["call_digest"]:
                raise C.Denied("idempotency identity already bound to another call")
            if previous["status"] == "launch_intent":
                raise C.Denied("previous launch outcome unknown; owner reconciliation required")
            return {"status": previous["status"], "exit_code": previous.get("exit_code"), "replayed": True, "call_digest": result["call_digest"],
                    "result_valid": previous.get("result_valid", False), "result": previous.get("result")}
        records = list((self.state_dir / "journal").iterdir())
        if len(records) >= 4096:
            raise C.Denied("broker receipt capacity requires owner retention handling")
        used = sum(C.read_record(path).get("grant_digest") == result["grant_digest"] for path in records)
        if used >= packet["grant"]["max_operations"]:
            raise C.Denied("issued operation budget exhausted")
        target_latch = self.state_dir / "targets" / (C.digest(result["task"]["target_id"])[7:] + ".json")
        mutation = result["task"]["external_side_effects"] or result["task"]["stateful"] or int(result["task"]["risk"][1]) > 1
        if mutation and target_latch.exists():
            raise C.Denied("target outcome requires owner reconciliation")
        run_dir = self.worker_dir / (call["operation_id"] + "-" + uuid.uuid4().hex)
        argv, environment, payload = self.snapshot(result["task"], registry, call, run_dir)
        # Remote workers need admitted correlation/deadline bindings. Preserve
        # the exact legacy payload unless the protected registry opts in.
        if result["task"].get("worker_input", "legacy-v1") == "context-v2":
            payload = C.worker_input(registry, call, result)
        entry = {"schema_version": "1.0", "operation_id": call["operation_id"], "call_digest": result["call_digest"], "subject": subject, "principal": self.clients[subject]["principal"],
                 "registry_digest": result["registry_digest"], "grant_digest": result["grant_digest"], "signer_ids": result["signer_ids"],
                 "task_id": call["task_id"], "target_id": result["task"]["target_id"], "policy_digest": registry["policy_digest"], "intent_at": datetime.now(timezone.utc).isoformat(),
                 "admission_kind": "exact" if result["exact_required"] else "scoped", "risk": result["task"]["risk"], "mode": result["mode"],
                 "status": "launch_intent", "exit_code": None}
        if mutation:
            atomic(target_latch, {"operation_id": call["operation_id"], "call_digest": result["call_digest"]})
        atomic(journal, entry)  # No process before durable file + directory sync.
        self.audit_append(call["operation_id"] + "-intent", entry)
        # Source changes are irrelevant to the frozen private snapshot; executable
        # and its dependencies must be OS-protected from the agent principal.
        if C.digest(regular(Path(result["task"]["executable"]["path"]), 128 * 1024 * 1024)) != result["task"]["executable"]["digest"]:
            raise C.Denied("executable changed at final admission")
        def final_check():
            current_registry, final = self.context(packet, subject)
            if final["call_digest"] != result["call_digest"] or C.digest(current_registry) != C.digest(registry):
                raise C.Denied("admission changed before launch")
            return {"principal": self.clients[subject]["principal"], **final["request"]["execution"]}
        launched = False
        try:
            launched = True
            outcome = self.launch(argv, environment, payload, run_dir, result["task"], final_check)
            entry.update(outcome)
            entry["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.audit_append(call["operation_id"] + "-outcome", entry)
            atomic(journal, entry)
            if mutation and entry["status"] == "executed" and entry["exit_code"] == 0 and entry.get("result_valid") is True:
                target_latch.unlink()
                LOCK.sync_directory(target_latch.parent)
        except NotLaunched:
            entry.update(status="blocked_before_launch", exit_code=None)
            self.audit_append(call["operation_id"] + "-blocked", entry)
            atomic(journal, entry)
            if mutation:
                target_latch.unlink()
                LOCK.sync_directory(target_latch.parent)
            return {"status": "blocked_before_launch", "exit_code": None, "call_digest": result["call_digest"]}
        except Exception:
            if launched:
                self.poisoned = True
                # Leave durable intent in place; do not claim a safe retry.
                return {"status": "outcome_unknown", "exit_code": None, "call_digest": result["call_digest"]}
            raise
        return {"status": entry["status"], "exit_code": entry["exit_code"], "replayed": False, "call_digest": result["call_digest"],
                "result_valid": entry["result_valid"], "result": entry["result"]}


def handler(broker):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):
            try:
                if self.headers.get("Transfer-Encoding") is not None or len(self.headers.get_all("Content-Length", [])) != 1:
                    raise C.Denied("one bounded content length required")
                length = int(self.headers["Content-Length"])
                if not 0 < length <= C.MAX_INPUT:
                    raise C.Denied("body exceeds bound")
                self.connection.settimeout(10)
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise C.Denied("incomplete request body")
                routes = {"/v1/prepare": "prepare", "/v1/execute": "execute", "/v1/restrict": "restrict", "/v1/status": "status", "/v1/describe": "describe"}
                if self.path not in routes:
                    raise C.Denied("unknown route")
                certificate = self.connection.getpeercert(binary_form=True)
                if not certificate:
                    raise C.Denied("authenticated client certificate required")
                subject = C.digest(certificate)
                result = broker.dispatch(routes[self.path], C.decode(raw), subject)
                status = 200
            except Exception:
                result, status = {"status": "blocked", "reason": "invalid, unavailable, expired or unadmitted operation"}, 403
            body = C.canonical(result)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass  # Never log bearer grants, parameters, paths or headers.
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    broker, server = None, None
    try:
        if not sys.platform.startswith("linux"):
            raise C.Denied("broker service requires a separately provisioned Unix principal; Windows clients use TLS")
        config = C.read_record(args.config)
        C.exact(config, {"registry", "bundle_dir", "state_dir", "worker_dir", "host", "port", "certificate", "private_key", "client_ca", "agent_uids", "agent_gids"})
        for name in ("registry", "bundle_dir", "state_dir", "worker_dir", "certificate", "private_key", "client_ca"):
            if not Path(config[name]).is_absolute():
                raise C.Denied("absolute managed configuration paths required")
        if os.geteuid() != 0:
            raise C.Denied("broker requires an isolated supervisor able to drop worker identities")
        immutable(args.config)
        verify_deployment(config)
        registry = C.read_record(Path(config["registry"]))
        C.validate_registry(registry)
        for task in registry["tasks"].values():
            immutable(Path(task["executable"]["path"]))
        for agents, worker in (("agent_uids", "worker_uid"), ("agent_gids", "worker_gid")):
            if (not isinstance(config[agents], list) or not config[agents]
                    or any(type(value) is not int or value <= 0 for value in config[agents])
                    or any(task[worker] in config[agents] for task in registry["tasks"].values())):
                raise C.Denied("agent and worker principals/groups must be separate")
        broker = Broker(config["registry"], config["bundle_dir"], config["state_dir"], config["worker_dir"])
        class BoundedServer(ThreadingHTTPServer):
            slots = threading.BoundedSemaphore(32)

            def process_request(self, request, address):
                if not self.slots.acquire(blocking=False):
                    request.close()
                    return
                try:
                    super().process_request(request, address)
                except Exception:
                    self.slots.release()
                    raise

            def process_request_thread(self, request, address):
                try:
                    super().process_request_thread(request, address)
                finally:
                    self.slots.release()
        server = BoundedServer((config["host"], config["port"]), handler(broker))
        server.daemon_threads = True
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(config["certificate"], config["private_key"])
        context.load_verify_locations(cafile=config["client_ca"])
        context.verify_mode = ssl.CERT_REQUIRED
        original_get_request = server.get_request
        def secure_request():
            connection, address = original_get_request()
            connection.settimeout(5)
            try:
                return context.wrap_socket(connection, server_side=True), address
            except Exception:
                connection.close()
                raise
        server.get_request = secure_request
        print("READY: protected task broker", flush=True)
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("BLOCKED: broker configuration, identity or storage unavailable", file=sys.stderr)
        return 3
    finally:
        if server is not None:
            server.server_close()
        if broker is not None:
            broker.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
