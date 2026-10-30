#!/usr/bin/env python3
"""Inspect saved native Nova server details; never call a cloud or permit replay."""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID


CHECKLIST_FIELDS = {"project_id", "pool", "pool_segment", "compute_endpoint", "server_id", "volume_ids"}
CAPTURE_FIELDS = {"project_id", "pool", "compute_endpoint", "response"}
MAX_INPUT_BYTES = 8 * 1024 * 1024
SERVER_STATES = {
    "ACTIVE", "BUILD", "DELETED", "ERROR", "HARD_REBOOT", "MIGRATING", "PASSWORD",
    "PAUSED", "REBOOT", "REBUILD", "RESCUE", "RESIZE", "REVERT_RESIZE", "SHELVED",
    "SHELVED_OFFLOADED", "SHUTOFF", "SOFT_DELETED", "SUSPENDED", "UNKNOWN", "VERIFY_RESIZE",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def uuid_identity(value, compact=False):
    require(isinstance(value, str), "missing UUID")
    parsed = UUID(value)
    allowed = {str(parsed), parsed.hex} if compact else {str(parsed)}
    require(parsed.int != 0 and value in allowed, "noncanonical or empty UUID")
    return parsed.hex


def endpoint(value):
    require(isinstance(value, str) and 1 <= len(value) <= 2048
            and all(33 <= ord(character) <= 126 for character in value), "invalid endpoint characters")
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.hostname is not None and parsed.username is None
            and parsed.password is None and not parsed.query and not parsed.fragment, "invalid endpoint scope")
    host = parsed.hostname
    require(re.fullmatch(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", host) is not None, "invalid endpoint host")
    authority = host if parsed.port is None else f"{host}:{parsed.port}"
    require(parsed.netloc == authority and (parsed.port is None or 1 <= parsed.port <= 65535), "ambiguous endpoint authority")
    require(re.fullmatch(r"/[A-Za-z0-9/_.-]*", parsed.path) is not None
            and not {".", ".."} & set(parsed.path.split("/")), "invalid endpoint path")


def volume_ids(value):
    require(isinstance(value, list) and 1 <= len(value) <= 255, "invalid expected volume list")
    identities = [uuid_identity(item) for item in value]
    require(len(identities) == len(set(identities)), "duplicate volume UUID")
    return set(identities)


def inspect(checklist, capture):
    """Return an advisory saved-state subset observation, never execution authority."""
    require(isinstance(checklist, dict) and set(checklist) == CHECKLIST_FIELDS, "invalid checklist fields")
    require(isinstance(capture, dict) and set(capture) == CAPTURE_FIELDS, "invalid capture fields")
    project = uuid_identity(checklist["project_id"], compact=True)
    server_id = uuid_identity(checklist["server_id"])
    expected_volumes = volume_ids(checklist["volume_ids"])
    for field in ("pool", "pool_segment"):
        require(isinstance(checklist[field], str) and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", checklist[field]) is not None,
                "invalid retained pool scope")
    endpoint(checklist["compute_endpoint"])
    require(uuid_identity(capture["project_id"], compact=True) == project, "capture project differs")
    for field in ("pool", "compute_endpoint"):
        require(capture[field] == checklist[field], "capture scope differs")
    response = capture["response"]
    observation = "resource_unobserved"
    if response is not None:
        require(isinstance(response, dict) and set(response) == {"server"}, "not one native server GET")
        server = response["server"]
        require(isinstance(server, dict), "missing native server")
        require(uuid_identity(server.get("id")) == server_id, "server incarnation differs")
        require(uuid_identity(server.get("tenant_id"), compact=True) == project, "server project differs")
        require(server.get("OS-EXT-AZ:availability_zone") == checklist["pool_segment"], "server segment differs")
        status = server.get("status")
        require(isinstance(status, str) and status in SERVER_STATES, "unknown server status")
        require("OS-EXT-STS:task_state" in server, "task state unavailable")
        task = server["OS-EXT-STS:task_state"]
        require(task is None or (isinstance(task, str) and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", task) is not None),
                "invalid task state")
        vm_state = server.get("OS-EXT-STS:vm_state")
        require(isinstance(vm_state, str) and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", vm_state) is not None, "invalid VM state")
        power = server.get("OS-EXT-STS:power_state")
        require(type(power) is int and power in {0, 1, 3, 4, 6, 7}, "power state unavailable or invalid")
        attachments = server.get("os-extended-volumes:volumes_attached")
        require(isinstance(attachments, list) and all(isinstance(item, dict) for item in attachments), "invalid attachments")
        observed = [uuid_identity(item.get("id")) for item in attachments]
        require(len(observed) == len(set(observed)), "duplicate observed volume")
        observed_volumes = set(observed)
        require(observed_volumes <= expected_volumes, "unexpected attached volume")
        fault = server.get("fault")
        require(fault is None or (isinstance(fault, dict) and bool(fault)), "invalid server fault")
        if status == "ERROR" or fault or vm_state == "error" or power == 6:
            observation = "attention_required"
        elif task is not None or status == "BUILD":
            observation = "pending"
        elif status != "ACTIVE" or vm_state != "active" or power != 1:
            observation = "resource_not_active"
        elif observed_volumes != expected_volumes:
            observation = "attachments_incomplete"
        else:
            observation = "control_plane_match"
    return {"observation": observation, "retry_authorized": False, "ownership_proven": False,
            "full_plan_verified": False, "service_health_verified": False}


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON field")
            result[key] = value
        return result

    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    require(len(raw) <= MAX_INPUT_BYTES, "input exceeds inspection bound")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checklist", required=True)
    parser.add_argument("--capture", required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect(load_json(args.checklist), load_json(args.capture))
    except (ValueError, OSError, TypeError, RecursionError):
        print(json.dumps({"observation": "rejected", "retry_authorized": False}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result["observation"] == "control_plane_match" else 2


if __name__ == "__main__":
    raise SystemExit(main())
