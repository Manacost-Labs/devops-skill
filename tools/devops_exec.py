#!/usr/bin/env python3
"""Call a separately protected task broker; arbitrary local argv never executes."""
from __future__ import annotations

import argparse
import http.client
import importlib.util
import json
from pathlib import Path
import ssl
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


C = module("broker_client_contract", ROOT / "devops-platform-contracts/scripts/broker_contract.py")
SUPPORT = module("broker_client_lock", ROOT / "tools/runtime_lock.py")
BLOCKED_EXIT = 3


class Refused(C.Denied):
    """An authenticated broker explicitly refused this request."""


def call_broker(config, packet, route):
    C.exact(config, {"url", "ca_file", "client_certificate", "client_private_key", "timeout_seconds"})
    url = config["url"]
    if not isinstance(url, str) or any(c.isspace() or ord(c) < 32 for c in url) or "\\" in url:
        raise C.Denied("invalid broker URL")
    endpoint = urlsplit(url)
    if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username is not None or endpoint.password is not None or endpoint.path not in {"", "/"} or endpoint.query or endpoint.fragment:
        raise C.Denied("explicit HTTPS broker origin required")
    if not Path(config["ca_file"]).is_absolute() or type(config["timeout_seconds"]) is not int or not 1 <= config["timeout_seconds"] <= 330:
        raise C.Denied("managed trust file and timeout required")
    context = ssl.create_default_context(cafile=config["ca_file"])
    for name in ("client_certificate", "client_private_key"):
        if not Path(config[name]).is_absolute():
            raise C.Denied("absolute client identity references required")
    context.load_cert_chain(config["client_certificate"], config["client_private_key"])
    connection = http.client.HTTPSConnection(endpoint.hostname, endpoint.port or 443, timeout=config["timeout_seconds"], context=context)
    attempted = False
    try:
        connection.connect()  # Strict SAN/chain trust before any capability leaves.
        attempted = True
        connection.request("POST", "/v1/" + route, body=C.canonical(packet), headers={"Content-Type": "application/json", "Connection": "close"})
        response = connection.getresponse()
        body = response.read(C.MAX_INPUT + 1)
        result = C.decode(body)
        if not isinstance(result, dict):
            raise ValueError("invalid broker result")
        if response.status == 403 and result.get("status") == "blocked":
            raise Refused("broker refused operation")
        if response.status != 200:
            raise ValueError("unverified broker response")
        if route == "execute" and result.get("status") not in {"executed", "outcome_unknown", "blocked_before_launch"}:
            raise ValueError("invalid broker result")
        return result
    except Refused:
        raise
    except (OSError, http.client.HTTPException, ValueError):
        if attempted and route == "execute":
            return {"status": "outcome_unknown", "reason": "request may have reached broker; reconcile the same operation ID"}
        raise C.Denied("broker connection unavailable") from None
    finally:
        connection.close()


def execute():
    if "--" in sys.argv[1:] or "--operation" in sys.argv[1:] or "--at" in sys.argv[1:]:
        print("BLOCKED: arbitrary argv and request-embedded approvals cannot authorize execution; use a registered broker task")
        return BLOCKED_EXIT
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--broker-config", type=Path, required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--grant", type=Path)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--route", choices=("prepare", "execute", "restrict", "status", "describe"), default="execute")
    parser.add_argument("--mode", choices=tuple(C.MODES))
    parser.add_argument("--task-id")
    parser.add_argument("--parameters")
    parser.add_argument("--operation-id")
    args = parser.parse_args()
    try:
        if not args.broker_config.is_absolute():
            raise C.Denied("absolute managed broker profile required")
        if args.route == "restrict":
            if args.request or args.admission or args.task_id or args.parameters or args.operation_id:
                raise C.Denied("restriction takes no operation request or exact admission")
            packet = {"mode": args.mode or "safe", "grant": C.read_record(args.grant) if args.grant else None}
        elif args.route == "status":
            if args.grant or args.admission or args.mode or args.task_id or args.parameters or bool(args.request) == bool(args.operation_id):
                raise C.Denied("status takes only an operation receipt request")
            packet = C.read_record(args.request) if args.request else {"operation_id": args.operation_id}
        elif args.route == "describe":
            if not args.grant or args.request or args.admission or args.mode or args.task_id or args.parameters or args.operation_id:
                raise C.Denied("description takes only signed grant")
            packet = {"grant": C.read_record(args.grant)}
        else:
            if not args.grant or args.mode or bool(args.request) == bool(args.task_id):
                raise C.Denied("typed request and signed grant required")
            if args.request:
                if args.parameters or args.operation_id:
                    raise C.Denied("duplicate call specification")
                call = C.read_record(args.request)
            else:
                if not args.parameters or not args.operation_id:
                    raise C.Denied("typed parameters and operation identifier required")
                call = {"schema_version": "1.0", "task_id": args.task_id, "parameters": C.decode(args.parameters), "operation_id": args.operation_id}
            packet = {"call": call, "grant": C.read_record(args.grant), "admission": C.read_record(args.admission) if args.admission else None}
        result = call_broker(C.read_record(args.broker_config), packet, args.route)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        if result.get("status") in {"outcome_unknown", "launch_intent"}:
            return 4
        if result.get("status") == "executed":
            return 0 if result.get("exit_code") == 0 and result.get("result_valid") is True else 1
        return 0 if result.get("status") in {"prepared", "restricted", "described"} else BLOCKED_EXIT
    except Exception:
        print("BLOCKED: invalid or unavailable broker profile, signed authority or typed request; no local command was launched")
        return BLOCKED_EXIT


def main():
    # The remote supervisor owns the execution/upgrade locks. A read-only client
    # must not create local authority or require writable runtime state.
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
