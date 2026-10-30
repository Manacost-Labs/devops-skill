#!/usr/bin/env python3
"""Inspect saved Azure VM async observations; never poll or authorize a write."""
import argparse
import json
import re
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


MAX_INPUT_BYTES = 8 * 1024 * 1024
CHECKLIST_FIELDS = {
    "cloud", "tenant_id", "subscription_id", "resource_id", "vm_id", "location", "operation_url",
}
CAPTURE_FIELDS = {
    "cloud", "tenant_id", "subscription_id", "operation_url", "poll_http_status", "poll_body",
    "resource_http_status", "resource_body",
}
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
RESOURCE = re.compile(
    rf"/subscriptions/(?P<subscription>{UUID})/resourceGroups/[a-z0-9_.()-]{{1,90}}/"
    r"providers/Microsoft\.Compute/virtualMachines/[a-z0-9_.-]{1,64}", re.IGNORECASE,
)
OPERATION = re.compile(
    rf"/subscriptions/(?P<subscription>{UUID})/providers/Microsoft\.Compute/locations/"
    rf"(?P<location>[a-z0-9]{{1,64}})/operations/(?P<operation>{UUID})", re.IGNORECASE,
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def guid(value):
    require(isinstance(value, str) and re.fullmatch(UUID, value, re.IGNORECASE) is not None, "invalid GUID")
    result = uuid.UUID(value)
    require(result.int != 0, "zero GUID is not an established identity")
    return str(result)


def resource_identity(value, subscription):
    require(isinstance(value, str), "invalid VM resource identity")
    match = RESOURCE.fullmatch(value)
    require(match is not None and guid(match["subscription"]) == subscription, "VM scope differs")
    return value.casefold()


def operation_identity(value, subscription, location):
    require(isinstance(value, str) and len(value) <= 65536, "invalid operation URL")
    require(not any(ord(char) <= 32 or ord(char) == 127 for char in value) and "\\" not in value, "unsafe operation URL")
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.netloc == "management.azure.com" and not parsed.fragment, "foreign or unsafe operation origin")
    match = OPERATION.fullmatch(parsed.path)
    require(match is not None and guid(match["subscription"]) == subscription, "operation scope differs")
    require(match["location"].casefold() == location and guid(match["operation"]), "operation location differs")
    query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    require(len(query) == 1 and query[0][0] == "api-version" and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", query[0][1]) is not None, "unsupported operation query")
    return parsed.path.casefold()


def observation(value):
    return {
        "observation": value,
        "retry_authorized": False,
        "cleanup_authorized": False,
        "service_health_verified": False,
        "full_plan_verified": False,
    }


def inspect(checklist, capture):
    """Evaluate a retained Azure-AsyncOperation/VM subset, not overall success."""
    require(isinstance(checklist, dict) and set(checklist) == CHECKLIST_FIELDS, "invalid checklist fields")
    require(isinstance(capture, dict) and set(capture) == CAPTURE_FIELDS, "invalid capture fields")
    require(checklist["cloud"] == capture["cloud"] == "AzureCloud", "unsupported cloud")
    tenant = guid(checklist["tenant_id"])
    subscription = guid(checklist["subscription_id"])
    require(guid(capture["tenant_id"]) == tenant and guid(capture["subscription_id"]) == subscription, "capture scope differs")
    vm_id = guid(checklist["vm_id"])
    location = checklist["location"]
    require(isinstance(location, str) and re.fullmatch(r"[a-z0-9]{1,64}", location) is not None, "invalid location")
    resource_id = resource_identity(checklist["resource_id"], subscription)
    operation_path = operation_identity(checklist["operation_url"], subscription, location)
    operation_identity(capture["operation_url"], subscription, location)
    require(capture["operation_url"] == checklist["operation_url"], "different retained operation URL")
    for status_field, body_field in (("poll_http_status", "poll_body"), ("resource_http_status", "resource_body")):
        status, body = capture[status_field], capture[body_field]
        require(status is None or type(status) is int and 100 <= status <= 599, "invalid HTTP observation")
        require((status is None and body is None) or (status is not None and isinstance(body, dict)), "invalid body/status pair")
    provisioning = None
    if capture["resource_http_status"] == 200:
        resource = capture["resource_body"]
        require("error" not in resource and resource_identity(resource.get("id"), subscription) == resource_id, "VM observation differs")
        resource_type = resource.get("type")
        require(isinstance(resource_type, str) and resource_type.casefold() == "microsoft.compute/virtualmachines", "different resource type")
        require(resource.get("location") == location, "VM location differs")
        properties = resource.get("properties")
        require(isinstance(properties, dict) and guid(properties.get("vmId")) == vm_id, "VM incarnation differs")
        provisioning = properties.get("provisioningState")
        require(isinstance(provisioning, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,63}", provisioning) is not None, "missing VM provisioning state")
    if capture["poll_http_status"] != 200:
        return observation("poll_unavailable")
    poll = capture["poll_body"]
    status = poll.get("status")
    require(isinstance(status, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,63}", status) is not None, "missing async status")
    if "id" in poll:
        require(isinstance(poll["id"], str) and poll["id"].casefold() == operation_path, "poll body operation differs")
    if "name" in poll:
        require(guid(poll["name"]) == operation_path.rsplit("/", 1)[1], "poll body operation name differs")
    if status in {"Failed", "Canceled"}:
        return observation("failed")
    require("error" not in poll, "async status contradicts error")
    if status != "Succeeded":
        return observation("pending")
    if capture["resource_http_status"] != 200:
        return observation("resource_unobserved")
    if provisioning in {"Failed", "Canceled"}:
        return observation("failed")
    return observation("control_plane_match" if provisioning == "Succeeded" else "resource_pending")


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
    except (ValueError, OSError, TypeError, AttributeError, RecursionError):
        print(json.dumps(observation("rejected"), sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result["observation"] == "control_plane_match" else 2


if __name__ == "__main__":
    raise SystemExit(main())
