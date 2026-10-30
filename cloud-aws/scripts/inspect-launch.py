#!/usr/bin/env python3
"""Inspect saved AWS launch observations; never call AWS or authorize a retry."""
import argparse
import json
import re
from pathlib import Path


CHECKLIST_FIELDS = {
    "account_id", "partition", "region", "client_token", "count", "image_id",
    "instance_type", "subnet_id", "security_group_ids",
}
CAPTURE_FIELDS = {"account_id", "partition", "region", "response"}
STATES = {"pending", "running", "shutting-down", "terminated", "stopping", "stopped"}
STATE_CODES = {"pending": 0, "running": 16, "shutting-down": 32, "terminated": 48, "stopping": 64, "stopped": 80}
MAX_INPUT_BYTES = 8 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identifier(value, prefix):
    return isinstance(value, str) and re.fullmatch(prefix + r"-(?:[0-9a-f]{8}|[0-9a-f]{17})", value) is not None


def group_ids(value):
    require(isinstance(value, list) and bool(value), "security-group list is missing")
    require(all(identifier(item, "sg") for item in value), "invalid security-group identity")
    require(len(value) == len(set(value)), "duplicate security-group identity")
    return set(value)


def inspect(checklist, capture):
    """Return an advisory subset observation, not a platform completion status."""
    require(isinstance(checklist, dict) and set(checklist) == CHECKLIST_FIELDS, "invalid checklist fields")
    require(isinstance(capture, dict) and set(capture) == CAPTURE_FIELDS, "invalid capture fields")
    require(isinstance(checklist["account_id"], str) and re.fullmatch(r"[0-9]{12}", checklist["account_id"]) is not None, "invalid account identity")
    for field in ("partition", "region", "instance_type"):
        require(isinstance(checklist[field], str) and re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,63}", checklist[field]) is not None, "invalid checklist identity")
    for field in ("account_id", "partition", "region"):
        require(capture[field] == checklist[field], "capture scope differs from checklist")
    token = checklist["client_token"]
    require(isinstance(token, str) and 1 <= len(token) <= 64 and all(33 <= ord(c) <= 126 for c in token), "invalid retained client token")
    require(type(checklist["count"]) is int and 1 <= checklist["count"] <= 100, "count outside local inspection bound")
    require(identifier(checklist["image_id"], "ami") and identifier(checklist["subnet_id"], "subnet"), "invalid launch resource identity")
    expected_groups = group_ids(checklist["security_group_ids"])
    response = capture["response"]
    require(isinstance(response, dict) and "NextToken" not in response, "incomplete or invalid DescribeInstances response")
    require("Error" not in response and "Errors" not in response, "error response cannot establish launch state")
    if "ResponseMetadata" in response:
        metadata = response["ResponseMetadata"]
        require(isinstance(metadata, dict), "invalid response metadata")
        if "HTTPStatusCode" in metadata:
            require(type(metadata["HTTPStatusCode"]) is int and metadata["HTTPStatusCode"] == 200, "unsuccessful response metadata")
    reservations = response.get("Reservations")
    require(isinstance(reservations, list), "missing reservation list")
    instances = []
    identities = set()
    for reservation in reservations:
        require(isinstance(reservation, dict) and reservation.get("OwnerId") == checklist["account_id"], "reservation owner differs")
        batch = reservation.get("Instances")
        require(isinstance(batch, list) and bool(batch), "invalid instance list")
        for instance in batch:
            require(isinstance(instance, dict), "invalid instance observation")
            identity = instance.get("InstanceId")
            require(identifier(identity, "i") and identity not in identities, "invalid or duplicate instance identity")
            identities.add(identity)
            for observed, expected in (("ClientToken", "client_token"), ("ImageId", "image_id"), ("InstanceType", "instance_type"), ("SubnetId", "subnet_id")):
                require(instance.get(observed) == checklist[expected], "observed launch fields differ")
            groups = instance.get("SecurityGroups")
            require(isinstance(groups, list) and all(isinstance(group, dict) for group in groups), "invalid observed security groups")
            require(group_ids([group.get("GroupId") for group in groups]) == expected_groups, "observed security groups differ")
            state = instance.get("State")
            require(isinstance(state, dict) and isinstance(state.get("Name"), str) and state["Name"] in STATES, "invalid instance state")
            if "Code" in state:
                require(type(state["Code"]) is int and 0 <= state["Code"] <= 65535 and state["Code"] & 255 == STATE_CODES[state["Name"]], "contradictory instance state")
            instances.append(state["Name"])
    require(len(instances) <= checklist["count"], "more instances than checklist permits")
    if not instances:
        observation = "unobserved"
    elif any(state not in {"pending", "running"} for state in instances):
        observation = "terminal"
    elif len(instances) < checklist["count"]:
        observation = "partial"
    elif "pending" in instances:
        observation = "pending"
    else:
        observation = "control_plane_match"
    return {
        "observation": observation,
        "observed_count": len(instances),
        "retry_authorized": False,
        "service_health_verified": False,
        "full_plan_verified": False,
    }


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
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique)


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
