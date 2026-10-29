#!/usr/bin/env python3
"""Summarize one offline UID-bound v1 Pod snapshot from bounded stdin; no cluster I/O."""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid

MAX_BYTES = 1048576
MAX_ITEMS = 32
LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
QUANTITY = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+|[numkKMGTP]|[KMGTPE]i)?")
REASONS = {"OOMKilled", "Error", "Completed", "ContainerCannotRun", "StartError", "CrashLoopBackOff",
           "ImagePullBackOff", "ErrImagePull", "CreateContainerConfigError", "CreateContainerError",
           "ContainerCreating", "RunContainerError", "InvalidImageName", "PodInitializing",
           "ErrImageNeverPull", "Evicted", "DeadlineExceeded", "NodeLost", "UnexpectedAdmissionError"}


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def read_snapshot(stream):
    raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("snapshot too large")
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def mapping(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("mapping required")
    return value


def sequence(value):
    if value is not None and (not isinstance(value, list) or any(not isinstance(x, dict) for x in value)):
        raise ValueError("object array required")
    return value


def number(value):
    if value is not None and (type(value) is not int or not 0 <= value <= 2**63 - 1):
        raise ValueError("invalid count")
    return value


def boolean(value):
    if value is not None and type(value) is not bool:
        raise ValueError("invalid boolean")
    return value


def enum(value, allowed):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("invalid enum")
    return value if value in allowed else "other_or_unknown"


def label(value):
    if not isinstance(value, str) or not LABEL.fullmatch(value):
        raise ValueError("invalid label")
    return value


def resources(value):
    value = mapping(value)
    result = {}
    for group in ("requests", "limits"):
        original = mapping(value.get(group))
        result[group] = {}
        for name in ("cpu", "memory", "ephemeral-storage"):
            quantity = original.get(name)
            if quantity is not None and (not isinstance(quantity, (str, int)) or isinstance(quantity, bool)):
                raise ValueError("invalid resource quantity")
            if quantity is not None and (len(str(quantity)) > 40 or not QUANTITY.fullmatch(str(quantity))):
                raise ValueError("invalid resource quantity")
            result[group][name] = quantity
    return result


def container_state(value):
    value = mapping(value)
    present = [key for key in ("waiting", "running", "terminated") if value.get(key) is not None]
    if len(present) > 1:
        raise ValueError("ambiguous container state")
    if not present:
        return {"kind": "unreported", "reason": None, "exit_code": None, "signal": None}
    kind = present[0]
    state = mapping(value[kind])
    return {"kind": kind, "reason": enum(state.get("reason"), REASONS),
            "exit_code": number(state.get("exitCode")), "signal": number(state.get("signal"))}


def summarize(data, namespace, name, expected_uid):
    label(namespace)
    if not isinstance(name, str) or len(name) > 253 or any(not LABEL.fullmatch(part) for part in name.split(".")):
        raise ValueError("invalid Pod name")
    if str(uuid.UUID(expected_uid)) != expected_uid:
        raise ValueError("canonical UID required")
    data = mapping(data)
    metadata = mapping(data.get("metadata"))
    if data.get("apiVersion") != "v1" or data.get("kind") != "Pod":
        raise ValueError("one v1 Pod required")
    if (metadata.get("namespace"), metadata.get("name"), metadata.get("uid")) != (namespace, name, expected_uid):
        raise ValueError("Pod identity mismatch")
    spec, status = mapping(data.get("spec")), mapping(data.get("status"))
    result = {"status": "snapshot_observed", "verification": "not_assessed", "target_authenticity": "not_verified",
              "namespace": namespace, "pod_name": name, "pod_uid": expected_uid,
              "phase": enum(status.get("phase"), {"Pending", "Running", "Succeeded", "Failed", "Unknown"}),
              "pod_reason": enum(status.get("reason"), REASONS), "usage_and_node_pressure": "not_collected",
              "pod_resources": resources(spec.get("resources")), "resource_evidence": "declared_spec_only",
              "containers": {}, "unknown_fields": [], "truncated": False,
              "sensitive_text": "messages, commands, env, annotations, images, addresses and secret/claim references omitted"}
    for spec_key, status_key in (("containers", "containerStatuses"), ("initContainers", "initContainerStatuses"),
                                 ("ephemeralContainers", "ephemeralContainerStatuses")):
        declared = sequence(spec.get(spec_key))
        observed = sequence(status.get(status_key))
        if observed is None:
            if declared:
                result["unknown_fields"].append(status_key)
            result["containers"][spec_key] = None
            continue
        specifications = {}
        for item in declared or []:
            key = label(item.get("name"))
            if key in specifications:
                raise ValueError("duplicate container name")
            specifications[key] = item
        rows, seen = [], set()
        for item in observed:
            key = label(item.get("name"))
            if key in seen:
                raise ValueError("duplicate container status")
            seen.add(key)
            current, previous = container_state(item.get("state")), container_state(item.get("lastState"))
            if current["kind"] == "unreported" or item.get("ready") is None or item.get("restartCount") is None:
                result["unknown_fields"].append(status_key + ".selected_fields")
            definition = specifications.get(key)
            if definition is None:
                result["unknown_fields"].append(status_key + ".spec_match")
            rows.append({"name": key, "ready": boolean(item.get("ready")), "restart_count": number(item.get("restartCount")),
                         "current": current, "previous": previous,
                         "resources": resources(None if definition is None else definition.get("resources")),
                         "init_restart_policy": enum(None if definition is None else definition.get("restartPolicy"), {"Always"})})
        if set(specifications) - seen:
            result["unknown_fields"].append(status_key + ".missing_status")
        result["containers"][spec_key] = rows[:MAX_ITEMS]
        result["truncated"] |= len(rows) > MAX_ITEMS
    conditions = sequence(status.get("conditions"))
    result["conditions"] = None if conditions is None else [
        {"type": enum(item.get("type"), {"Ready", "ContainersReady", "Initialized", "PodScheduled", "PodReadyToStartContainers", "DisruptionTarget"}),
         "status": enum(item.get("status"), {"True", "False", "Unknown"})} for item in conditions[:MAX_ITEMS]]
    if conditions is None:
        result["unknown_fields"].append("conditions")
    result["truncated"] |= conditions is not None and len(conditions) > MAX_ITEMS
    if status.get("phase") is None:
        result["unknown_fields"].append("phase")
    if spec.get("containers") is None:
        result["unknown_fields"].append("spec.containers")
    result["unknown_fields"] = sorted(set(result["unknown_fields"]))
    result["completeness"] = "partial" if result["unknown_fields"] or result["truncated"] else "selected_fields_observed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--uid", required=True, help="expected Pod UID from trusted target discovery")
    args = parser.parse_args()
    try:
        result = summarize(read_snapshot(sys.stdin.buffer), args.namespace, args.name, args.uid)
    except (ValueError, TypeError, OSError, RecursionError, AttributeError):
        print(json.dumps({"status": "unknown", "verification": "not_assessed", "error": "invalid_or_mismatched_snapshot"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
