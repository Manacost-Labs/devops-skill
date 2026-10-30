#!/usr/bin/env python3
"""Inspect saved GCP instance-insert evidence, without cloud calls or retry authority."""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID


CHECKLIST_FIELDS = {"project", "zone", "operation_name", "operation_id", "request_id", "instance_name", "target_id"}
CAPTURE_FIELDS = {"operation", "instance"}
MAX_INPUT_BYTES = 8 * 1024 * 1024
INSTANCE_STATES = {"PROVISIONING", "STAGING", "RUNNING", "STOPPING", "SUSPENDING", "SUSPENDED", "REPAIRING", "TERMINATED"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def numeric_id(value):
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,19}", value) is not None and int(value) <= 2**64 - 1


def resource_url(value, expected_path):
    require(isinstance(value, str), "missing resource URL")
    require(all(33 <= ord(character) <= 126 for character in value), "invalid resource URL characters")
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.netloc in {"www.googleapis.com", "compute.googleapis.com"}
            and not parsed.query and not parsed.fragment and parsed.path == "/compute/v1/" + expected_path,
            "resource URL differs from retained scope")


def inspect(checklist, capture):
    """Correlate native Operation and independent GET; never a completion decision."""
    require(isinstance(checklist, dict) and set(checklist) == CHECKLIST_FIELDS, "invalid checklist fields")
    require(isinstance(capture, dict) and set(capture) == CAPTURE_FIELDS, "invalid capture fields")
    for field in ("project", "zone", "instance_name", "operation_name"):
        require(isinstance(checklist[field], str) and re.fullmatch(r"[a-z][a-z0-9-]{0,127}", checklist[field]) is not None,
                "invalid retained resource name")
    require(numeric_id(checklist["operation_id"]) and numeric_id(checklist["target_id"]), "invalid retained numeric identity")
    request_id = checklist["request_id"]
    require(isinstance(request_id, str), "missing request UUID")
    parsed_uuid = UUID(request_id)
    require(parsed_uuid.int != 0 and str(parsed_uuid) == request_id, "request UUID is zero or noncanonical")
    root = f"projects/{checklist['project']}/zones/{checklist['zone']}"
    instance_path = root + "/instances/" + checklist["instance_name"]
    operation = capture["operation"]
    require(isinstance(operation, dict), "missing native operation")
    require(not {"nextPageToken", "items"} & set(operation), "list response is not one native operation")
    require(operation.get("kind") == "compute#operation" and "region" not in operation, "not a zonal operation")
    require(operation.get("name") == checklist["operation_name"] and operation.get("id") == checklist["operation_id"],
            "operation identity differs")
    require(operation.get("clientOperationId") == request_id and operation.get("operationType") == "insert",
            "request identity or method differs")
    require(operation.get("targetId") == checklist["target_id"], "target incarnation differs")
    resource_url(operation.get("selfLink"), root + "/operations/" + checklist["operation_name"])
    resource_url(operation.get("zone"), root)
    resource_url(operation.get("targetLink"), instance_path)
    status = operation.get("status")
    require(isinstance(status, str) and status in {"PENDING", "RUNNING", "DONE"}, "unknown operation status")
    failed = False
    if "error" in operation:
        error = operation["error"]
        require(isinstance(error, dict) and isinstance(error.get("errors"), list) and bool(error["errors"])
                and all(isinstance(item, dict) and isinstance(item.get("code"), str) and bool(item["code"])
                        for item in error["errors"]), "malformed native operation error")
        failed = True
    if "httpErrorStatusCode" in operation:
        code = operation["httpErrorStatusCode"]
        require(type(code) is int and 400 <= code <= 599, "malformed HTTP error status")
        failed = True
    if "httpErrorMessage" in operation:
        require(isinstance(operation["httpErrorMessage"], str), "malformed HTTP error message")
        failed = failed or bool(operation["httpErrorMessage"])
    require(not failed or status == "DONE", "error in a nonterminal operation")
    warnings = operation.get("warnings", [])
    require(isinstance(warnings, list) and all(isinstance(item, dict) for item in warnings), "malformed warnings")
    instance = capture["instance"]
    if instance is not None:
        require(isinstance(instance, dict) and instance.get("kind") == "compute#instance", "invalid native instance GET")
        require(instance.get("id") == checklist["target_id"] and instance.get("name") == checklist["instance_name"],
                "instance incarnation differs")
        resource_url(instance.get("selfLink"), instance_path)
        resource_url(instance.get("zone"), root)
        require(isinstance(instance.get("status"), str) and instance["status"] in INSTANCE_STATES, "unknown instance state")
    if failed:
        observation = "failed"
    elif status != "DONE":
        observation = "pending"
    elif instance is None:
        observation = "resource_unobserved"
    elif instance["status"] != "RUNNING":
        observation = "resource_not_running"
    else:
        observation = "control_plane_match"
    return {"observation": observation, "warnings_present": bool(warnings), "retry_authorized": False,
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
